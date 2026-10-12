"""#286: pin released Burns-TF stable producer, keeping explicit trust gates.

This is source-safe: test reads only registry / CI contracts, never Workbooks.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RELEASE_SHA = "ed6c7059803ff1adee057f5bd94d3ca661aac187"
OLD_SHA = "f58b162197ad8f113b7cd6fc0088ae5dd39a096d"


class BurnsStableReleasePinTests(unittest.TestCase):
    @staticmethod
    def registry_entry() -> dict:
        registry = yaml.safe_load(
            (ROOT / "registry/materializers.yaml").read_text(encoding="utf-8")
        )
        found = [p for p in registry["plugins"] if p["id"] == "cuc-burns"]
        if len(found) != 1:
            raise AssertionError("cuc-burns must have one canonical registry entry")
        return found[0]

    def test_registry_pins_exact_published_release_and_stable_only_discovery(self):
        plugin = self.registry_entry()
        self.assertEqual(plugin["repository"], "alexsosn/CTC-TF")
        self.assertEqual(plugin["ref"], RELEASE_SHA)
        self.assertEqual(plugin["version"], "0.3.0")
        self.assertEqual(plugin["release_tracking"], {
            "mode": "github-releases", "channel": "stable", "tag_prefix": "v"
        })
        self.assertEqual(plugin["manifest"], "agora.materializer.json")
        self.assertEqual(plugin["materializers"], ["cuc-burns-csv"])

    def test_explicit_approval_and_cuc_parent_bound_materializer_remain_required(self):
        plugin = self.registry_entry()
        self.assertEqual(plugin["package"]["install_trust"], "explicit-code-execution")
        self.assertEqual(plugin["licenses"]["data"], "CC-BY-NC-ND-2.5")
        self.assertEqual(plugin["licenses"]["software"], "MIT")
        self.assertNotIn("convert", plugin["materializers"])
        self.assertNotIn("latest", plugin["ref"])

    def test_real_source_workflow_uses_same_released_commit_not_old_pin(self):
        workflow = (
            ROOT / ".github/workflows/ctc-burns-registered-e2e.yml"
        ).read_text(encoding="utf-8")
        self.assertGreaterEqual(workflow.count(RELEASE_SHA), 2)
        self.assertNotIn(OLD_SHA, workflow)
        self.assertIn("bubblewrap", workflow.lower())
        self.assertNotIn("upload-artifact", workflow)


if __name__ == "__main__":
    unittest.main()
