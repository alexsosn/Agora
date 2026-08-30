#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_registry import validate_registry

PLUGIN_CATEGORY = "Education & Research"
CODEX_INSTALLATION = "AVAILABLE"
CODEX_AUTHENTICATION = "ON_INSTALL"


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def release_to_semver(release: str) -> str:
    value = release.removeprefix("v")
    parts = value.split(".")
    if not 1 <= len(parts) <= 3 or any(not part.isdigit() for part in parts):
        raise ValueError(f"release {release!r} cannot be converted to semantic version")
    return ".".join(parts + ["0"] * (3 - len(parts)))


def keyword_list(plugin: dict[str, Any]) -> list[str]:
    return sorted(set(plugin["disciplines"]) | set(plugin["capabilities"]))


def claude_plugin_manifest(
    plugin: dict[str, Any], marketplace: dict[str, Any], version: str
) -> dict[str, Any]:
    publisher = marketplace["publisher"]
    author: dict[str, str] = {"name": publisher["name"]}
    if publisher.get("url"):
        author["url"] = publisher["url"]
    return {
        "name": plugin["id"],
        "version": version,
        "description": plugin["description"],
        "author": author,
        "homepage": marketplace["repository"],
        "repository": marketplace["repository"],
        "license": marketplace["license"],
        "keywords": keyword_list(plugin),
        "mcpServers": "./.claude-plugin/mcp.json",
    }


def codex_plugin_manifest(
    plugin: dict[str, Any], marketplace: dict[str, Any], version: str
) -> dict[str, Any]:
    publisher = marketplace["publisher"]
    author: dict[str, str] = {"name": publisher["name"]}
    if publisher.get("url"):
        author["url"] = publisher["url"]
    return {
        "name": plugin["id"],
        "version": version,
        "description": plugin["description"],
        "author": author,
        "homepage": marketplace["repository"],
        "repository": marketplace["repository"],
        "license": marketplace["license"],
        "keywords": keyword_list(plugin),
        "mcpServers": "./.codex-plugin/mcp.json",
        "interface": {
            "displayName": plugin["name"],
            "shortDescription": plugin["description"],
            "longDescription": plugin["description"],
            "developerName": publisher["name"],
            "category": PLUGIN_CATEGORY,
            "websiteURL": marketplace["repository"],
        },
    }


def claude_marketplace(
    plugins: list[dict[str, Any]], marketplace: dict[str, Any]
) -> dict[str, Any]:
    publisher = marketplace["publisher"]
    return {
        "name": marketplace["id"],
        "owner": {"name": publisher["name"]},
        # Claude Code reads the marketplace blurb from metadata.description; a
        # top-level "description" key is ignored.
        "metadata": {"description": marketplace["description"]},
        "plugins": [
            {
                "name": plugin["id"],
                "source": f"./plugins/{plugin['id']}",
                "description": plugin["description"],
                "author": {"name": publisher["name"]},
                "homepage": marketplace["repository"],
                "category": PLUGIN_CATEGORY,
            }
            for plugin in plugins
        ],
    }


def codex_marketplace(
    plugins: list[dict[str, Any]], marketplace: dict[str, Any]
) -> dict[str, Any]:
    return {
        "name": marketplace["id"],
        "interface": {"displayName": marketplace["display_name"]},
        "plugins": [
            {
                "name": plugin["id"],
                "source": {
                    "source": "local",
                    "path": f"./plugins/{plugin['id']}",
                },
                "policy": {
                    "installation": CODEX_INSTALLATION,
                    "authentication": CODEX_AUTHENTICATION,
                },
                "category": PLUGIN_CATEGORY,
            }
            for plugin in plugins
        ],
    }


def claude_mcp(plugin: dict[str, Any]) -> dict[str, Any]:
    return {plugin["id"]: copy.deepcopy(plugin["runtime"]["launch"]["claude"])}


def codex_mcp(plugin: dict[str, Any]) -> dict[str, Any]:
    return {
        "mcpServers": {
            plugin["id"]: copy.deepcopy(plugin["runtime"]["launch"]["codex"])
        }
    }


def render_outputs(root: Path = ROOT) -> dict[Path, str]:
    root = Path(root)
    registry = root / "registry"

    errors = validate_registry(root)
    if errors:
        joined = "\n".join(f"- {error}" for error in errors)
        raise ValueError(f"canonical registry is invalid:\n{joined}")

    marketplace = load_yaml(registry / "marketplace.yaml")
    plugins_doc = load_yaml(registry / "plugins.yaml")
    scope = load_yaml(registry / "v0.1.yaml")

    plugin_by_id = {plugin["id"]: plugin for plugin in plugins_doc["plugins"]}
    plugins = [plugin_by_id[plugin_id] for plugin_id in scope["required_plugins"]]
    version = release_to_semver(scope["release"])

    outputs: dict[Path, str] = {
        root / ".claude-plugin/marketplace.json": json_text(
            claude_marketplace(plugins, marketplace)
        ),
        root / ".agents/plugins/marketplace.json": json_text(
            codex_marketplace(plugins, marketplace)
        ),
    }

    for plugin in plugins:
        plugin_root = root / "plugins" / plugin["id"]
        outputs[plugin_root / ".claude-plugin/plugin.json"] = json_text(
            claude_plugin_manifest(plugin, marketplace, version)
        )
        outputs[plugin_root / ".codex-plugin/plugin.json"] = json_text(
            codex_plugin_manifest(plugin, marketplace, version)
        )
        outputs[plugin_root / ".claude-plugin/mcp.json"] = json_text(
            claude_mcp(plugin)
        )
        outputs[plugin_root / ".codex-plugin/mcp.json"] = json_text(
            codex_mcp(plugin)
        )

    return outputs


def write_outputs(root: Path = ROOT) -> list[Path]:
    outputs = render_outputs(root)
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return list(outputs)


def check_outputs(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for path, expected in render_outputs(root).items():
        relative = path.relative_to(root)
        if not path.is_file():
            errors.append(f"missing generated artifact: {relative}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            errors.append(f"stale generated artifact: {relative}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Claude Code and ChatGPT/Codex marketplace artifacts from Agora's canonical registry."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if committed generated artifacts are missing or stale",
    )
    args = parser.parse_args()

    try:
        if args.check:
            errors = check_outputs()
            if errors:
                print("Marketplace generation check failed:", file=sys.stderr)
                for error in errors:
                    print(f"- {error}", file=sys.stderr)
                return 1
            print("Marketplace artifacts are fresh for Claude Code and ChatGPT/Codex.")
            return 0

        written = write_outputs()
    except (ValueError, KeyError) as exc:
        print(f"Marketplace generation failed: {exc}", file=sys.stderr)
        return 1

    print("Generated marketplace artifacts:")
    for path in written:
        print(f"- {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
