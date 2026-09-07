#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLAN = Path("wiki/releases/v0.1-plan-active.md")
BEGIN = "<!-- BEGIN GENERATED V0.1 PLUGIN VERIFICATION -->"
END = "<!-- END GENERATED V0.1 PLUGIN VERIFICATION -->"


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _canonical_model(root: Path) -> list[dict[str, Any]]:
    root = Path(root)
    scope = load_yaml(root / "registry" / "v0.1.yaml")
    plugin_doc = load_yaml(root / "registry" / "plugins.yaml")
    check_doc = load_yaml(root / "registry" / "verification-checks.yaml")

    required = scope.get("required_plugins")
    if not isinstance(required, list) or not required:
        raise ValueError("registry/v0.1.yaml must define non-empty required_plugins")

    plugins = {
        item.get("id"): item
        for item in plugin_doc.get("plugins", [])
        if isinstance(item, dict) and item.get("id")
    }
    checks = {
        item.get("id"): item
        for item in check_doc.get("checks", [])
        if isinstance(item, dict) and item.get("id")
    }

    result: list[dict[str, Any]] = []
    for plugin_id in required:
        plugin = plugins.get(plugin_id)
        if plugin is None:
            raise ValueError(f"v0.1 plugin {plugin_id!r} is missing from registry/plugins.yaml")
        verification = plugin.get("verification")
        if not isinstance(verification, dict) or not verification.get("status"):
            raise ValueError(f"v0.1 plugin {plugin_id!r} has no verification metadata")
        clients = verification.get("clients")
        if not isinstance(clients, dict) or not clients:
            raise ValueError(f"v0.1 plugin {plugin_id!r} has no client verification metadata")

        rendered_clients: list[dict[str, Any]] = []
        for client_id in sorted(clients):
            evidence = clients[client_id]
            if not isinstance(evidence, dict) or not evidence.get("status") or not evidence.get("transport"):
                raise ValueError(
                    f"v0.1 plugin {plugin_id!r} client {client_id!r} has incomplete verification metadata"
                )
            references = evidence.get("checks")
            if not isinstance(references, list) or not references:
                raise ValueError(
                    f"v0.1 plugin {plugin_id!r} client {client_id!r} has no referenced verification checks"
                )

            resolved_checks: list[dict[str, Any]] = []
            for reference in references:
                check_id = reference.get("check_id") if isinstance(reference, dict) else None
                if not check_id or check_id not in checks:
                    raise ValueError(
                        f"verification check {check_id!r} referenced by {plugin_id}:{client_id} is missing"
                    )
                check = checks[check_id]
                mismatches: list[str] = []
                if check.get("plugin") != plugin_id:
                    mismatches.append("plugin")
                if check.get("client") != client_id:
                    mismatches.append("client")
                if check.get("transport") != evidence.get("transport"):
                    mismatches.append("transport")
                if mismatches:
                    raise ValueError(
                        f"verification check {check_id!r} does not match {plugin_id}:{client_id} "
                        f"for {', '.join(mismatches)}"
                    )
                resolved_checks.append(check)

            live_verified = evidence["status"] == "verified" and any(
                check.get("kind") == "live" and check.get("evidence_level") == "verified"
                for check in resolved_checks
            )
            rendered_clients.append(
                {
                    "id": client_id,
                    "status": evidence["status"],
                    "transport": evidence["transport"],
                    "live_verified": live_verified,
                }
            )

        result.append(
            {
                "id": plugin_id,
                "status": verification["status"],
                "clients": rendered_clients,
            }
        )
    return result


def render_verification_block(root: Path = ROOT) -> str:
    lines = [
        BEGIN,
        "Current v0.1 verification status (generated from the canonical registry):",
    ]
    for plugin in _canonical_model(root):
        lines.append(f"- {plugin['id']} aggregate: `{plugin['status']}`")
        for client in plugin["clients"]:
            suffix = " — live-verified" if client["live_verified"] else ""
            lines.append(
                f"  - {plugin['id']} / {client['id']}: `{client['status']}` "
                f"via `{client['transport']}`{suffix}"
            )
    lines.extend(
        [
            "",
            "Aggregate plugin status and per-client status are separate claims; a live-verified client path does not promote the aggregate plugin status.",
            END,
        ]
    )
    return "\n".join(lines)


def replace_generated_block(document: str, block: str) -> str:
    if document.count(BEGIN) != 1 or document.count(END) != 1:
        raise ValueError("release plan must contain exactly one generated verification marker pair")
    before, rest = document.split(BEGIN, 1)
    _current, after = rest.split(END, 1)
    if not block.startswith(BEGIN) or not block.endswith(END):
        raise ValueError("generated verification block has invalid markers")
    return before + block + after


def expected_text(root: Path = ROOT) -> str:
    root = Path(root)
    path = root / PLAN
    if not path.is_file():
        raise ValueError(f"missing release plan: {PLAN}")
    current = path.read_text(encoding="utf-8")
    return replace_generated_block(current, render_verification_block(root))


def check(root: Path = ROOT) -> list[str]:
    root = Path(root)
    path = root / PLAN
    try:
        expected = expected_text(root)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    actual = path.read_text(encoding="utf-8")
    return [] if actual == expected else [f"stale generated v0.1 verification block: {PLAN}"]


def write(root: Path = ROOT) -> Path:
    root = Path(root)
    path = root / PLAN
    path.write_text(expected_text(root), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the registry-derived v0.1 plugin/client verification block in the release plan."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail without writing if the committed verification block is missing or stale.",
    )
    args = parser.parse_args()

    if args.check:
        errors = check(ROOT)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print("v0.1 release verification status is fresh against the canonical registry.")
        return 0

    try:
        path = write(ROOT)
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
