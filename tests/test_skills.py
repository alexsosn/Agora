from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

SKILLS = {
    "context-fabric": (
        "context-fabric-research",
        {"list_available_corpora", "list_collection_members", "load_corpus"},
    ),
    "perseus": (
        "perseus-research",
        {"find_author_names", "get_work_resources", "search_perseus"},
    ),
    "sefaria": (
        "sefaria-research",
        {"get_text", "text_search", "get_links_between_texts"},
    ),
    "sedra": (
        "sedra-research",
        {"lookup_word", "get_lexeme"},
    ),
}

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ScholarlySkillTests(unittest.TestCase):
    def test_every_v01_plugin_has_one_portable_research_skill(self):
        for plugin_id, (skill_name, _tools) in SKILLS.items():
            path = ROOT / "plugins" / plugin_id / "skills" / skill_name / "SKILL.md"
            self.assertTrue(path.is_file(), f"missing skill: {path.relative_to(ROOT)}")

    def test_skill_frontmatter_follows_agent_skills_core_contract(self):
        for plugin_id, (skill_name, _tools) in SKILLS.items():
            path = ROOT / "plugins" / plugin_id / "skills" / skill_name / "SKILL.md"
            text = path.read_text(encoding="utf-8")
            match = FRONTMATTER.match(text)
            self.assertIsNotNone(match, f"missing YAML frontmatter: {path}")
            metadata = yaml.safe_load(match.group(1))

            self.assertEqual(metadata["name"], skill_name)
            self.assertRegex(metadata["name"], SKILL_NAME)
            self.assertLessEqual(len(metadata["name"]), 64)
            self.assertIsInstance(metadata["description"], str)
            self.assertGreaterEqual(len(metadata["description"]), 60)
            self.assertLessEqual(len(metadata["description"]), 1024)
            self.assertIn("Use", metadata["description"])
            self.assertEqual(metadata.get("license"), "MIT")

    def test_skills_are_concise_and_reference_real_plugin_tools(self):
        for plugin_id, (skill_name, tools) in SKILLS.items():
            path = ROOT / "plugins" / plugin_id / "skills" / skill_name / "SKILL.md"
            text = path.read_text(encoding="utf-8")
            self.assertLessEqual(len(text.splitlines()), 500)
            for tool in tools:
                self.assertIn(f"`{tool}`", text, f"{path} does not mention {tool}")

    def test_skills_encode_research_safety_invariants(self):
        context_fabric = (
            ROOT / "plugins/context-fabric/skills/context-fabric-research/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Do not assume", context_fabric)
        self.assertIn("resource status", context_fabric.lower())

        perseus = (
            ROOT / "plugins/perseus/skills/perseus-research/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Do not invent URNs", perseus)
        self.assertIn("lemma", perseus.lower())

        sefaria = (
            ROOT / "plugins/sefaria/skills/sefaria-research/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Hebrew/Aramaic", sefaria)
        self.assertIn("reference", sefaria.lower())

        sedra = (
            ROOT / "plugins/sedra/skills/sedra-research/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("word form", sedra.lower())
        self.assertIn("lexeme", sedra.lower())


if __name__ == "__main__":
    unittest.main()
