from __future__ import annotations

import json
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

    def test_antigravity_is_not_a_phase_2_output(self):
        for path in render_outputs():
            self.assertNotIn("antigravity", str(path).lower())


if __name__ == "__main__":
    unittest.main()
