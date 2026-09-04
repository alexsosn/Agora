#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agora_materialize import load_manifest

REGISTRY_PATH = ROOT / "registry/materializers.yaml"
SCHEMA_PATH = ROOT / "registry/schema/materializers.schema.json"
INSTALLATION_RECEIPT = "agora-installation.json"
GIT_TIMEOUT_SECONDS = 120
PIP_TIMEOUT_SECONDS = 600


class MaterializerRegistryError(ValueError):
    pass


class MaterializerInstallError(RuntimeError):
    pass


def _load_yaml(path: Path) -> Any:
    try:
        with Path(path).open("r", encoding="utf-8") as stream:
            return yaml.safe_load(stream)
    except OSError as exc:
        raise MaterializerRegistryError(f"cannot read materializer registry {path}: {exc}") from exc


def _load_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MaterializerRegistryError(f"cannot read JSON {path}: {exc}") from exc


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    document = _load_yaml(path)
    schema = _load_json(SCHEMA_PATH)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda error: error.json_path)
    if errors:
        error = errors[0]
        location = error.json_path if getattr(error, "json_path", None) else "$"
        raise MaterializerRegistryError(
            f"materializer registry violates schema at {location}: {error.message}"
        )

    seen: set[str] = set()
    for plugin in document["plugins"]:
        plugin_id = plugin["id"]
        if plugin_id in seen:
            raise MaterializerRegistryError(f"duplicate materializer plugin id {plugin_id!r}")
        seen.add(plugin_id)
    return document


def select_plugin(document: dict[str, Any], plugin_id: str) -> dict[str, Any]:
    for plugin in document["plugins"]:
        if plugin["id"] == plugin_id:
            return plugin
    available = ", ".join(plugin["id"] for plugin in document["plugins"])
    raise KeyError(f"unknown materializer plugin {plugin_id!r}; available: {available}")


def default_install_root() -> Path:
    override = os.environ.get("AGORA_DATA_HOME")
    if override:
        base = Path(override).expanduser()
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return base / "agora" / "materializers"


def installation_path(plugin: dict[str, Any], install_root: Path) -> Path:
    return Path(install_root).expanduser() / plugin["id"] / plugin["ref"]


def _hash_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _contained_path(root: Path, relative: str, *, label: str) -> Path:
    root = Path(root).resolve()
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise MaterializerInstallError(f"{label} escapes the installed plugin root")
    return candidate


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


def _run_git(command: list[str], *, env: dict[str, str], capture: bool = False) -> str | None:
    try:
        if capture:
            return subprocess.check_output(
                command,
                env=env,
                text=True,
                stderr=subprocess.STDOUT,
                timeout=GIT_TIMEOUT_SECONDS,
            ).strip()
        subprocess.run(
            command,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
        return None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        detail = getattr(exc, "stderr", None) or getattr(exc, "output", None) or str(exc)
        raise MaterializerInstallError(f"Git download failed: {str(detail).strip()}") from exc


def _checkout_repository(plugin: dict[str, Any], destination: Path) -> str:
    git = shutil.which("git")
    if git is None:
        raise MaterializerInstallError("git is required to install a registered materializer plugin")

    destination = Path(destination)
    home = destination.parent / f".{destination.name}.git-home"
    home.mkdir()
    env = _git_environment(home)
    repository_url = f"https://github.com/{plugin['repository']}.git"
    try:
        _run_git([git, "init", "--quiet", str(destination)], env=env)
        _run_git([git, "-C", str(destination), "remote", "add", "origin", repository_url], env=env)
        _run_git(
            [
                git,
                "-C",
                str(destination),
                "fetch",
                "--quiet",
                "--depth",
                "1",
                "origin",
                plugin["ref"],
            ],
            env=env,
        )
        _run_git(
            [git, "-C", str(destination), "checkout", "--quiet", "--detach", "FETCH_HEAD"],
            env=env,
        )
        resolved = _run_git(
            [git, "-C", str(destination), "rev-parse", "HEAD"], env=env, capture=True
        )
        assert resolved is not None
        if resolved != plugin["ref"]:
            raise MaterializerInstallError(
                f"registered ref resolved to {resolved}, expected immutable commit {plugin['ref']}"
            )
        shutil.rmtree(destination / ".git", ignore_errors=True)
        return resolved
    finally:
        shutil.rmtree(home, ignore_errors=True)


def _validate_manifest_binding(plugin: dict[str, Any], plugin_root: Path) -> dict[str, Any]:
    manifest_path = _contained_path(
        plugin_root, plugin["manifest"], label="registered materializer manifest"
    )
    if not manifest_path.is_file():
        raise MaterializerInstallError(
            f"registered manifest {plugin['manifest']!r} is missing from {plugin['repository']}@{plugin['ref']}"
        )

    manifest = load_manifest(manifest_path)
    declared = manifest["plugin"]
    checks = {
        "id": plugin["id"],
        "name": plugin["name"],
        "version": plugin["version"],
        "repository": plugin["repository"],
    }
    for field, expected in checks.items():
        if declared.get(field) != expected:
            raise MaterializerInstallError(
                f"installed manifest plugin.{field}={declared.get(field)!r} does not match registry value {expected!r}"
            )

    declared_ids = [materializer["id"] for materializer in manifest["materializers"]]
    if declared_ids != plugin["materializers"]:
        raise MaterializerInstallError(
            "installed manifest materializer ids do not match the canonical registry: "
            f"{declared_ids!r} != {plugin['materializers']!r}"
        )
    return manifest


def _install_python_project(plugin: dict[str, Any], plugin_root: Path) -> None:
    package_path = _contained_path(
        plugin_root, plugin["package"]["path"], label="registered Python project"
    )
    if not (package_path / "pyproject.toml").is_file():
        raise MaterializerInstallError(
            f"registered Python project {plugin['package']['path']!r} has no pyproject.toml"
        )

    env = os.environ.copy()
    env.update(
        {
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INPUT": "1",
            "PYTHONNOUSERSITE": "1",
        }
    )
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-input",
        "--disable-pip-version-check",
        "--target",
        str(plugin_root),
        str(package_path),
    ]
    try:
        subprocess.run(command, check=True, env=env, timeout=PIP_TIMEOUT_SECONDS)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        raise MaterializerInstallError(f"Python package installation failed: {exc}") from exc


