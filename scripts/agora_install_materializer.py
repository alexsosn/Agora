#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.agora_materialize import load_manifest

REGISTRY_PATH = ROOT / "registry/materializers.yaml"
SCHEMA_PATH = ROOT / "registry/schema/materializers.schema.json"
SOURCE_RECEIPT = "agora-source.json"
INSTALLATION_RECEIPT = "agora-installation.json"
ENVIRONMENT_MARKER = ".agora-environment.json"
PIP_REPORT = "pip-report.json"
GIT_TIMEOUT_SECONDS = 120
PIP_TIMEOUT_SECONDS = 600
RUNTIME_TREE_EXCLUDES = {
    ".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".nox", ".venv", "venv",
}


class MaterializerRegistryError(ValueError):
    pass


class MaterializerInstallError(RuntimeError):
    pass


def _json_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _tree_hash(root: Path, *, excludes: set[str] | None = None) -> str:
    root = Path(root).resolve()
    excludes = excludes or set()
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        rel = path.relative_to(root)
        if any(part in excludes for part in rel.parts):
            continue
        name = rel.as_posix().encode()
        if path.is_symlink():
            digest.update(b"L\0" + name + b"\0" + os.readlink(path).encode() + b"\0")
        elif path.is_dir():
            digest.update(b"D\0" + name + b"\0")
        elif path.is_file():
            digest.update(b"F\0" + name + b"\0")
            with path.open("rb") as fh:
                while chunk := fh.read(1024 * 1024):
                    digest.update(chunk)
            digest.update(b"\0")
    return digest.hexdigest()


def _contained(root: Path, relative: str, label: str) -> Path:
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if path != root and root not in path.parents:
        raise MaterializerInstallError(f"{label} escapes its declared root")
    return path


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    try:
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MaterializerRegistryError(str(exc)) from exc
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(doc),
        key=lambda e: e.json_path,
    )
    if errors:
        raise MaterializerRegistryError(
            f"materializer registry violates schema at {errors[0].json_path}: {errors[0].message}"
        )
    ids = [item["id"] for item in doc["plugins"]]
    if len(ids) != len(set(ids)):
        raise MaterializerRegistryError("duplicate materializer plugin id")
    return doc


def select_plugin(doc: dict[str, Any], plugin_id: str) -> dict[str, Any]:
    for plugin in doc["plugins"]:
        if plugin["id"] == plugin_id:
            return plugin
    raise KeyError(f"unknown materializer plugin {plugin_id!r}")


def default_install_root() -> Path:
    if value := os.environ.get("AGORA_DATA_HOME"):
        base = Path(value).expanduser()
    elif value := os.environ.get("XDG_DATA_HOME"):
        base = Path(value).expanduser()
    else:
        base = Path.home() / ".local" / "share"
    return base / "agora" / "materializers"


def commit_root(plugin: dict[str, Any], root: Path) -> Path:
    return Path(root).expanduser() / plugin["id"] / plugin["ref"]


def runtime_identity() -> dict[str, str]:
    cache_tag = sys.implementation.cache_tag or "unknown"
    return {
        "implementation": sys.implementation.name,
        "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "cache_tag": cache_tag,
        "abi": str(sysconfig.get_config_var("SOABI") or cache_tag),
        "platform": sysconfig.get_platform(),
        "system": platform.system() or "unknown",
        "machine": platform.machine() or "unknown",
    }


def runtime_tag(identity: dict[str, str] | None = None) -> str:
    i = identity or runtime_identity()
    raw = "-".join((i["implementation"], i["version"], i["abi"], i["platform"]))
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw)


def installation_path(plugin: dict[str, Any], root: Path) -> Path:
    return commit_root(plugin, root) / "environments" / runtime_tag()


@contextmanager
def _lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise MaterializerInstallError(f"another materializer operation is in progress: {path}") from exc
    try:
        os.close(fd)
        yield
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(value, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _git_env(home: Path) -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "true",
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
    }


def _git(command: list[str], env: dict[str, str], *, capture: bool = False) -> str | None:
    try:
        if capture:
            return subprocess.check_output(
                command, env=env, text=True, stderr=subprocess.STDOUT, timeout=GIT_TIMEOUT_SECONDS
            ).strip()
        subprocess.run(
            command, env=env, check=True, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, text=True, timeout=GIT_TIMEOUT_SECONDS,
        )
        return None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        detail = getattr(exc, "stderr", None) or getattr(exc, "output", None) or str(exc)
        raise MaterializerInstallError(f"Git fetch failed: {str(detail).strip()}") from exc


