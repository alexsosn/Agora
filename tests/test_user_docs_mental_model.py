import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
USER_GUIDE = ROOT / "wiki" / "guides" / "README.md"


def _section(markdown: str, heading: str) -> str:
    marker = f"## {heading}"
    start = markdown.index(marker) + len(marker)
    match = re.search(r"^##\s+", markdown[start:], flags=re.MULTILINE)
    end = start + match.start() if match else len(markdown)
    return markdown[start:end]


class UserDocumentationMentalModelTests(unittest.TestCase):
    def test_user_guide_has_compact_first_contact_mental_model(self):
        guide = USER_GUIDE.read_text(encoding="utf-8")
        section = _section(guide, "How Agora fits together")

        required = (
            "Agora marketplace",
            "Context-Fabric plugin",
            "Perseus plugin",
            "Sefaria plugin",
            "SEDRA plugin",
            "BHSA",
            "Skill",
        )
        for term in required:
            self.assertIn(term, section)

        self.assertLessEqual(
            len(section.splitlines()),
            30,
            "The first-contact mental model should remain readable in one screen.",
        )

    def test_mental_model_answers_bhsa_and_skill_questions(self):
        guide = USER_GUIDE.read_text(encoding="utf-8")
        section = _section(guide, "How Agora fits together")

        self.assertIn("install Context-Fabric", section)
        self.assertRegex(section, r"BHSA[^\n]*not a plugin")
        self.assertRegex(section, r"Skill[^\n]*(guidance|instructions)")

    def test_mental_model_defers_internal_implementation_terms(self):
        guide = USER_GUIDE.read_text(encoding="utf-8")
        section = _section(guide, "How Agora fits together").lower()

        deferred_terms = (
            "provider",
            "transport",
            "registry",
            "verification check",
            "verification-check",
            "materializer",
            "mcp server",
            "feature module",
            "collection member",
        )
        for term in deferred_terms:
            self.assertNotIn(term, section)

    def test_readme_uses_the_same_top_level_terms(self):
        readme = README.read_text(encoding="utf-8")
        self.assertIn("Agora is a plugin marketplace", readme)
        self.assertIn("Context-Fabric", readme)
        self.assertIn("Text-Fabric corpora", readme)
        self.assertIn("scholarly skills", readme)
        self.assertNotRegex(readme, r"BHSA\s+plugin", "BHSA must not be described as a plugin.")

        first_contact = readme.split("## Verification scope", 1)[0].lower()
        self.assertNotIn(
            "provider",
            first_contact,
            "Provider is implementation vocabulary; defer it until verification/reference material.",
        )


if __name__ == "__main__":
    unittest.main()
