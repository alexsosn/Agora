import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
USER_GUIDE = ROOT / "wiki" / "guides" / "README.md"


class UserDocumentationLandingTests(unittest.TestCase):
    def test_readme_prominently_links_researcher_user_guide(self):
        readme = README.read_text(encoding="utf-8")
        link = "[Researcher user guide](wiki/guides/README.md)"
        self.assertIn(link, readme)
        self.assertLess(
            readme.index(link),
            readme.index("## Installation"),
            "The researcher guide should be visible before installation details.",
        )

    def test_user_guide_exposes_required_goal_exits(self):
        guide = USER_GUIDE.read_text(encoding="utf-8")
        required_labels = (
            "Get started",
            "Browse plugins",
            "Browse resources",
            "Research tutorials / recipes",
            "Compatibility",
            "Troubleshooting",
        )
        for label in required_labels:
            self.assertIn(label, guide)

    def test_user_guide_repository_local_links_resolve(self):
        guide = USER_GUIDE.read_text(encoding="utf-8")
        destinations = re.findall(r"\[[^\]]+\]\(([^)]+)\)", guide)
        self.assertTrue(destinations, "Expected the landing page to contain links.")

        broken = []
        for destination in destinations:
            if destination.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path = destination.split("#", 1)[0]
            if not path:
                continue
            resolved = (USER_GUIDE.parent / path).resolve()
            if not resolved.exists():
                broken.append(destination)

        self.assertEqual([], broken, f"Broken repository-local links: {broken}")


if __name__ == "__main__":
    unittest.main()
