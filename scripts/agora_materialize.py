from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import jsonschema


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "registry/schema/materializer-plugin.schema.json"
GIT_TIMEOUT_SECONDS = 120
SANDBOX_OUTPUT_ROOT = "/agora-output"
_TREE_EXCLUDES = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".nox",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


class ManifestError(ValueError):
    """Materializer manifest is invalid or unsafe for the host contract."""


class AcquisitionError(RuntimeError):
    """No declared acquisition path could be completed."""


@dataclass(frozen=True)
class PreparedSource:
    path: Path
    provenance: dict[str, Any]
    cleanup_root: Path | None = None

    def cleanup(self) -> None:
        if self.cleanup_root is not None:
            shutil.rmtree(self.cleanup_root, ignore_errors=True)


@dataclass(frozen=True)
class StagingOutput:
    root: Path
    output: Path

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def _safe_relative(value: str, *, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{where} must be a non-empty relative path")
    normalized = value.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    if candidate.is_absolute() or ".." in candidate.parts or normalized.startswith("~"):
        raise ManifestError(f"{where} must stay inside its declared root: {value!r}")
    return candidate.as_posix()


def _validate_https_url(value: str, *, where: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ManifestError(f"{where} must be an https URL")
    if parsed.username is not None or parsed.password is not None:
        raise ManifestError(f"{where} must not contain embedded credentials")
    return value


def _validate_module_name(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestError("execution.module must be a non-empty Python module name")
    if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", value):
        raise ManifestError(f"unsafe Python module name: {value!r}")
    return value


def _validate_args(args: list[str]) -> list[str]:
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise ManifestError("execution.args must be a list of strings")
    allowed = {"source", "output", "source_revision"}
    for item in args:
        for match in re.finditer(r"\{([^{}]+)\}", item):
            if match.group(1) not in allowed:
                raise ManifestError(f"unsupported execution placeholder: {match.group(0)}")
    return args


def load_manifest(path: Path) -> dict[str, Any]:
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(data, schema)

    materializers = data.get("materializers", [])
    ids = [item.get("id") for item in materializers]
    if len(ids) != len(set(ids)):
        raise ManifestError("materializer ids must be unique")

    for materializer in materializers:
        execution = materializer["execution"]
        _validate_module_name(execution["module"])
        _validate_args(execution["args"])
        if execution.get("network") != "deny":
            raise ManifestError("contract v1 requires execution.network='deny'")

        acquisition_ids: list[str] = []
        for index, acquisition in enumerate(materializer["acquisition"]):
            acquisition_id = acquisition.get("id", str(index))
            if acquisition_id in acquisition_ids:
                raise ManifestError(f"duplicate acquisition id: {acquisition_id!r}")
            acquisition_ids.append(acquisition_id)
            if acquisition["type"] == "git":
                _validate_https_url(acquisition["url"], where="git acquisition URL")
                ref = acquisition.get("ref")
                if not isinstance(ref, str) or not ref:
                    raise ManifestError("git acquisition ref must be a non-empty immutable revision")
                if not re.fullmatch(r"[0-9a-fA-F]{40}", ref):
                    raise ManifestError(
                        "git acquisition ref must be a full 40-character commit SHA in contract v1"
                    )
                if "subpath" in acquisition:
                    _safe_relative(acquisition["subpath"], where="git acquisition subpath")

        for required in materializer["input"].get("required_globs", []):
            _safe_relative(required, where="input required_glob")
        for required in materializer["output"].get("required_paths", []):
            _safe_relative(required, where="output required_path")
    return data


def select_materializer(manifest: dict[str, Any], materializer_id: str) -> dict[str, Any]:
    matches = [item for item in manifest["materializers"] if item["id"] == materializer_id]
    if not matches:
        raise KeyError(f"unknown materializer id: {materializer_id!r}")
    if len(matches) != 1:
        raise ManifestError(f"materializer id is not unique: {materializer_id!r}")
    return matches[0]


def _isolated_git_environment(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "never",
        }
    )
    env.pop("GIT_ASKPASS", None)
    env.pop("SSH_ASKPASS", None)
    return env


def _git(*args: str, cwd: Path, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    return result.stdout.strip()


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda value: value.relative_to(root).as_posix()):
        relative = path.relative_to(root)
        if any(part in _TREE_EXCLUDES for part in relative.parts):
            continue
        if path.is_symlink():
            digest.update(b"L\0")
            digest.update(relative.as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(os.readlink(path).encode("utf-8"))
            digest.update(b"\0")
        elif path.is_file():
            digest.update(b"F\0")
            digest.update(relative.as_posix().encode("utf-8"))
            digest.update(b"\0")
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            digest.update(b"\0")
    return digest.hexdigest()


def _materializer_code_digest(root: Path) -> str:
    root = Path(root).resolve()
    installation_record = root / ".agora-environment.json"
    if installation_record.is_file():
        try:
            record = json.loads(installation_record.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError("managed materializer environment has unreadable identity metadata") from exc
        expected = record.get("runtime_tree_sha256")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("managed materializer environment has invalid runtime_tree_sha256")
        actual = _tree_digest(root)
        if actual != expected:
            raise ValueError(
                "managed materializer runtime no longer matches its installed identity; reinstall it"
            )
        return actual

    code_root = root / "src"
    if not code_root.is_dir():
        code_root = root
    return _tree_digest(code_root)


def _git_revision_for_path(path: Path) -> str | None:
    try:
        top = _git("rev-parse", "--show-toplevel", cwd=path)
        return _git("rev-parse", "HEAD", cwd=Path(top))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def _validate_local_source(path: Path, materializer: dict[str, Any]) -> dict[str, Any]:
    path = Path(path).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"materializer source is not a directory: {path}")
    if materializer["input"].get("allow_symlinks") is False:
        symlinks = [candidate for candidate in path.rglob("*") if candidate.is_symlink()]
        if symlinks:
            raise ValueError(f"materializer source contains symlinks but contract forbids them: {symlinks[0]}")
    for pattern in materializer["input"].get("required_globs", []):
        matches = list(path.glob(pattern))
        if not matches:
            raise ValueError(f"materializer source does not satisfy required_glob: {pattern}")
    return {
        "kind": "user-local",
        "name": path.name,
        "tree_sha256": _tree_digest(path),
        "git_head": _git_revision_for_path(path),
    }


def _acquire_git_source(acquisition: dict[str, Any], materializer: dict[str, Any]) -> PreparedSource:
    root = Path(tempfile.mkdtemp(prefix="agora-source-"))
    repo = root / "repo"
    home = root / "home"
    home.mkdir()
    repo.mkdir()
    env = _isolated_git_environment(home)
    try:
        _git("init", "-q", cwd=repo, env=env)
        _git("remote", "add", "origin", acquisition["url"], cwd=repo, env=env)
        _git(
            "fetch",
            "--quiet",
            "--depth",
            "1",
            "origin",
            acquisition["ref"],
            cwd=repo,
            env=env,
        )
        resolved = _git("rev-parse", "FETCH_HEAD", cwd=repo, env=env)
        _git("checkout", "--quiet", "--detach", resolved, cwd=repo, env=env)
        source = repo
        subpath = acquisition.get("subpath")
        if subpath:
            source = repo / _safe_relative(subpath, where="git acquisition subpath")
        if not source.is_dir():
            raise ValueError(f"git acquisition subpath is not a directory: {subpath!r}")
        local = _validate_local_source(source, materializer)
        provenance = {
            "kind": "git",
            "url": acquisition["url"],
            "requested_ref": acquisition["ref"],
            "resolved_commit": resolved,
            "subpath": subpath,
            "tree_sha256": local["tree_sha256"],
        }
        return PreparedSource(path=source, provenance=provenance, cleanup_root=root)
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise


def acquire_source(
    materializer: dict[str, Any],
    *,
    source_override: Path | None = None,
) -> PreparedSource:
    if source_override is not None:
        provenance = _validate_local_source(source_override, materializer)
        return PreparedSource(path=Path(source_override).expanduser().resolve(), provenance=provenance)

    failures: list[str] = []
    for acquisition in materializer["acquisition"]:
        if acquisition["type"] == "git":
            try:
                return _acquire_git_source(acquisition, materializer)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
                failures.append(f"git:{type(exc).__name__}")
                continue
        if acquisition["type"] == "user-local":
            failures.append("user-local:source required")
            continue
    rendered = ", ".join(failures) if failures else "no acquisition strategies"
    raise AcquisitionError(f"could not acquire materializer source ({rendered})")


def _render_args(
    args: list[str],
    *,
    source: str,
    output: str,
    source_revision: str,
) -> list[str]:
    return [
        item.format(source=source, output=output, source_revision=source_revision)
        for item in args
    ]


def _sandbox_backend_preflight(sandbox: str) -> tuple[str, str | None]:
    if sandbox == "off":
        return "off", None
    if sandbox != "required":
        raise ValueError("sandbox must be 'required' or 'off'")

    system = platform.system()
    if system == "Linux":
        executable = shutil.which("bwrap")
        if executable is None:
            raise RuntimeError(
                "required materializer sandbox is unavailable: install bubblewrap (bwrap) or do not run the materializer"
            )
        return "bubblewrap", executable
    if system == "Darwin":
        executable = shutil.which("sandbox-exec")
        if executable is None:
            raise RuntimeError("required materializer sandbox is unavailable: sandbox-exec was not found")
        return "sandbox-exec", executable
    raise RuntimeError(f"required materializer sandbox is not implemented for {system or 'this platform'}")


def _linux_python_path() -> tuple[str, list[str]]:
    executable = Path(sys.executable).resolve()
    prefix = Path(sys.prefix).resolve()
    try:
        relative = executable.relative_to(prefix)
    except ValueError:
        return str(executable), []

    system_roots = tuple(Path(p) for p in ("/usr", "/bin", "/lib", "/lib64"))
    if any(prefix == root or root in prefix.parents for root in system_roots):
        return str(executable), []

    return str(PurePosixPath("/runtime") / PurePosixPath(relative.as_posix())), [
        "--ro-bind",
        str(prefix),
        "/runtime",
    ]


def _build_linux_sandbox(
    *,
    bwrap: str,
    plugin_root: Path,
    source: Path,
    output: Path,
    module: str,
    args: list[str],
    source_revision: str,
) -> list[str]:
    python_inside, runtime_bind = _linux_python_path()
    sandbox_output = str(PurePosixPath(SANDBOX_OUTPUT_ROOT) / output.name)
    command = [
        bwrap,
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
    ]
    for system_path in ("/usr", "/bin", "/lib", "/lib64", "/etc"):
        if Path(system_path).exists():
            command.extend(["--ro-bind", system_path, system_path])
    command.extend(runtime_bind)
    if runtime_bind:
        command.extend(["--setenv", "LD_LIBRARY_PATH", "/runtime/lib"])
    command.extend(
        [
            "--ro-bind",
            str(plugin_root),
            "/plugin",
            "--ro-bind",
            str(source),
            "/input",
            "--bind",
            str(output.parent),
            SANDBOX_OUTPUT_ROOT,
            "--setenv",
            "HOME",
            "/tmp/home",
            "--setenv",
            "TMPDIR",
            "/tmp",
            "--setenv",
            "PYTHONPATH",
            "/plugin/src:/plugin",
            "--setenv",
            "PYTHONUTF8",
            "1",
            "--setenv",
            "PYTHONDONTWRITEBYTECODE",
            "1",
            "--chdir",
            "/tmp",
            python_inside,
            "-m",
            module,
            *_render_args(
                args,
                source="/input",
                output=sandbox_output,
                source_revision=source_revision,
            ),
        ]
    )
    return command


def _sandbox_profile_path(path: Path) -> str:
    return json.dumps(str(path.resolve()))


def _build_macos_sandbox(
    *,
    sandbox_exec: str,
    plugin_root: Path,
    source: Path,
    output: Path,
    work_dir: Path,
    module: str,
    args: list[str],
    source_revision: str,
) -> list[str]:
    output_parent = output.parent.resolve()
    readable = {
        Path("/System"),
        Path("/usr"),
        Path("/bin"),
        Path("/sbin"),
        Path("/Library"),
        Path(sys.prefix).resolve(),
        Path(sys.base_prefix).resolve(),
        plugin_root.resolve(),
        source.resolve(),
        output_parent,
        work_dir.resolve(),
    }
    read_rules = "\n".join(
        f"(allow file-read* (subpath {_sandbox_profile_path(path)}))"
        for path in sorted(readable, key=str)
        if path.exists()
    )
    profile = f"""(version 1)
(deny default)
(allow process*)
(allow sysctl-read)
(allow mach-lookup)
(allow file-read-metadata)
(allow file-read-data (literal \"/\"))
{read_rules}
(allow file-read* file-write* (subpath \"/dev\"))
(allow file-write* (subpath {_sandbox_profile_path(output_parent)}))
(allow file-write* (subpath {_sandbox_profile_path(work_dir)}))
(deny network*)
"""
    profile_path = work_dir / "materializer.sb"
    profile_path.write_text(profile, encoding="utf-8")
    return [
        sandbox_exec,
        "-f",
        str(profile_path),
        sys.executable,
        "-m",
        module,
        *_render_args(
            args,
            source=str(source),
            output=str(output),
            source_revision=source_revision,
        ),
    ]


def build_sandbox_command(
    *,
    plugin_root: Path,
    source: Path,
    output: Path,
    work_dir: Path,
    module: str,
    args: list[str],
    source_revision: str = "",
) -> tuple[list[str], str]:
    plugin_root = Path(plugin_root).resolve()
    source = Path(source).resolve()
    output = Path(output).resolve()
    work_dir = Path(work_dir).resolve()
    backend, executable = _sandbox_backend_preflight("required")

    if backend == "bubblewrap":
        assert executable is not None
        return (
            _build_linux_sandbox(
                bwrap=executable,
                plugin_root=plugin_root,
                source=source,
                output=output,
                module=module,
                args=args,
                source_revision=source_revision,
            ),
            backend,
        )
    if backend == "sandbox-exec":
        assert executable is not None
        return (
            _build_macos_sandbox(
                sandbox_exec=executable,
                plugin_root=plugin_root,
                source=source,
                output=output,
                work_dir=work_dir,
                module=module,
                args=args,
                source_revision=source_revision,
            ),
            backend,
        )
    raise AssertionError(f"unexpected sandbox backend {backend}")


def _preflight_output(path: Path) -> Path:
    requested = Path(path).expanduser()
    if requested.is_symlink():
        raise ValueError("materializer output path must not be a symlink")

    parent = requested.parent if requested.parent != Path("") else Path(".")
    parent.mkdir(parents=True, exist_ok=True)
    parent = parent.resolve()
    final = parent / requested.name

    if final.is_symlink():
        raise ValueError("materializer output path must not be a symlink")
    if final.exists():
        if not final.is_dir():
            raise ValueError(f"materializer output is not a directory: {final}")
        if any(final.iterdir()):
            raise ValueError(f"materializer output directory must be empty: {final}")
    return final


def _create_staging_output(final: Path) -> StagingOutput:
    root = Path(
        tempfile.mkdtemp(prefix=f".{final.name}.agora-stage-", dir=final.parent)
    ).resolve()
    output = root / "output"
    output.mkdir(mode=0o700)
    return StagingOutput(root=root, output=output)


def _validate_staging_output(staging: StagingOutput) -> None:
    if staging.output.is_symlink() or not staging.output.is_dir():
        raise ValueError("materializer replaced Agora's designated output directory")
    if staging.output.parent.resolve() != staging.root:
        raise ValueError("materializer output directory escaped Agora's private staging workspace")


def validate_output(path: Path, materializer: dict[str, Any]) -> None:
    root = Path(path).resolve()
    for relative in materializer["output"]["required_paths"]:
        candidate = (root / relative).resolve()
        if root not in candidate.parents and candidate != root:
            raise ValueError(f"declared output path escaped output root: {relative}")
        if not candidate.exists():
            raise ValueError(f"materializer did not produce required output path: {relative}")


def _runtime_environment(*, plugin_root: Path, work_dir: Path) -> dict[str, str]:
    path = os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
    python_path = os.pathsep.join((str(plugin_root / "src"), str(plugin_root)))
    return {
        "PATH": path,
        "HOME": str(work_dir / "home"),
        "TMPDIR": str(work_dir / "tmp"),
        "PYTHONPATH": python_path,
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def _write_provenance(path: Path, data: dict[str, Any]) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise ValueError(
            "materializer produced the reserved provenance path 'agora-materialization.json'"
        ) from exc
    except OSError as exc:
        if path.is_symlink():
            raise ValueError(
                "materializer produced the reserved provenance path 'agora-materialization.json'"
            ) from exc
        raise

    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def materialize(
    *,
    manifest_path: Path,
    materializer_id: str,
    output: Path,
    source: Path | None = None,
    sandbox: str = "required",
) -> Path:
    manifest_path = Path(manifest_path).resolve()
    manifest = load_manifest(manifest_path)
    spec = select_materializer(manifest, materializer_id)
    plugin_root = manifest_path.parent

    # Fail before acquisition/network side effects when the destination or sandbox is unusable.
    final_output = _preflight_output(output)
    preflight_backend, _ = _sandbox_backend_preflight(sandbox)
    code_sha256 = _materializer_code_digest(plugin_root)

    prepared: PreparedSource | None = None
    work_dir: Path | None = None
    staging: StagingOutput | None = None
    try:
        prepared = acquire_source(spec, source_override=source)
        staging = _create_staging_output(final_output)
        work_dir = Path(tempfile.mkdtemp(prefix="agora-materializer-"))
        (work_dir / "home").mkdir()
        (work_dir / "tmp").mkdir()

        execution = spec["execution"]
        source_revision = str(prepared.provenance.get("resolved_commit", ""))
        if sandbox == "required":
            command, sandbox_backend = build_sandbox_command(
                plugin_root=plugin_root,
                source=prepared.path,
                output=staging.output,
                work_dir=work_dir,
                module=execution["module"],
                args=execution["args"],
                source_revision=source_revision,
            )
        else:
            command = [
                sys.executable,
                "-m",
                execution["module"],
                *_render_args(
                    execution["args"],
                    source=str(prepared.path),
                    output=str(staging.output),
                    source_revision=source_revision,
                ),
            ]
            sandbox_backend = preflight_backend

        subprocess.run(
            command,
            check=True,
            cwd=work_dir,
            env=_runtime_environment(plugin_root=plugin_root, work_dir=work_dir),
        )
        _validate_staging_output(staging)
        validate_output(staging.output, spec)

        provenance = {
            "schema_version": 1,
            "plugin": {
                "id": manifest["plugin"]["id"],
                "version": manifest["plugin"]["version"],
                "code_sha256": code_sha256,
            },
            "materializer": materializer_id,
            "source": prepared.provenance,
            "output": {"format": spec["output"]["format"]},
            "sandbox": sandbox_backend,
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_provenance(staging.output / "agora-materialization.json", provenance)

        os.replace(staging.output, final_output)
        staging.cleanup()
        staging = None
        return final_output
    finally:
        if prepared is not None:
            prepared.cleanup()
        if work_dir is not None:
            shutil.rmtree(work_dir, ignore_errors=True)
        if staging is not None:
            staging.cleanup()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Acquire source data and run an experimental Agora materializer. "
            "Supplying --manifest is the explicit trust decision in this prototype."
        )
    )
    parser.add_argument(
        "--manifest",
        required=True,
        type=Path,
        help="trusted plugin's agora.materializer.json (the path itself is the prototype trust decision)",
    )
    parser.add_argument(
        "--materializer",
        required=True,
        help="materializer id declared by the selected manifest",
    )
    parser.add_argument("--output", required=True, type=Path, help="local artifact output directory")
    parser.add_argument(
        "--source",
        type=Path,
        help="explicit local source directory; bypasses automatic acquisition",
    )
    parser.add_argument(
        "--sandbox",
        choices=("required", "off"),
        default="required",
        help="require the OS sandbox by default; 'off' is an explicit development/trust override",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    final = materialize(
        manifest_path=args.manifest,
        materializer_id=args.materializer,
        output=args.output,
        source=args.source,
        sandbox=args.sandbox,
    )
    print(final)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())