from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_SKILLS = {
    "context-fabric": {
        "context-fabric-research": {
            "list_available_corpora",
            "list_collection_members",
            "load_corpus",
        },
        "bhsa-research": {"load_corpus"},
        "cuc-ugaritic-research": {"load_corpus"},
        "tlhdig-hittite-research": {"load_corpus"},
        "greek-collections-research": {"list_collection_members", "load_corpus"},
    },
    "perseus": {
        "perseus-research": {
            "find_author_names",
            "get_work_resources",
            "search_perseus",
        },
    },
    "sefaria": {
        "sefaria-research": {"get_text", "text_search", "get_links_between_texts"},
    },
    "sedra": {
        "sedra-research": {"lookup_word", "get_lexeme"},
    },
}

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def skill_path(plugin_id: str, skill_name: str) -> Path:
    return ROOT / "plugins" / plugin_id / "skills" / skill_name / "SKILL.md"


def skill_ui_path(plugin_id: str, skill_name: str) -> Path:
    return (
        ROOT
        / "plugins"
        / plugin_id
        / "skills"
        / skill_name
        / "agents"
        / "openai.yaml"
    )


def all_skill_paths() -> list[Path]:
    return sorted((ROOT / "plugins").glob("*/skills/*/SKILL.md"))


class ScholarlySkillTests(unittest.TestCase):
    def test_required_v01_research_skills_exist(self):
        for plugin_id, skills in REQUIRED_SKILLS.items():
            for skill_name in skills:
                path = skill_path(plugin_id, skill_name)
                self.assertTrue(path.is_file(), f"missing skill: {path.relative_to(ROOT)}")

    def test_every_committed_skill_follows_agent_skills_core_contract(self):
        paths = all_skill_paths()
        self.assertTrue(paths, "no plugin skills were discovered")

        for path in paths:
            text = path.read_text(encoding="utf-8")
            match = FRONTMATTER.match(text)
            self.assertIsNotNone(match, f"missing YAML frontmatter: {path}")
            metadata = yaml.safe_load(match.group(1))

            self.assertIsInstance(metadata, dict, f"invalid frontmatter: {path}")
            skill_name = path.parent.name
            self.assertEqual(metadata["name"], skill_name)
            self.assertRegex(metadata["name"], SKILL_NAME)
            self.assertLessEqual(len(metadata["name"]), 64)
            self.assertIsInstance(metadata["description"], str)
            self.assertGreaterEqual(len(metadata["description"]), 60)
            self.assertLessEqual(len(metadata["description"]), 1024)
            self.assertIn("Use", metadata["description"])
            self.assertEqual(metadata.get("license"), "MIT")
            self.assertLessEqual(len(text.splitlines()), 500)

    def test_every_required_skill_has_codex_ui_metadata(self):
        for plugin_id, skills in REQUIRED_SKILLS.items():
            for skill_name in skills:
                path = skill_ui_path(plugin_id, skill_name)
                self.assertTrue(
                    path.is_file(), f"missing Codex skill metadata: {path.relative_to(ROOT)}"
                )
                document = yaml.safe_load(path.read_text(encoding="utf-8"))
                self.assertEqual(set(document), {"interface"})
                interface = document["interface"]
                self.assertEqual(
                    set(interface),
                    {"display_name", "short_description", "default_prompt"},
                )
                self.assertIsInstance(interface["display_name"], str)
                self.assertGreaterEqual(len(interface["display_name"]), 3)
                self.assertIsInstance(interface["short_description"], str)
                self.assertGreaterEqual(len(interface["short_description"]), 20)
                self.assertLessEqual(len(interface["short_description"]), 120)
                self.assertIn(f"${skill_name}", interface["default_prompt"])

    def test_required_skills_reference_their_real_plugin_tools(self):
        for plugin_id, skills in REQUIRED_SKILLS.items():
            for skill_name, tools in skills.items():
                path = skill_path(plugin_id, skill_name)
                text = path.read_text(encoding="utf-8")
                for tool in tools:
                    self.assertIn(f"`{tool}`", text, f"{path} does not mention {tool}")

    def test_provider_skills_encode_research_safety_invariants(self):
        context_fabric = skill_path(
            "context-fabric", "context-fabric-research"
        ).read_text(encoding="utf-8")
        self.assertIn("Do not assume", context_fabric)
        self.assertIn("resolved upstream source revision", context_fabric.lower())

        perseus = skill_path("perseus", "perseus-research").read_text(
            encoding="utf-8"
        )
        self.assertIn("Do not invent URNs", perseus)
        self.assertIn("lemma", perseus.lower())

        sefaria = skill_path("sefaria", "sefaria-research").read_text(
            encoding="utf-8"
        )
        self.assertIn("Hebrew/Aramaic", sefaria)
        self.assertIn("reference", sefaria.lower())

        sedra = skill_path("sedra", "sedra-research").read_text(encoding="utf-8")
        self.assertIn("word form", sedra.lower())
        self.assertIn("lexeme", sedra.lower())

    def test_context_fabric_corpus_skills_preserve_source_specific_invariants(self):
        bhsa = skill_path("context-fabric", "bhsa-research").read_text(
            encoding="utf-8"
        )
        for feature in ("`sp`", "`vt`", "`vs`", "`pdp`", "`function`"):
            self.assertIn(feature, bhsa)
        self.assertIn("CC BY-NC 4.0", bhsa)

        cuc = skill_path("context-fabric", "cuc-ugaritic-research").read_text(
            encoding="utf-8"
        )
        for feature in ("`g_cons`", "`emen`", "`cert`", "`alt`"):
            self.assertIn(feature, cuc)
        self.assertIn("`source_revision`", cuc)
        self.assertIn("upstream documentation", cuc.lower())

        tlhdig = skill_path("context-fabric", "tlhdig-hittite-research").read_text(
            encoding="utf-8"
        )
        self.assertIn("`source_revision`", tlhdig)
        self.assertIn("upstream documentation", tlhdig.lower())
        self.assertIn("0.1.0", tlhdig)

        greek = skill_path("context-fabric", "greek-collections-research").read_text(
            encoding="utf-8"
        )
        self.assertIn("resolved upstream source revision", greek)
        self.assertIn("Perseus", greek)
        self.assertIn("Open Greek and Latin", greek)


if __name__ == "__main__":
    unittest.main()
