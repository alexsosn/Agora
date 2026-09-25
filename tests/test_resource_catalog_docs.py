from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "wiki" / "guides" / "resources.md"
GENERATOR = ROOT / "scripts" / "generate_resource_catalog_docs.py"
USER_GUIDE = ROOT / "wiki" / "guides" / "README.md"


def _yaml(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class ResourceCatalogDocumentationTests(unittest.TestCase):
    def test_generator_and_catalog_exist_and_are_fresh(self):
        self.assertTrue(GENERATOR.is_file(), "Missing generated-catalog script")
        self.assertTrue(CATALOG.is_file(), "Missing generated resource catalog")
        proc = subprocess.run(
            [sys.executable, str(GENERATOR), "--check"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, proc.returncode, proc.stderr or proc.stdout)

    def test_all_registered_resources_have_exact_generated_entries(self):
        resources = _yaml(ROOT / "registry" / "resources.yaml")["resources"]
        catalog = CATALOG.read_text(encoding="utf-8")
        resource_ids = [item["id"] for item in resources]

        # Snapshot the current catalog size while making the source of truth the
        # canonical registry, so a post-1.0 addition cannot disappear silently.
        self.assertEqual(37, len(resource_ids))
        rendered_ids = re.findall(r"<!-- resource:([A-Za-z0-9_.-]+) -->", catalog)
        self.assertEqual(resource_ids, rendered_ids)

    def test_all_registered_feature_modules_are_discoverable_separately(self):
        modules = _yaml(ROOT / "registry" / "feature-modules.yaml")["resources"]
        catalog = CATALOG.read_text(encoding="utf-8")
        self.assertIn("## Annotation modules", catalog)
        for module in modules:
            self.assertEqual(
                1,
                catalog.count(f"<!-- feature-module:{module['id']} -->"),
                f"Expected exactly one module entry for {module['id']}",
            )

    def test_catalog_supports_representative_discovery_tasks(self):
        catalog = CATALOG.read_text(encoding="utf-8")
        for text in (
            "ETCBC Targum Corpus",
            "Aramaic",
            "Nestle 1904 Greek New Testament",
            "SBL Greek New Testament",
            "Biblical studies",
            "Historical load observation",
            "BHSA",
            "TLHdig-TF",
        ):
            self.assertIn(text, catalog)

    def test_catalog_states_evidence_and_rights_boundaries(self):
        catalog = CATALOG.read_text(encoding="utf-8")
        self.assertIn("Integration evidence", catalog)
        self.assertIn("does not certify scholarly quality", catalog)
        self.assertIn("historical measurements", catalog)
        self.assertIn("not requirements or predictions", catalog)
        self.assertIn("component-specific", catalog)
        self.assertIn("member-specific", catalog)
        self.assertIn("unresolved", catalog)

    def test_collections_are_catalogued_without_dumping_member_indexes(self):
        resources = _yaml(ROOT / "registry" / "resources.yaml")["resources"]
        collection_ids = [item["id"] for item in resources if item["kind"] == "collection"]
        catalog = CATALOG.read_text(encoding="utf-8")
        self.assertIn("Collection members are not enumerated on this page", catalog)
        for collection_id in collection_ids:
            self.assertIn(f"<!-- resource:{collection_id} -->", catalog)

        # Snapshot-specific member IDs belong to collection discovery, not the static catalog.
        bible_members = _yaml(ROOT / "registry" / "collections" / "bible.yaml")["members"]
        self.assertTrue(bible_members)
        self.assertNotIn(bible_members[0]["id"], catalog)

    def test_researcher_landing_links_the_catalog(self):
        guide = USER_GUIDE.read_text(encoding="utf-8")
        self.assertIn("[Browse the resource catalog](resources.md)", guide)


if __name__ == "__main__":
    unittest.main()