def _checkout(plugin: dict[str, Any], destination: Path) -> str:
    git = shutil.which("git")
    if git is None:
        raise MaterializerInstallError("git is required")
    home = destination.parent / f".{destination.name}.git-home"
    home.mkdir()
    env = _git_env(home)
    try:
        _git([git, "init", "--quiet", str(destination)], env)
        _git([git, "-C", str(destination), "remote", "add", "origin",
              f"https://github.com/{plugin['repository']}.git"], env)
        _git([git, "-C", str(destination), "fetch", "--quiet", "--depth", "1",
              "origin", plugin["ref"]], env)
        _git([git, "-C", str(destination), "checkout", "--quiet", "--detach", "FETCH_HEAD"], env)
        resolved = _git([git, "-C", str(destination), "rev-parse", "HEAD"], env, capture=True)
        if resolved != plugin["ref"]:
            raise MaterializerInstallError(
                f"downloaded commit {resolved} does not match registered commit {plugin['ref']}"
            )
        shutil.rmtree(destination / ".git", ignore_errors=True)
        return str(resolved)
    finally:
        shutil.rmtree(home, ignore_errors=True)


def _validate_binding(plugin: dict[str, Any], root: Path) -> dict[str, Any]:
    path = _contained(root, plugin["manifest"], "registered manifest")
    if not path.is_file():
        raise MaterializerInstallError(f"registered manifest {plugin['manifest']!r} is missing")
    manifest = load_manifest(path)
    declared = manifest["plugin"]
    for field in ("id", "name", "version", "repository"):
        if declared.get(field) != plugin[field]:
            raise MaterializerInstallError(
                f"manifest plugin.{field}={declared.get(field)!r} does not match registry {plugin[field]!r}"
            )
    ids = [item["id"] for item in manifest["materializers"]]
    if ids != plugin["materializers"]:
        raise MaterializerInstallError("manifest materializer ids do not match registry")
    return manifest


def _source_current(plugin: dict[str, Any], base: Path) -> bool:
    source, receipt_path = base / "source", base / SOURCE_RECEIPT
    if not source.is_dir() or not receipt_path.is_file():
        return False
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        manifest = _contained(source, plugin["manifest"], "source manifest")
        return (
            receipt["plugin"]["id"] == plugin["id"]
            and receipt["plugin"]["commit"] == plugin["ref"]
            and receipt["manifest"]["sha256"] == _file_hash(manifest)
            and receipt["source"]["tree_sha256"] == _tree_hash(source)
            and receipt["materializers"] == plugin["materializers"]
        )
    except (KeyError, OSError, ValueError, json.JSONDecodeError):
        return False


def fetch_materializer(
    plugin_id: str, *, install_root: Path | None = None,
    registry_path: Path = REGISTRY_PATH, repair: bool = False,
) -> Path:
    plugin = select_plugin(load_registry(registry_path), plugin_id)
    root = Path(install_root) if install_root is not None else default_install_root()
    base = commit_root(plugin, root)
    base.mkdir(parents=True, exist_ok=True)
    source = base / "source"
    with _lock(base / ".source.lock"):
        if source.exists() and _source_current(plugin, base):
            return source.resolve()
        if source.exists() and not repair:
            raise MaterializerInstallError(f"fetched source integrity failed: {source}; use --repair")
        staging = Path(tempfile.mkdtemp(prefix=".source.fetch-", dir=base))
        try:
            _checkout(plugin, staging)
            _validate_binding(plugin, staging)
            receipt = {
                "schema_version": 1,
                "plugin": {"id": plugin["id"], "version": plugin["version"],
                           "repository": plugin["repository"], "commit": plugin["ref"]},
                "manifest": {"path": plugin["manifest"],
                             "sha256": _file_hash(staging / plugin["manifest"])},
                "source": {"tree_sha256": _tree_hash(staging)},
                "materializers": list(plugin["materializers"]),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            if source.exists():
                shutil.rmtree(source)
            os.replace(staging, source)
            staging = None
            _write_json(base / SOURCE_RECEIPT, receipt)
            return source.resolve()
        finally:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)


