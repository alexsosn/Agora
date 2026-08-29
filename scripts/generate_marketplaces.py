#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_registry import validate_registry

CODEX_CATEGORY = "Education & Research"
CODEX_INSTALLATION = "AVAILABLE"
CODEX_AUTHENTICATION = "ON_INSTALL"
PERSEUS_PACKAGE = "perseus-mcp==1.0.2"
SEFARIA_TEXTS_MCP = "https://mcp.sefaria.org/sse"
MCP_PROXY_PACKAGE = "mcp-proxy==0.12.0"
MCP_PROXY_MCP_COMPAT = "mcp>=1.17,<2"


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
            "category": CODEX_CATEGORY,
            "websiteURL": marketplace["repository"],
        },
    }


def claude_marketplace(
    plugins: list[dict[str, Any]], marketplace: dict[str, Any]
) -> dict[str, Any]:
    publisher = marketplace["publisher"]
    return {
        "name": marketplace["id"],
        "description": marketplace["description"],
        "owner": {"name": publisher["name"]},
        "plugins": [
            {
                "name": plugin["id"],
                "source": f"./plugins/{plugin['id']}",
                "description": plugin["description"],
                "author": {"name": publisher["name"]},
                "homepage": marketplace["repository"],
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
                "category": CODEX_CATEGORY,
            }
            for plugin in plugins
        ],
    }


def claude_mcp(plugin_id: str) -> dict[str, Any]:
    if plugin_id == "context-fabric":
        server = {
            "command": "uv",
            "args": [
                "run",
                "--project",
                "${CLAUDE_PLUGIN_ROOT}",
                "agora-context-fabric-mcp",
                "--plugin-root",
                "${CLAUDE_PLUGIN_ROOT}",
            ],
        }
    elif plugin_id == "perseus":
        server = {
            "command": "uvx",
            "args": ["--from", PERSEUS_PACKAGE, "perseus-mcp"],
        }
    elif plugin_id == "sefaria":
        server = {"type": "sse", "url": SEFARIA_TEXTS_MCP}
    elif plugin_id == "sedra":
        server = {
            "command": "uv",
            "args": [
                "run",
                "--project",
                "${CLAUDE_PLUGIN_ROOT}",
                "agora-sedra-mcp",
            ],
        }
    else:
        raise ValueError(f"no Claude MCP integration is defined for plugin {plugin_id!r}")
    return {plugin_id: server}


def codex_mcp(plugin_id: str) -> dict[str, Any]:
    if plugin_id == "context-fabric":
        server = {
            "type": "stdio",
            "cwd": ".",
            "command": "uv",
            "args": [
                "run",
                "--project",
                ".",
                "agora-context-fabric-mcp",
                "--plugin-root",
                ".",
            ],
        }
    elif plugin_id == "perseus":
        server = {
            "type": "stdio",
            "cwd": ".",
            "command": "uvx",
            "args": ["--from", PERSEUS_PACKAGE, "perseus-mcp"],
        }
    elif plugin_id == "sefaria":
        # Codex supports stdio and streamable HTTP, not legacy SSE. Bridge the
        # official Sefaria Texts SSE endpoint to stdio. mcp-proxy 0.12.0 was
        # published against MCP SDK 1.x and has an unbounded dependency that
        # otherwise resolves incompatible MCP 2.x, so constrain its environment.
        server = {
            "type": "stdio",
            "command": "uvx",
            "args": [
                "--from",
                MCP_PROXY_PACKAGE,
                "--with",
                MCP_PROXY_MCP_COMPAT,
                "mcp-proxy",
                SEFARIA_TEXTS_MCP,
            ],
        }
    elif plugin_id == "sedra":
        server = {
            "type": "stdio",
            "cwd": ".",
            "command": "uv",
            "args": ["run", "--project", ".", "agora-sedra-mcp"],
        }
    else:
        raise ValueError(f"no Codex MCP integration is defined for plugin {plugin_id!r}")
    return {"mcpServers": {plugin_id: server}}


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
            claude_mcp(plugin["id"])
        )
        outputs[plugin_root / ".codex-plugin/mcp.json"] = json_text(
            codex_mcp(plugin["id"])
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
