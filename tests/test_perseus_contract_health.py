from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "registry/plugins.yaml"
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


if __name__ == "__main__":
    unittest.main()
