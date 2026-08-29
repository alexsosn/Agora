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

PLUGIN_IDS = ("context-fabric", "perseus", "sefaria", "sedra")


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
        }
        for plugin_id in PLUGIN_IDS:
            expected.add(Path(f"plugins/{plugin_id}/.claude-plugin/plugin.json"))
            expected.add(Path(f"plugins/{plugin_id}/.codex-plugin/plugin.json"))
            expected.add(Path(f"plugins/{plugin_id}/.claude-plugin/mcp.json"))
            expected.add(Path(f"plugins/{plugin_id}/.codex-plugin/mcp.json"))
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

    def test_all_manifests_reference_platform_specific_mcp_configs(self):
        for plugin_id in PLUGIN_IDS:
            with (ROOT / f"plugins/{plugin_id}/.claude-plugin/plugin.json").open(
                "r", encoding="utf-8"
            ) as fh:
                claude = json.load(fh)
            with (ROOT / f"plugins/{plugin_id}/.codex-plugin/plugin.json").open(
                "r", encoding="utf-8"
            ) as fh:
                codex = json.load(fh)
            self.assertEqual(claude["mcpServers"], "./.claude-plugin/mcp.json")
            self.assertEqual(codex["mcpServers"], "./.codex-plugin/mcp.json")

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

    def test_perseus_claude_mcp_runs_pinned_upstream_package(self):
        with (ROOT / "plugins/perseus/.claude-plugin/mcp.json").open(
            "r", encoding="utf-8"
        ) as fh:
            server = json.load(fh)["perseus"]
        self.assertEqual(server["command"], "uvx")
        self.assertEqual(
            server["args"],
            ["--from", "perseus-mcp==1.0.2", "perseus-mcp"],
        )

    def test_sefaria_claude_mcp_uses_official_hosted_texts_endpoint(self):
        with (ROOT / "plugins/sefaria/.claude-plugin/mcp.json").open(
            "r", encoding="utf-8"
        ) as fh:
            server = json.load(fh)["sefaria"]
        self.assertEqual(
            server,
            {"type": "sse", "url": "https://mcp.sefaria.org/sse"},
        )

    def test_sedra_claude_mcp_runs_bundled_adapter(self):
        with (ROOT / "plugins/sedra/.claude-plugin/mcp.json").open(
            "r", encoding="utf-8"
        ) as fh:
            server = json.load(fh)["sedra"]
        self.assertEqual(server["command"], "uv")
        self.assertEqual(
            server["args"],
            [
                "run",
                "--project",
                "${CLAUDE_PLUGIN_ROOT}",
                "agora-sedra-mcp",
            ],
        )

    def test_codex_mcp_files_use_strict_stdio_shape(self):
        allowed = {"type", "command", "args", "env", "cwd"}
        for plugin_id in PLUGIN_IDS:
            with (ROOT / f"plugins/{plugin_id}/.codex-plugin/mcp.json").open(
                "r", encoding="utf-8"
            ) as fh:
                config = json.load(fh)
            self.assertEqual(set(config), {"mcpServers"})
            self.assertEqual(set(config["mcpServers"]), {plugin_id})
            server = config["mcpServers"][plugin_id]
            self.assertEqual(server["type"], "stdio")
            self.assertLessEqual(set(server), allowed)

    def test_context_fabric_codex_mcp_uses_plugin_relative_cwd(self):
        with (ROOT / "plugins/context-fabric/.codex-plugin/mcp.json").open(
            "r", encoding="utf-8"
        ) as fh:
            server = json.load(fh)["mcpServers"]["context-fabric"]
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

    def test_perseus_codex_mcp_runs_pinned_upstream_package(self):
        with (ROOT / "plugins/perseus/.codex-plugin/mcp.json").open(
            "r", encoding="utf-8"
        ) as fh:
            server = json.load(fh)["mcpServers"]["perseus"]
        self.assertEqual(server["command"], "uvx")
        self.assertEqual(
            server["args"],
            ["--from", "perseus-mcp==1.0.2", "perseus-mcp"],
        )

    def test_sefaria_codex_mcp_bridges_legacy_sse_over_stdio(self):
        with (ROOT / "plugins/sefaria/.codex-plugin/mcp.json").open(
            "r", encoding="utf-8"
        ) as fh:
            server = json.load(fh)["mcpServers"]["sefaria"]
        self.assertEqual(server["command"], "uvx")
        self.assertEqual(
            server["args"],
            [
                "--from",
                "mcp-proxy==0.12.0",
                "--with",
                "mcp>=1.17,<2",
                "mcp-proxy",
                "https://mcp.sefaria.org/sse",
            ],
        )

    def test_sedra_codex_mcp_runs_bundled_adapter(self):
        with (ROOT / "plugins/sedra/.codex-plugin/mcp.json").open(
            "r", encoding="utf-8"
        ) as fh:
            server = json.load(fh)["mcpServers"]["sedra"]
        self.assertEqual(server["cwd"], ".")
        self.assertEqual(server["command"], "uv")
        self.assertEqual(
            server["args"],
            ["run", "--project", ".", "agora-sedra-mcp"],
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
