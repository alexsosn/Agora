import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
USER_GUIDE = ROOT / "wiki" / "guides" / "README.md"


def _github_heading_slug(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text)
    return text.strip("-")


def _heading_slugs(path: Path) -> set[str]:
    slugs = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if match:
            slugs.add(_github_heading_slug(match.group(1)))
    return slugs


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

    def test_user_guide_repository_local_links_and_fragments_resolve(self):
        guide = USER_GUIDE.read_text(encoding="utf-8")
        destinations = re.findall(r"\[[^\]]+\]\(([^)]+)\)", guide)
        self.assertTrue(destinations, "Expected the landing page to contain links.")

        broken = []
        for destination in destinations:
            if destination.startswith(("http://", "https://", "mailto:")):
                continue

            if destination.startswith("#"):
                target = USER_GUIDE
                fragment = destination[1:]
            else:
                path_text, separator, fragment = destination.partition("#")
                target = (USER_GUIDE.parent / path_text).resolve()
                if not target.exists():
                    broken.append(destination)
                    continue
                if not separator:
                    fragment = ""

            if fragment and fragment not in _heading_slugs(target):
                broken.append(destination)

        self.assertEqual([], broken, f"Broken repository-local links/fragments: {broken}")


if __name__ == "__main__":
    unittest.main()