def _install_python(plugin: dict[str, Any], source: Path, runtime: Path, report: Path) -> None:
    package = _contained(source, plugin["package"]["path"], "registered Python project")
    if not (package / "pyproject.toml").is_file():
        raise MaterializerInstallError("registered Python project has no pyproject.toml")
    env = os.environ.copy()
    env.update({"PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_INPUT": "1",
                "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-input", "--disable-pip-version-check",
             "--no-compile", "--report", str(report), "--target", str(runtime), str(package)],
            check=True, env=env, timeout=PIP_TIMEOUT_SECONDS,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        raise MaterializerInstallError(f"Python package installation failed: {exc}") from exc


def _module_exists(root: Path, module: str) -> bool:
    current = root
    parts = module.split(".")
    for index, part in enumerate(parts):
        if index == len(parts) - 1 and (current / f"{part}.py").is_file():
            return True
        if not (current / part).is_dir():
            return False
        current /= part
    return current.is_dir() and (current / "__init__.py").is_file()


def _verify_execution_modules_static(manifest: dict[str, Any], runtime: Path) -> None:
    for materializer in manifest["materializers"]:
        module = materializer["execution"]["module"]
        if not _module_exists(runtime, module):
            raise MaterializerInstallError(f"installed materializer module {module!r} is absent")


def _distributions(runtime: Path) -> list[dict[str, str]]:
    rows = []
    for dist in importlib.metadata.distributions(path=[str(runtime)]):
        rows.append({"name": str(dist.metadata.get("Name") or dist.name), "version": str(dist.version)})
    return sorted(rows, key=lambda row: (row["name"].lower(), row["version"]))


def _environment_current(plugin: dict[str, Any], target: Path) -> bool:
    receipt_path, runtime = target / INSTALLATION_RECEIPT, target / "runtime"
    if not receipt_path.is_file() or not runtime.is_dir():
        return False
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        marker = json.loads((runtime / ENVIRONMENT_MARKER).read_text(encoding="utf-8"))
        source = target.parent.parent / "source"
        distributions = _distributions(runtime)
        env_hash = _tree_hash(runtime, excludes=RUNTIME_TREE_EXCLUDES)
        source_hash = _tree_hash(source)
        return (
            receipt.get("schema_version") == 2
            and receipt["plugin"]["id"] == plugin["id"]
            and receipt["plugin"]["commit"] == plugin["ref"]
            and receipt["runtime"] == runtime_identity()
            and receipt["source"]["tree_sha256"] == source_hash
            and receipt["environment"]["tree_sha256"] == env_hash
            and receipt["environment"]["distributions"] == distributions
            and receipt["environment"]["descriptor_sha256"]
                == _json_hash({"runtime": runtime_identity(), "distributions": distributions})
            and receipt["environment"]["pip_report_sha256"] == _file_hash(target / PIP_REPORT)
            and receipt["environment"]["install_trust"] == "explicit-code-execution"
            and receipt["manifest"]["source_sha256"] == _file_hash(source / plugin["manifest"])
            and receipt["manifest"]["execution_sha256"] == _file_hash(runtime / plugin["manifest"])
            and marker["managed"] is True
            and marker["runtime"] == runtime_identity()
            and marker["distributions"] == distributions
            and marker["source_tree_sha256"] == source_hash
            and receipt["execution_identity_sha256"]
                == _json_hash({"source_tree_sha256": source_hash,
                               "environment_tree_sha256": env_hash,
                               "runtime": runtime_identity()})
        )
    except (KeyError, OSError, ValueError, json.JSONDecodeError):
        return False


def install_materializer(
    plugin_id: str, *, install_root: Path | None = None,
    registry_path: Path = REGISTRY_PATH, approve_code_execution: bool = False,
    repair: bool = False,
) -> Path:
    if not approve_code_execution:
        raise MaterializerInstallError(
            "Python installation executes third-party PEP 517/build code; pass --approve-code-execution"
        )
    plugin = select_plugin(load_registry(registry_path), plugin_id)
    if plugin["package"].get("install_trust") != "explicit-code-execution":
        raise MaterializerInstallError("registry lacks explicit install-time trust metadata")
    root = Path(install_root) if install_root is not None else default_install_root()
    source = fetch_materializer(plugin_id, install_root=root, registry_path=registry_path, repair=repair)
    target = installation_path(plugin, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    with _lock(target.parent / f".{target.name}.lock"):
        if target.exists() and _environment_current(plugin, target):
            return target.resolve()
        if target.exists() and not repair:
            raise MaterializerInstallError(f"installed environment integrity failed: {target}; use --repair")

        source_hash = _tree_hash(source)
        manifest = _validate_binding(plugin, source)
        staging = Path(tempfile.mkdtemp(prefix=".environment.install-", dir=target.parent))
        build = Path(tempfile.mkdtemp(prefix="agora-materializer-build-"))
        try:
            build_source = build / "source"
            shutil.copytree(source, build_source)
            runtime = staging / "runtime"
            runtime.mkdir()
            _install_python(plugin, build_source, runtime, staging / PIP_REPORT)
            if _tree_hash(source) != source_hash:
                raise MaterializerInstallError("installation mutated immutable fetched source")
            _validate_binding(plugin, source)
            if (runtime / "src").exists():
                raise MaterializerInstallError("managed runtime reserves top-level 'src'")
            shutil.copy2(source / plugin["manifest"], runtime / plugin["manifest"])
            distributions = _distributions(runtime)
            rt = runtime_identity()
            descriptor = _json_hash({"runtime": rt, "distributions": distributions})
            marker = {
                "schema_version": 1, "managed": True, "runtime": rt,
                "distributions": distributions, "descriptor_sha256": descriptor,
                "source_tree_sha256": source_hash,
                "manifest_sha256": _file_hash(source / plugin["manifest"]),
            }
            _write_json(runtime / ENVIRONMENT_MARKER, marker)
            _verify_execution_modules_static(manifest, runtime)
            env_hash = _tree_hash(runtime, excludes=RUNTIME_TREE_EXCLUDES)
            receipt = {
                "schema_version": 2,
                "plugin": {"id": plugin["id"], "version": plugin["version"],
                           "repository": plugin["repository"], "commit": plugin["ref"]},
                "manifest": {"source_path": plugin["manifest"],
                             "source_sha256": _file_hash(source / plugin["manifest"]),
                             "execution_path": f"runtime/{plugin['manifest']}",
                             "execution_sha256": _file_hash(runtime / plugin["manifest"])},
                "source": {"path": "../../source", "tree_sha256": source_hash},
                "materializers": list(plugin["materializers"]), "runtime": rt,
                "environment": {"runtime_root": "runtime", "tree_sha256": env_hash,
                                "distributions": distributions, "descriptor_sha256": descriptor,
                                "pip_report_sha256": _file_hash(staging / PIP_REPORT),
                                "install_trust": "explicit-code-execution"},
                "execution_identity_sha256": _json_hash({
                    "source_tree_sha256": source_hash, "environment_tree_sha256": env_hash,
                    "runtime": rt,
                }),
                "installed_at": datetime.now(timezone.utc).isoformat(),
            }
            _write_json(staging / INSTALLATION_RECEIPT, receipt)
            if target.exists():
                backup = target.parent / f".{target.name}.backup-{os.getpid()}"
                os.replace(target, backup)
                try:
                    os.replace(staging, target)
                except Exception:
                    os.replace(backup, target)
                    raise
                shutil.rmtree(backup, ignore_errors=True)
            else:
                os.replace(staging, target)
            staging = None
            return target.resolve()
        finally:
            shutil.rmtree(build, ignore_errors=True)
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover, passively fetch, and explicitly install Agora materializers."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    fetch = commands.add_parser("fetch", help="download/validate source without executing plugin Python")
    fetch.add_argument("plugin_id"); fetch.add_argument("--root", type=Path); fetch.add_argument("--repair", action="store_true")
    install = commands.add_parser("install", help="install after explicit third-party code approval")
    install.add_argument("plugin_id"); install.add_argument("--root", type=Path)
    install.add_argument("--approve-code-execution", action="store_true")
    install.add_argument("--repair", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "list":
        for plugin in load_registry()["plugins"]:
            print(f"{plugin['id']}\t{plugin['version']}\t{','.join(plugin['materializers'])}\t{plugin['description']}")
        return 0
    if args.command == "fetch":
        print(fetch_materializer(args.plugin_id, install_root=args.root, repair=args.repair))
        return 0
    target = install_materializer(
        args.plugin_id, install_root=args.root, approve_code_execution=args.approve_code_execution,
        repair=args.repair,
    )
    plugin = select_plugin(load_registry(), args.plugin_id)
    print(f"Installed environment: {target}")
    print(f"Materializer manifest: {target / 'runtime' / plugin['manifest']}")
    print(f"Installation receipt: {target / INSTALLATION_RECEIPT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
