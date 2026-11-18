"""#304: active researcher-facing Pseudepigrapha native archive identity matches registry."""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from scripts import generate_plugin_docs

ROOT = Path(__file__).resolve().parents[1]
HEADING = "## Published Online Critical Pseudepigrapha (Pseudepigrapha-TF)"


class PseudepigraphaResearcherGuide304Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = yaml.safe_load(
            (ROOT / "registry/resources.yaml").read_text(encoding="utf-8")
        )["resources"]
        cls.resource = next(row for row in rows if row["id"] == "pseudepigrapha")
        cls.guide = (
            ROOT / "wiki/guides/plugins/context-fabric.md"
        ).read_text(encoding="utf-8")
        cls.section = cls.guide.split(HEADING, 1)[1].split("\n## ", 1)[0]

    def test_registered_archive_version_and_source_links_are_current(self):
        resource = self.resource
        archive = resource["acquisition"]["archive"]
        release = archive["release_tag"]
        repository = resource["upstream"]["repository"]
        self.assertEqual(archive["version"], "1.1")
        self.assertEqual(resource["verification"]["status"], "community")
        self.assertIn(f"**{archive['version']}**", self.section)
        self.assertIn(f"[Pseudepigrapha-TF {release}]", self.section)
        self.assertIn(
            f"https://github.com/{repository}/releases/tag/{release}",
            self.section,
        )
        self.assertIn(f"`{archive['asset_name']}`", self.section)
        self.assertIn(f"{repository}/blob/{release}/DATA_LICENSE.md", self.section)
        self.assertIn(
            f"{repository}/blob/{release}/docs/features/0_home.md",
            self.section,
        )
        for outdated in ("v1.0.0", "tf-1.0.zip", "**1.0**"):
            self.assertNotIn(outdated, self.section)

    def test_verification_and_local_corpus_boundary_are_not_overstated(self):
        self.assertIn("**community**", self.section)
        self.assertIn("Agora", self.section)
        self.assertIn("end-to-end", self.section)
        self.assertIn("offline", self.section)
        self.assertIn("`pseudepigrapha-tf` materializer", self.section)
        self.assertIn("not historical manuscript witnesses", self.section)

    def test_generated_page_matches_canonical_generator(self):
        self.assertTrue(generate_plugin_docs.check())


if __name__ == "__main__":
    unittest.main()
