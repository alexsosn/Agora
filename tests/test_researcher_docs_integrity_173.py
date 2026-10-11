"""#173: bounded user-document integrity and five cognitive walkthroughs.

Existing catalog/plugin/skill tests own canonical-data comparisons. This module
owns local researcher navigation, not scholarly certification or external URLs.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ROOT / "wiki" / "guides"
WALK = GUIDES / "cognitive-walkthroughs.md"
LINK = re.compile(r"\]\(([^)]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
SOURCES = [
    ROOT / "README.md",
    GUIDES / "README.md",
    GUIDES / "installation.md",
    GUIDES / "compatibility.md",
    GUIDES / "resources.md",
    GUIDES / "context-fabric-cache.md",
    GUIDES / "context-fabric-local-import.md",
    GUIDES / "scholarly-guidance.md",
    GUIDES / "troubleshooting.md",
    GUIDES / "development-setup.md",
    WALK,
] + sorted((GUIDES / "plugins").glob("*.md")) + sorted(
    (GUIDES / "first-success").glob("*.md")
)


def github_slug(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text).lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s", "-", text).strip("-")


def valid_fragments(path: Path) -> set[str]:
    counts: dict[str, int] = {}
    fragments: set[str] = set()
    for name in HEADING.findall(path.read_text(encoding="utf-8")):
        slug = github_slug(name.strip())
        number = counts.get(slug, 0)
        fragments.add(slug if number == 0 else f"{slug}-{number}")
        counts[slug] = number + 1
    return fragments


class ResearcherDocumentationIntegrityTests(unittest.TestCase):
    def test_github_anchor_keeps_double_hyphen_after_removed_slash(self):
        self.assertEqual(
            "chatgpt--managed-codex-workspace-import",
            github_slug("ChatGPT / managed Codex workspace import"),
        )

    def test_every_local_user_document_link_and_heading_fragment_resolves(self):
        broken = []
        for source in SOURCES:
            self.assertTrue(source.is_file(), f"Expected user-facing page: {source}")
            for candidate in LINK.findall(source.read_text(encoding="utf-8")):
                dest = unquote(candidate.strip().split(" ", 1)[0].strip("<>"))
                if not dest or dest.startswith(("http://", "https://", "mailto:", "data:")):
                    continue
                path_part, _, fragment = dest.partition("#")
                target = (source.parent / path_part).resolve() if path_part else source.resolve()
                if not target.is_relative_to(ROOT.resolve()) or not target.is_file():
                    broken.append((str(source.relative_to(ROOT)), candidate, "missing/outside"))
                elif fragment and fragment not in valid_fragments(target):
                    broken.append((str(source.relative_to(ROOT)), candidate, "fragment"))
        self.assertEqual([], broken[:25], f"{len(broken)} broken local doc links")

    def test_resource_catalog_links_directly_to_plugin_needed_for_targum(self):
        catalog = (GUIDES / "resources.md").read_text(encoding="utf-8")
        self.assertIn("ETCBC Targum Corpus", catalog)
        self.assertIn("<!-- resource:targum -->", catalog)
        self.assertIn("[Context-Fabric plugin](plugins/context-fabric.md)", catalog)

    def test_five_real_researcher_walkthroughs_record_cognitive_cost(self):
        self.assertTrue(WALK.is_file())
        body = WALK.read_text(encoding="utf-8")
        headings = re.findall(r"^## [1-5]\. (.+)$", body, flags=re.MULTILINE)
        self.assertEqual(5, len(headings))
        for topic in ("Targum", "BHSA", "Perseus", "Sefaria", "cost"):
            self.assertIn(topic.lower(), body.lower())
        sections = re.split(r"^## [1-5]\. (.+)$", body, flags=re.MULTILINE)
        for idx in range(1, len(sections) - 1, 2):
            with self.subTest(route=sections[idx]):
                route = sections[idx + 1]
                for label in ("**Shortest path:**", "**Observed route:**", "**Clicks:**",
                              "**Recall burden:**", "**Wrong turns:**",
                              "**Answer without raw YAML/source:**"):
                    self.assertIn(label, route)
                self.assertIn("Yes", route)
        for bad in ("registry/resources.yaml", "registry/plugins.yaml",
                    "scripts/generate_plugin_docs.py"):
            self.assertNotIn("](" + bad, body)
        self.assertIn("[Cognitive walkthroughs](cognitive-walkthroughs.md)",
                      (GUIDES / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
