from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)

REQUIRED_REPO_SKILLS = {
    "agora-plugin-integration": (
        "Would the bug or missing capability still exist",
        "Do not create a silent compatibility shim",
    ),
    "agora-plugin-review": (
        "first review question is architectural ownership",
        "Do not let implementation effort already invested",
    ),
    "agora-pr-review": (
        "CONTRIBUTING.md",
        "Do not invent contribution requirements",
        "agora-plugin-review",
    ),
}


class RepositoryMaintenanceSkillTests(unittest.TestCase):
    def test_plugin_boundary_is_normative_and_linked_from_agent_instructions(self):
        boundary = ROOT / "wiki" / "architecture" / "ref-plugin-boundary.md"
        agents = ROOT / "AGENTS.md"

        self.assertTrue(boundary.is_file())
        self.assertTrue(agents.is_file())

        boundary_text = boundary.read_text(encoding="utf-8")
        agents_text = agents.read_text(encoding="utf-8")
        self.assertIn("Status: normative architecture reference", boundary_text)
        self.assertIn("If removing Agora", boundary_text)
        self.assertIn("ref-plugin-boundary.md", agents_text)

    def test_required_repository_maintenance_skills_exist_and_encode_boundary(self):
        for skill_name, required_phrases in REQUIRED_REPO_SKILLS.items():
            path = ROOT / ".agents" / "skills" / skill_name / "SKILL.md"
            self.assertTrue(path.is_file(), f"missing repository skill: {path}")

            text = path.read_text(encoding="utf-8")
            match = FRONTMATTER.match(text)
            self.assertIsNotNone(match, f"missing frontmatter: {path}")
            metadata = yaml.safe_load(match.group(1))
            self.assertEqual(metadata["name"], skill_name)
            self.assertEqual(metadata["license"], "MIT")
            self.assertEqual(metadata["metadata"]["scope"], "repository-maintenance")
            self.assertIn("Use", metadata["description"])

            for phrase in required_phrases:
                self.assertIn(phrase, text)

    def test_pr_review_skill_is_linked_from_agent_instructions(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("agora-pr-review", agents)
        self.assertIn("CONTRIBUTING.md", agents)

    def test_pr_template_requires_scope_ownership_check(self):
        path = ROOT / ".github" / "pull_request_template.md"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("Scope ownership", text)
        self.assertIn("bug or missing capability still exists", text)
        self.assertIn("does not monkey-patch third-party behavior", text)


if __name__ == "__main__":
    unittest.main()
