"""#292: a blocked Greek corpus member must have a truthful researcher exit."""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ISSUE = "context-fabric/duplicate-structure-levels"
SECTION = "## Greek collection member is blocked by duplicate structure levels"


class GreekBlockedMemberRecoveryDocsTests(unittest.TestCase):
    def test_recovery_tracks_a_real_blocking_member_issue(self):
        resources = yaml.safe_load(
            (ROOT / "registry/resources.yaml").read_text(encoding="utf-8")
        )["resources"]
        greek = next(row for row in resources if row["id"] == "greek_literature")
        issues = greek["verification"]["known_issues"]
        known = next(row for row in issues if row["id"] == ISSUE)
        self.assertEqual((known["impact"], known["severity"]), ("member", "blocking"))

        collection = yaml.safe_load(
            (ROOT / "registry/collections/greek_literature.yaml").read_text(
                encoding="utf-8"
            )
        )
        flagged = [
            member for member in collection["members"]
            if ISSUE in {
                item["issue_id"]
                for item in member.get("verification", {}).get("known_issues", [])
            }
        ]
        self.assertGreater(len(flagged), 0)

    def test_researcher_can_reach_safe_recovery_from_plugin_page(self):
        trouble = (ROOT / "wiki/guides/troubleshooting.md").read_text(
            encoding="utf-8"
        )
        plugin = (ROOT / "wiki/guides/plugins/context-fabric.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(SECTION, trouble)
        self.assertIn(
            "[Greek collection member is blocked by duplicate structure levels]"
            "(#greek-collection-member-is-blocked-by-duplicate-structure-levels)",
            trouble,
        )
        self.assertIn(
            "../troubleshooting.md#greek-collection-member-is-blocked-by-duplicate-structure-levels",
            plugin,
        )

    def test_recovery_does_not_misrepresent_unsupported_structure_as_fixed(self):
        trouble = (ROOT / "wiki/guides/troubleshooting.md").read_text(
            encoding="utf-8"
        )
        section = trouble.split(SECTION, 1)[1].split("\n## ", 1)[0]
        for expected in (
            ISSUE,
            "KnownMemberIssueError",
            "do not bypass",
            "Perseus",
            "Scaife",
            "passage retrieval",
            "not equivalent",
            "edition",
            "schema",
        ):
            self.assertIn(expected.lower(), section.lower())


if __name__ == "__main__":
    unittest.main()
