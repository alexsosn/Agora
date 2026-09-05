from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "registry/plugins.yaml"
PERSEUS_SKILL = ROOT / "plugins/perseus/skills/perseus-research/SKILL.md"
KNOWN_ISSUE_ID = "perseus/cts-scaife-inventory-routing"


class PerseusContractHealthTests(unittest.TestCase):
    def test_perseus_declares_structured_cts_scaife_routing_advisory(self):
        document = yaml.safe_load(PLUGINS.read_text(encoding="utf-8"))
        plugins = {plugin["id"]: plugin for plugin in document["plugins"]}
        perseus = plugins["perseus"]

        known_issues = perseus["verification"].get("known_issues", [])
        issue = next(
            (item for item in known_issues if item.get("id") == KNOWN_ISSUE_ID),
            None,
        )
        self.assertIsNotNone(issue, f"missing plugin known issue {KNOWN_ISSUE_ID}")
        self.assertEqual(issue["severity"], "advisory")
        self.assertIn("Scaife", issue["summary"])
        self.assertIn("CTS", issue["summary"])
        self.assertEqual(issue["upstream"][0]["repository"], "tonyjurg/Perseus-mcp")

    def test_perseus_skill_routes_scaife_only_merged_discovery(self):
        skill = PERSEUS_SKILL.read_text(encoding="utf-8")

        self.assertIn("`find_author_names` merges CTS and Scaife", skill)
        self.assertIn(
            "`get_author_resources` and `get_work_resources` are CTS-oriented",
            skill,
        )
        self.assertIn("`get_scaife_library_metadata`", skill)
        self.assertIn("not proof that the work is unavailable", skill)
        self.assertIn(
            "Do not infer that CTS and Scaife edition or translation URNs are equivalent",
            skill,
        )


if __name__ == "__main__":
    unittest.main()
