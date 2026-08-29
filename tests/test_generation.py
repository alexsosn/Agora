from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path

import yaml

from scripts.generate_marketplaces import (
    ROOT,
    check_outputs,
    release_to_semver,
    render_outputs,
)


class MarketplaceGenerationTests(unittest.TestCase):
    def test_release_to_semver(self):
        self.assertEqual(release_to_semver("v0.1"), "0.1.0")
        self.assertEqual(release_to_semver("v1.2.3"), "1.2.3")
        with self.assertRaises(ValueError):
            release_to_semver("next")

    def test_expected_native_artifacts_are_generated(self):
        outputs = {path.relative_to(ROOT) for path in render_outputs()}
        expected = {
            Path(".claude-plugin/marketplace.json"),
            Path(".agents/plugins/marketplace.json"),
            Path("plugins/context-fabric/.claude-plugin/mcp.json"),
            Path("plugins/context-fabric/.codex-plugin/mcp.json"),
        }
        for plugin_id in ("context-fabric", "perseus", "sefaria", "sedra"):
            expected.add(Path(f"plugins/{plugin_id}/.claude-plugin/plugin.json"))
            expected.add(Path(f"plugins/{plugin_id}/.codex-plugin/plugin.json"))
        self.assertEqual(outputs, expected)

    def test_committed_artifacts_are_fresh(self):
        self.assertEqual(check_outputs(), [])

    def test_marketplaces_follow_release_plugin_order(self):
        with (ROOT / "registry/v0.1.yaml").open("r", encoding="utf-8") as fh:
            scope = yaml.safe_load(fh)
        expected = scope["required_plugins"]

        with (ROOT / ".claude-plugin/marketplace.json").open("r", encoding="utf-8") as fh:
            claude = json.load(fh)
        with (ROOT / ".agents/plugins/marketplace.json").open("r", encoding="utf-8") as fh:
            codex = json.load(fh)

        self.assertEqual([item["name"] for item in claude["plugins"]], expected)
        self.assertEqual([item["name"] for item in codex["plugins"]], expected)

    def test_codex_entries_use_native_local_source_and_policy(self):
        with (ROOT / ".agents/plugins/marketplace.json").open("r", encoding="utf-8") as fh:
            marketplace = json.load(fh)
        for entry in marketplace["plugins"]:
            self.assertEqual(entry["source"]["source"], "local")
            self.assertEqual(entry["source"]["path"], f"./plugins/{entry['name']}")
            self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
            self.assertEqual(entry["policy"]["authentication"], "ON_INSTALL")
            self.assertEqual(entry["category"], "Education & Research")

    def test_claude_entries_use_local_plugin_roots(self):
        with (ROOT / ".claude-plugin/marketplace.json").open("r", encoding="utf-8") as fh:
            marketplace = json.load(fh)
        for entry in marketplace["plugins"]:
            self.assertEqual(entry["source"], f"./plugins/{entry['name']}")

    def test_claude_marketplace_does_not_leak_codex_display_name(self):
        with (ROOT / ".claude-plugin/marketplace.json").open("r", encoding="utf-8") as fh:
            marketplace = json.load(fh)
        for entry in marketplace["plugins"]:
            self.assertNotIn("displayName", entry)

    def test_context_fabric_manifests_reference_platform_specific_mcp_configs(self):
        with (ROOT / "plugins/context-fabric/.claude-plugin/plugin.json").open(
            "r", encoding="utf-8"
        ) as fh:
            claude = json.load(fh)
        with (ROOT / "plugins/context-fabric/.codex-plugin/plugin.json").open(
            "r", encoding="utf-8"
        ) as fh:
            codex = json.load(fh)

        self.assertEqual(claude["mcpServers"], "./.claude-plugin/mcp.json")
        self.assertEqual(codex["mcpServers"], "./.codex-plugin/mcp.json")

        for plugin_id in ("perseus", "sefaria", "sedra"):
            with (ROOT / f"plugins/{plugin_id}/.claude-plugin/plugin.json").open(
                "r", encoding="utf-8"
            ) as fh:
                self.assertNotIn("mcpServers", json.load(fh))

    def test_context_fabric_claude_mcp_uses_plugin_root(self):
        with (ROOT / "plugins/context-fabric/.claude-plugin/mcp.json").open(
            "r", encoding="utf-8"
        ) as fh:
            config = json.load(fh)
        self.assertEqual(set(config), {"context-fabric"})
        server = config["context-fabric"]
        self.assertEqual(server["command"], "uv")
        self.assertEqual(
            server["args"],
            [
                "run",
                "--project",
                "${CLAUDE_PLUGIN_ROOT}",
                "agora-context-fabric-mcp",
                "--plugin-root",
                "${CLAUDE_PLUGIN_ROOT}",
            ],
        )

    def test_context_fabric_codex_mcp_uses_plugin_relative_cwd(self):
        with (ROOT / "plugins/context-fabric/.codex-plugin/mcp.json").open(
            "r", encoding="utf-8"
        ) as fh:
            config = json.load(fh)
        self.assertEqual(set(config), {"mcpServers"})
        server = config["mcpServers"]["context-fabric"]
        self.assertEqual(server["cwd"], ".")
        self.assertEqual(server["command"], "uv")
        self.assertEqual(
            server["args"],
            [
                "run",
                "--project",
                ".",
                "agora-context-fabric-mcp",
                "--plugin-root",
                ".",
            ],
        )

    def test_context_fabric_project_declares_runtime_entrypoint_and_dependencies(self):
        with (ROOT / "plugins/context-fabric/pyproject.toml").open("rb") as fh:
            project = tomllib.load(fh)["project"]
        self.assertEqual(project["requires-python"], ">=3.13")
        self.assertIn("cfabric-mcp==0.1.7", project["dependencies"])
        self.assertIn("PyYAML>=6.0,<7", project["dependencies"])
        self.assertEqual(
            project["scripts"]["agora-context-fabric-mcp"],
            "agora_context_fabric.server:main",
        )

    def test_antigravity_is_not_a_phase_2_output(self):
        for path in render_outputs():
            self.assertNotIn("antigravity", str(path).lower())


if __name__ == "__main__":
    unittest.main()
