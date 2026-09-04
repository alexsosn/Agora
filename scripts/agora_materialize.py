from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "registry/schema/materializer-plugin.schema.json"
GIT_TIMEOUT_SECONDS = 120
_TREE_EXCLUDES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".venv",
    "venv",
}


class ManifestError(ValueError):
    pass


class AcquisitionError(RuntimeError):
    """Automatic acquisition failed for an environmental/network reason."""


@dataclass(frozen=True)
class PreparedSource:
    path: Path
    provenance: dict[str, Any]
    cleanup_root: Path | None = None

    def cleanup(self) -> None:
        if self.cleanup_root is not None:
            shutil.rmtree(self.cleanup_root, ignore_errors=True)


def _safe_relative(value: str, *, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{where} must be a non-empty relative path")
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise ManifestError(f"{where} must stay inside the declared source/output root")
    return value


def _format_schema_error(error: Any) -> str:
    location = error.json_path if getattr(error, "json_path", None) else "$"
    return f"{location}: {error.message}"


def _validate_manifest_semantics(doc: dict[str, Any]) -> None:
    ids: set[str] = set()
    for index, materializer in enumerate(doc["materializers"]):
        materializer_id = materializer["id"]
        if materializer_id in ids:
            raise ManifestError(f"duplicate materializer id {materializer_id!r}")
        ids.add(materializer_id)

        seen_types: set[str] = set()
        for ai, strategy in enumerate(materializer["acquisition"]):
            strategy_type = strategy["type"]
            if strategy_type in seen_types:
                raise ManifestError(
                    f"materializers[{index}].acquisition repeats strategy type {strategy_type!r}"
                )
            seen_types.add(strategy_type)

            if strategy_type == "git":
                parsed = urlparse(strategy["url"])
                if (
                    parsed.scheme != "https"
                    or not parsed.netloc
                    or parsed.username is not None
                    or parsed.password is not None
                ):
                    raise ManifestError(
                        f"materializers[{index}].acquisition[{ai}].url must be an absolute "
                        "credential-free HTTPS URL"
                    )
                if strategy["ref"].startswith("-"):
                    raise ManifestError(
                        f"materializers[{index}].acquisition[{ai}].ref must be a non-option Git ref"
                    )
                _safe_relative(
                    strategy["subpath"],
                    where=f"materializers[{index}].acquisition[{ai}].subpath",
                )

        for pattern in materializer["input"]["required_globs"]:
            _safe_relative(pattern, where=f"materializers[{index}].input.required_globs")
        for relative in materializer["output"]["required_paths"]:
            _safe_relative(relative, where=f"materializers[{index}].output.required_paths")


def load_manifest(path: Path) -> dict[str, Any]:
    path = Path(path)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot read materializer manifest {path}: {exc}") from exc

    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - repository corruption
        raise RuntimeError(f"cannot read Agora materializer schema {SCHEMA_PATH}: {exc}") from exc

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(doc), key=lambda item: item.json_path)
    if errors:
        raise ManifestError(f"materializer manifest violates schema: {_format_schema_error(errors[0])}")

    _validate_manifest_semantics(doc)
    return doc


def select_materializer(manifest: dict[str, Any], materializer_id: str) -> dict[str, Any]:
    for materializer in manifest["materializers"]:
        if materializer["id"] == materializer_id:
            return materializer
    available = ", ".join(item["id"] for item in manifest["materializers"])
    raise KeyError(f"unknown materializer {materializer_id!r}; available: {available}")


def _hash_tree(root: Path, *, excluded_names: set[str] | None = None) -> str:
    root = Path(root).resolve()
    excluded_names = excluded_names or set()
    digest = hashlib.sha256()

    candidates = sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix())
    for candidate in candidates:
        relative = candidate.relative_to(root)
        if any(part in excluded_names for part in relative.parts):
            continue
        rel = relative.as_posix().encode("utf-8")
        if candidate.is_symlink():
            digest.update(b"L\0" + rel + b"\0")
            digest.update(os.readlink(candidate).encode("utf-8", errors="surrogateescape"))
            digest.update(b"\0")
        elif candidate.is_dir():
            digest.update(b"D\0" + rel + b"\0")
        elif candidate.is_file():
            digest.update(b"F\0" + rel + b"\0")
            with candidate.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
            digest.update(b"\0")
    return digest.hexdigest()


