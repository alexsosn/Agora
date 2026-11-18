"""#172: recovery instructions are discoverable by visible symptom, not subsystem."""
from __future__ import annotations

import re
import unittest

import yaml
from pathlib import Path

from scripts import generate_plugin_docs

ROOT = Path(__file__).resolve().parents[1]
GREEK_ISSUE = "context-fabric/duplicate-structure-levels"
GREEK_SECTION = "## Greek collection member is blocked by duplicate structure levels"
RECOVERY = ROOT / "wiki/guides/troubleshooting.md"
INSTALL = ROOT / "wiki/guides/installation.md"
DEV = ROOT / "wiki/guides/development-setup.md"
COMPAT = ROOT / "wiki/guides/compatibility.md"
PLUGIN_DIR = ROOT / "wiki/guides/plugins"
HEADING = (
    "Marketplace or plugin is not visible",
    "MCP server does not start",
    "uv, uvx or Python is not found",
    "Remote lookup fails",
    "Corpus acquisition or compilation appears stuck",
    "Corpus cache uses unexpected disk space",
    "Search count stops at 10,000",
    "CUC text formats appear missing",
    "Perseus passage works but navigation fails",
    "Sefaria search repeats a reference",
    "Plugin works in one client but not another",
)
EXITS = {
    "context-fabric": ("corpus-acquisition-or-compilation-appears-stuck",
                       "search-count-stops-at-10000", "cuc-text-formats-appear-missing"),
    "perseus": ("perseus-passage-works-but-navigation-fails",),
    "sefaria": ("sefaria-search-repeats-a-reference",),
    "sedra": ("remote-lookup-fails",),
    "cal": ("remote-lookup-fails",),
}
ISSUES = {
    "sefaria/search-version-duplicates": "sefaria-search-repeats-a-reference",
    "context-fabric/search-count-cache-cap": "search-count-stops-at-10000",
    "context-fabric/cuc-text-format-discovery": "cuc-text-formats-appear-missing",
    "perseus/legacy-cts-malformed-navigation": "perseus-passage-works-but-navigation-fails",
}


def slug(text: str) -> str:
    return re.sub(r"[\s-]+", "-", re.sub(r"[^\w\s-]", "", text.lower())).strip("-")


class SymptomRecoveryDocsTests(unittest.TestCase):
    def test_every_named_user_symptom_has_classification_action_and_detailed_exit(self):
        self.assertTrue(RECOVERY.is_file())
        body = RECOVERY.read_text(encoding="utf-8")
        self.assertIn("## Choose the symptom", body)
        parts = re.split(r"^## (.+)$", body, flags=re.MULTILINE)
        sections = {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}
        for heading in HEADING:
            with self.subTest(heading=heading):
                self.assertIn(heading, sections)
                section = sections[heading]
                self.assertIn("**Likely cause:**", section)
                self.assertIn("**Safe next action:**", section)
                self.assertIn("**Details:**", section)
                self.assertRegex(section, r"\]\([^)]*\.md(?:#[a-z0-9-]+)?\)")
                self.assertIn("(#" + slug(heading) + ")", body)

    def test_user_install_is_separate_from_contributor_local_setup(self):
        install = INSTALL.read_text(encoding="utf-8")
        self.assertNotIn("## Local Codex development/testing", install)
        self.assertIn("[local development setup](development-setup.md)", install)
        self.assertIn("[troubleshooting by symptom](troubleshooting.md)", install)
        self.assertIn("## Updating", install)
        self.assertIn("## Removing", install)
        self.assertIn("describe_available_corpus", install)
        self.assertIn("prepare_corpus", install)
        self.assertIn("load_corpus", install)
        self.assertIn("corpus_cache_status", install)
        developer = DEV.read_text(encoding="utf-8")
        self.assertIn("codex plugin marketplace add", developer)
        self.assertIn("codex plugin add context-fabric@agora", developer)
        self.assertIn("development-setup.md", (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8"))
        self.assertIn("troubleshooting.md", (ROOT / "wiki/guides/README.md").read_text(encoding="utf-8"))
        self.assertIn("| **Troubleshooting** | [Start from the symptom you see](troubleshooting.md) |",
                      (ROOT / "wiki/guides/README.md").read_text(encoding="utf-8"))

    def test_generated_plugin_pages_point_directly_to_relevant_symptoms(self):
        for plugin, fragments in EXITS.items():
            with self.subTest(plugin=plugin):
                page = (PLUGIN_DIR / (plugin + ".md")).read_text(encoding="utf-8")
                for fragment in fragments:
                    self.assertIn("../troubleshooting.md#" + fragment, page)
        self.assertTrue(generate_plugin_docs.check())

    def test_each_known_limitation_links_to_its_recovery(self):
        compatibility = COMPAT.read_text(encoding="utf-8")
        rows = compatibility.split("## Current upstream limitations", 1)[1]
        for issue, fragment in ISSUES.items():
            with self.subTest(issue=issue):
                row = next(line for line in rows.splitlines()
                           if line.startswith("|") and issue in line)
                self.assertIn("troubleshooting.md#" + fragment, row)
        self.assertIn("https://help.openai.com/en/articles/20001504", INSTALL.read_text())


    def test_recovery_tracks_a_real_blocking_member_issue(self):
        resources = yaml.safe_load(
            (ROOT / "registry/resources.yaml").read_text(encoding="utf-8")
        )["resources"]
        greek = next(row for row in resources if row["id"] == "greek_literature")
        issues = greek["verification"]["known_issues"]
        known = next(row for row in issues if row["id"] == GREEK_ISSUE)
        self.assertEqual((known["impact"], known["severity"]), ("member", "blocking"))

        collection = yaml.safe_load(
            (ROOT / "registry/collections/greek_literature.yaml").read_text(
                encoding="utf-8"
            )
        )
        flagged = [
            member for member in collection["members"]
            if GREEK_ISSUE in {
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
        self.assertIn(GREEK_SECTION, trouble)
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
        section = trouble.split(GREEK_SECTION, 1)[1].split("\n## ", 1)[0]
        for expected in (
            GREEK_ISSUE,
            "KnownMemberIssueError",
            "do not bypass",
            "Perseus",
            "Scaife",
            "passage retrieval",
            "not equivalent",
            "edition",
            "schema",
            "perseus@agora",
            "Argonautica",
        ):
            self.assertIn(expected.lower(), section.lower())


if __name__ == "__main__":
    unittest.main()
