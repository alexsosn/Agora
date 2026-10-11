"""#169 RED: researcher access to existing canonical scholarly skill sections."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from scripts import generate_plugin_docs, generate_resource_catalog_docs

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "wiki/guides/scholarly-guidance.md"
LANDING = ROOT / "wiki/guides/README.md"
RESOURCE_DOC = ROOT / "wiki/guides/resources.md"
PLUGINS = ("context-fabric", "perseus", "sefaria", "sedra")
SKILLS = {
    "context-fabric-research": "context-fabric",
    "bhsa-research": "context-fabric",
    "cuc-ugaritic-research": "context-fabric",
    "greek-collections-research": "context-fabric",
    "tlhdig-hittite-research": "context-fabric",
    "perseus-research": "perseus",
    "sefaria-research": "sefaria",
    "sedra-research": "sedra",
}
LINK = re.compile(r"\]\((?P<path>\.\./\.\./plugins/[^)#]+/SKILL\.md)#(?P<anchor>[^)]+)\)")


def heading_slug(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text).lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s-]+", "-", text).strip("-")


class HumanScholarlyGuidanceContracts(unittest.TestCase):
    def test_user_front_door_links_human_guidance_index(self):
        self.assertTrue(GUIDE.is_file(), "Missing human scholarly guidance index")
        landing = LANDING.read_text(encoding="utf-8")
        self.assertIn("[Scholarly guidance](scholarly-guidance.md)", landing)
        self.assertIn("scholarly-guidance.md", RESOURCE_DOC.read_text(encoding="utf-8"))
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                page = ROOT / "wiki/guides/plugins" / (plugin + ".md")
                body = page.read_text(encoding="utf-8")
                self.assertIn("[human scholarly guidance](../scholarly-guidance.md)", body)

    def test_skill_navigation_targets_exact_existing_headings(self):
        self.assertTrue(GUIDE.is_file(), "Missing scholarly guidance guide")
        guide = GUIDE.read_text(encoding="utf-8")
        self.assertLess(len(guide), 6000, "Do not duplicate complete skill manuals")
        seen = set()
        links = list(LINK.finditer(guide))
        self.assertGreaterEqual(len(links), 18, "Use specific sections, not just raw skill links")
        for match in links:
            target = (GUIDE.parent / match["path"]).resolve()
            with self.subTest(target=str(target), anchor=match["anchor"]):
                self.assertTrue(target.is_relative_to(ROOT / "plugins"))
                self.assertTrue(target.is_file())
                name = target.parent.name
                self.assertIn(name, SKILLS)
                self.assertEqual(target.parent.parent.parent.name, SKILLS[name])
                headings = {
                    heading_slug(line.lstrip("#").strip())
                    for line in target.read_text(encoding="utf-8").splitlines()
                    if re.match(r"^#{1,6}\s", line)
                }
                self.assertIn(match["anchor"], headings)
                seen.add(name)
        self.assertEqual(seen, set(SKILLS))

    def test_bhsa_language_license_and_reproducibility_topics_reachable(self):
        guide = GUIDE.read_text(encoding="utf-8")
        required = {
            "sp-and-pdp-are-not-interchangeable",
            "verbal-analysis", "counting-and-comparison",
            "reproducibility", "license-and-attribution",
        }
        actual = {m["anchor"] for m in LINK.finditer(guide)
                  if "/bhsa-research/" in m["path"]}
        self.assertTrue(required.issubset(actual), required - actual)
        for name in ("cuc-ugaritic-research", "greek-collections-research",
                     "tlhdig-hittite-research"):
            self.assertIn(name + "/SKILL.md#", guide)
        self.assertIn("upstream", guide.lower())
        self.assertIn("agent", guide.lower())

    def test_generated_pages_remain_canonical(self):
        self.assertTrue(generate_plugin_docs.check())
        self.assertTrue(generate_resource_catalog_docs.check())


if __name__ == "__main__":
    unittest.main()