def _materializer_code_digest(plugin_root: Path) -> str:
    plugin_root = Path(plugin_root).resolve()
    code_root = plugin_root / "src" if (plugin_root / "src").is_dir() else plugin_root
    return _hash_tree(code_root, excluded_names=_TREE_EXCLUDES)


def _validate_source(path: Path, materializer: dict[str, Any]) -> None:
    if not path.is_dir():
        raise ValueError(f"materializer source is not a directory: {path}")
    input_spec = materializer["input"]
    if not input_spec["allow_symlinks"]:
        for candidate in path.rglob("*"):
            if candidate.is_symlink():
                raise ValueError(f"materializer source contains a disallowed symlink: {candidate}")
    for pattern in input_spec["required_globs"]:
        if not any(path.glob(pattern)):
            raise ValueError(f"required input pattern {pattern!r} matched no files in {path}")


def _git_environment(home: Path) -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "true",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def _detect_local_git_revision(path: Path) -> str | None:
    git = shutil.which("git")
    if git is None:
        return None
    try:
        return subprocess.check_output(
            [git, "-C", str(path), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).strip() or None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None


def prepare_user_source(path: Path, materializer: dict[str, Any]) -> PreparedSource:
    resolved = Path(path).expanduser().resolve()
    _validate_source(resolved, materializer)
    provenance: dict[str, Any] = {
        "type": "user-local",
        "name": resolved.name,
        "tree_sha256": _hash_tree(resolved),
    }
    revision = _detect_local_git_revision(resolved)
    if revision is not None:
        provenance["resolved_commit"] = revision
    return PreparedSource(path=resolved, provenance=provenance)


def _run_git(command: list[str], *, env: dict[str, str], capture: bool = False) -> str | None:
    try:
        if capture:
            return subprocess.check_output(
                command,
                env=env,
                text=True,
                timeout=GIT_TIMEOUT_SECONDS,
            ).strip()
        subprocess.run(command, check=True, env=env, timeout=GIT_TIMEOUT_SECONDS)
        return None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        raise AcquisitionError(f"Git acquisition failed: {exc}") from exc


def acquire_git_source(strategy: dict[str, Any], materializer: dict[str, Any]) -> PreparedSource:
    git = shutil.which("git")
    if git is None:
        raise AcquisitionError("Git acquisition requested but git is not installed")

    root = Path(tempfile.mkdtemp(prefix="agora-source-"))
    repo = root / "repository"
    home = root / "home"
    home.mkdir()
    env = _git_environment(home)
    try:
        _run_git([git, "init", "--quiet", str(repo)], env=env)
        _run_git([git, "-C", str(repo), "remote", "add", "origin", strategy["url"]], env=env)
        _run_git(
            [git, "-C", str(repo), "fetch", "--quiet", "--depth", "1", "origin", strategy["ref"]],
            env=env,
        )
        _run_git([git, "-C", str(repo), "checkout", "--quiet", "--detach", "FETCH_HEAD"], env=env)
        revision = _run_git([git, "-C", str(repo), "rev-parse", "HEAD"], env=env, capture=True)
        assert revision is not None

        repo_root = repo.resolve()
        source = (repo / strategy["subpath"]).resolve()
        if repo_root not in source.parents and source != repo_root:
            raise ValueError("Git acquisition subpath escaped the repository")
        _validate_source(source, materializer)
        return PreparedSource(
            path=source,
            provenance={
                "type": "git",
                "url": strategy["url"],
                "requested_ref": strategy["ref"],
                "resolved_commit": revision,
                "subpath": strategy["subpath"],
            },
            cleanup_root=root,
        )
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise


def acquire_source(
    materializer: dict[str, Any],
    *,
    source_override: Path | None = None,
) -> PreparedSource:
    if source_override is not None:
        if not any(item["type"] == "user-local" for item in materializer["acquisition"]):
            raise ValueError("this materializer does not accept user-provided local source files")
        return prepare_user_source(source_override, materializer)

    git_errors: list[str] = []
    user_local: dict[str, Any] | None = None
    for strategy in materializer["acquisition"]:
        if strategy["type"] == "git":
            try:
                return acquire_git_source(strategy, materializer)
            except AcquisitionError as exc:
                git_errors.append(str(exc))
        elif strategy["type"] == "user-local":
            user_local = strategy

    if user_local is not None and sys.stdin.isatty():
        if git_errors:
            print(f"automatic acquisition failed: {'; '.join(git_errors)}", file=sys.stderr)
        entered = input(f"{user_local['prompt']}: ").strip()
        if not entered:
            raise RuntimeError("no local source directory was provided")
        return prepare_user_source(Path(entered), materializer)

    detail = f" Automatic acquisition errors: {'; '.join(git_errors)}" if git_errors else ""
    raise RuntimeError(
        "no source could be acquired non-interactively; pass --source with a user-provided directory."
        + detail
    )


def _render_args(
    args: list[str],
    *,
    source: str,
    output: str,
    source_revision: str = "",
) -> list[str]:
    values = {
        "{source}": source,
        "{output}": output,
        "{source_revision}": source_revision,
    }
    rendered: list[str] = []
    for arg in args:
        value = arg
        for placeholder, replacement in values.items():
            value = value.replace(placeholder, replacement)
        if "{" in value or "}" in value:
            raise ManifestError(f"unresolved or invalid execution placeholder in {arg!r}")
        rendered.append(value)
    return rendered


def _sandbox_backend_preflight(sandbox: str) -> tuple[str, str | None]:
    if sandbox == "off":
        return "none-explicit", None
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
            str(output),
            "/output",
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
                output="/output",
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
        output.resolve(),
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
(allow file-write* (subpath {_sandbox_profile_path(output)}))
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


def _create_staging_output(final: Path) -> Path:
    return Path(tempfile.mkdtemp(prefix=f".{final.name}.agora-stage-", dir=final.parent)).resolve()


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
    staging_output: Path | None = None
    try:
        prepared = acquire_source(spec, source_override=source)
        staging_output = _create_staging_output(final_output)
        work_dir = Path(tempfile.mkdtemp(prefix="agora-materializer-"))
        (work_dir / "home").mkdir()
        (work_dir / "tmp").mkdir()

        execution = spec["execution"]
        source_revision = str(prepared.provenance.get("resolved_commit", ""))
        if sandbox == "required":
            command, sandbox_backend = build_sandbox_command(
                plugin_root=plugin_root,
                source=prepared.path,
                output=staging_output,
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
                    output=str(staging_output),
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
        validate_output(staging_output, spec)

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
        _write_provenance(staging_output / "agora-materialization.json", provenance)

        os.replace(staging_output, final_output)
        staging_output = None
        return final_output
    finally:
        if prepared is not None:
            prepared.cleanup()
        if work_dir is not None:
            shutil.rmtree(work_dir, ignore_errors=True)
        if staging_output is not None:
            shutil.rmtree(staging_output, ignore_errors=True)


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
        help="materializer id declared by the trusted plugin",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="absent or empty final directory for the derived local artifact",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="user-provided local source directory; otherwise Agora tries declared automatic acquisition",
    )
    parser.add_argument(
        "--sandbox",
        choices=("required", "off"),
        default="required",
        help="require an OS sandbox (default); 'off' is an explicit development-only trust override",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = materialize(
        manifest_path=args.manifest,
        materializer_id=args.materializer,
        output=args.output,
        source=args.source,
        sandbox=args.sandbox,
    )
    print(result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
