#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any, Mapping

import yaml

ROOT = Path(__file__).resolve().parents[1]
FILE_BACKED_KINDS = {"uv-lock", "uv-constraints"}


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_environment(
    environment: Mapping[str, Any] | None,
    *,
    label: str,
    root: Path,
    errors: list[str],
) -> None:
    if not isinstance(environment, Mapping):
        errors.append(f"{label}: missing dependency environment identity")
        return

    kind = environment.get("kind")
    if kind == "hosted":
        if "path" in environment or "sha256" in environment:
            errors.append(f"{label}: hosted environment must not declare path or sha256")
        return
    if kind not in FILE_BACKED_KINDS:
        errors.append(f"{label}: unsupported dependency environment kind {kind!r}")
        return

    relative = environment.get("path")
    expected = environment.get("sha256")
    if not isinstance(relative, str) or not relative:
        errors.append(f"{label}: file-backed environment requires path")
        return
    if not isinstance(expected, str) or len(expected) != 64:
        errors.append(f"{label}: file-backed environment requires a 64-character sha256")
        return

    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        errors.append(f"{label}: environment path must be repository-relative: {relative!r}")
        return
    target = root / candidate
    if not target.is_file():
        errors.append(f"{label}: dependency environment file does not exist: {relative}")
        return
    actual = _sha256(target)
    if actual != expected:
        errors.append(
            f"{label}: sha256 mismatch for {relative}: declared {expected}, actual {actual}"
        )


def _constraint_launch_path(plugin_id: str, client: str) -> str:
    if client == "claude":
        return "${CLAUDE_PLUGIN_ROOT}/runtime-constraints.txt"
    return "runtime-constraints.txt"


def _validate_launch_binding(
    plugin: Mapping[str, Any],
    *,
    client: str,
    environment: Mapping[str, Any] | None,
    errors: list[str],
) -> None:
    plugin_id = plugin.get("id", "<unknown>")
    launch = ((plugin.get("runtime") or {}).get("launch") or {}).get(client) or {}
    command = launch.get("command")
    args = launch.get("args") or []
    kind = environment.get("kind") if isinstance(environment, Mapping) else None
    label = f"plugin[{plugin_id}].{client}"

    if kind == "hosted":
        if "url" not in launch:
            errors.append(f"{label}: hosted dependency environment requires URL launch")
        return
    if kind == "uv-lock":
        if command != "uv" or "run" not in args or "--locked" not in args:
            errors.append(f"{label}: uv-lock environment must launch with 'uv run --locked'")
        return
    if kind == "uv-constraints":
        if command != "uvx":
            errors.append(f"{label}: uv-constraints environment must launch with uvx")
            return
        if "--constraint" not in args:
            errors.append(f"{label}: uvx launch must pass --constraint")
            return
        position = args.index("--constraint")
        actual = args[position + 1] if position + 1 < len(args) else None
        expected = _constraint_launch_path(str(plugin_id), client)
        if actual != expected:
            errors.append(
                f"{label}: uvx constraint path must be {expected!r}, found {actual!r}"
            )


def validate_runtime_environments(root: Path = ROOT) -> list[str]:
    root = Path(root)
    registry_path = root / "registry/plugins.yaml"
    if not registry_path.is_file():
        return ["registry/plugins.yaml: missing plugin registry"]

    document = _load_yaml(registry_path)
    errors: list[str] = []
    for plugin in document.get("plugins", []):
        plugin_id = plugin.get("id", "<unknown>")
        clients = ((plugin.get("verification") or {}).get("clients") or {})
        for client, evidence in clients.items():
            for index, reference in enumerate((evidence or {}).get("checks", [])):
                inputs = reference.get("inputs") or {}
                label = f"plugin[{plugin_id}].verification.{client}.checks[{index}]"
                environment = inputs.get("environment")
                _validate_environment(environment, label=f"{label}.environment", root=root, errors=errors)
                _validate_launch_binding(
                    plugin,
                    client=client,
                    environment=environment,
                    errors=errors,
                )

                check_id = reference.get("check_id", "")
                if isinstance(check_id, str) and check_id.startswith("mcp-live/"):
                    _validate_environment(
                        inputs.get("harness_environment"),
                        label=f"{label}.harness_environment",
                        root=root,
                        errors=errors,
                    )

        if plugin_id == "sefaria":
            codex = ((plugin.get("runtime") or {}).get("launch") or {}).get("codex") or {}
            args = codex.get("args") or []
            if "mcp>=1.17,<2" not in args:
                errors.append(
                    "plugin[sefaria].codex: explicit mcp>=1.17,<2 compatibility guard is required"
                )

    return errors


def main() -> int:
    errors = validate_runtime_environments(ROOT)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("Runtime dependency environment identities are valid and launch-bound.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