def _verify_execution_modules(manifest: dict[str, Any], plugin_root: Path) -> None:
    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        (str(plugin_root / "src"), str(plugin_root))
    )
    probe = (
        "import importlib.util, sys; "
        "raise SystemExit(0 if importlib.util.find_spec(sys.argv[1]) is not None else 1)"
    )
    for materializer in manifest["materializers"]:
        module = materializer["execution"]["module"]
        try:
            subprocess.run(
                [sys.executable, "-c", probe, module],
                check=True,
                env=env,
                timeout=30,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            detail = getattr(exc, "stderr", None) or str(exc)
            raise MaterializerInstallError(
                f"installed materializer module {module!r} is not importable: {str(detail).strip()}"
            ) from exc


def _receipt_for(plugin: dict[str, Any], plugin_root: Path) -> dict[str, Any]:
    manifest_path = _contained_path(
        plugin_root, plugin["manifest"], label="registered materializer manifest"
    )
    return {
        "schema_version": 1,
        "plugin": {
            "id": plugin["id"],
            "name": plugin["name"],
            "version": plugin["version"],
            "repository": plugin["repository"],
            "commit": plugin["ref"],
        },
        "manifest": {
            "path": plugin["manifest"],
            "sha256": _hash_file(manifest_path),
        },
        "materializers": list(plugin["materializers"]),
        "installed_at": datetime.now(timezone.utc).isoformat(),
    }


def _existing_installation_is_current(plugin: dict[str, Any], target: Path) -> bool:
    receipt_path = Path(target) / INSTALLATION_RECEIPT
    if not receipt_path.is_file():
        return False
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        manifest_path = _contained_path(
            target, plugin["manifest"], label="installed materializer manifest"
        )
        return (
            receipt["plugin"]["id"] == plugin["id"]
            and receipt["plugin"]["repository"] == plugin["repository"]
            and receipt["plugin"]["commit"] == plugin["ref"]
            and receipt["plugin"]["version"] == plugin["version"]
            and receipt["manifest"]["path"] == plugin["manifest"]
            and receipt["manifest"]["sha256"] == _hash_file(manifest_path)
            and receipt["materializers"] == plugin["materializers"]
        )
    except (KeyError, OSError, ValueError, json.JSONDecodeError):
        return False


def install_materializer(
    plugin_id: str,
    *,
    install_root: Path | None = None,
    registry_path: Path = REGISTRY_PATH,
) -> Path:
    document = load_registry(registry_path)
    plugin = select_plugin(document, plugin_id)
    root = Path(install_root) if install_root is not None else default_install_root()
    target = installation_path(plugin, root).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        if _existing_installation_is_current(plugin, target):
            return target.resolve()
        raise MaterializerInstallError(
            f"installation target already exists but does not match the registry: {target}"
        )

    staging = Path(
        tempfile.mkdtemp(prefix=f".{plugin['id']}.agora-install-", dir=target.parent)
    )
    try:
        resolved = _checkout_repository(plugin, staging)
        if resolved != plugin["ref"]:  # defensive if a test double violates the helper contract
            raise MaterializerInstallError(
                f"downloaded commit {resolved} does not match registered commit {plugin['ref']}"
            )
        manifest = _validate_manifest_binding(plugin, staging)
        _install_python_project(plugin, staging)
        _verify_execution_modules(manifest, staging)
        receipt = _receipt_for(plugin, staging)
        (staging / INSTALLATION_RECEIPT).write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(staging, target)
        return target.resolve()
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover and install Agora-registered third-party materializer plugins."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="list materializer plugins known to Agora")

    install = subparsers.add_parser(
        "install", help="download and install one immutable registered materializer plugin"
    )
    install.add_argument("plugin_id", help="registered materializer plugin id")
    install.add_argument(
        "--root",
        type=Path,
        default=None,
        help="installation root (defaults to AGORA_DATA_HOME/XDG_DATA_HOME)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "list":
        registry = load_registry()
        for plugin in registry["plugins"]:
            materializers = ", ".join(plugin["materializers"])
            print(f"{plugin['id']}\t{plugin['version']}\t{materializers}\t{plugin['description']}")
        return 0

    target = install_materializer(args.plugin_id, install_root=args.root)
    manifest = target / select_plugin(load_registry(), args.plugin_id)["manifest"]
    print(f"Installed {args.plugin_id} at {target}")
    print(f"Materializer manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
