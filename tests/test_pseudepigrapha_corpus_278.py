"""#278 RED: the discoverable Pseudepigrapha prebuilt corpus uses published TF 1.1.

Separate from the Python converter/materializer contract and legacy v0.1
scope. Checked primary GitHub Releases asset digest on 2026-10-12.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CORPUS_ID = "pseudepigrapha"
COMMIT = "39bd9fb895d1201e9cd9260170512fd8c399a3ac"
ZIP_SHA = "88f23ac9106c6ea8b35f89b19d760cf5d4ee544a3f8d8262d6ed7e2092e447e9"
PIN = {
    "release_tag": "v1.1.0",
    "asset_name": "tf-1.1.zip",
    "sha256": ZIP_SHA,
    "compressed_bytes": 9_632_817,
    "version": "1.1",
}


class PseudepigraphaCorpusMigration278Tests(unittest.TestCase):
    def test_current_default_is_exact_released_data_not_converter(self):
        doc = yaml.safe_load((ROOT / "registry/resources.yaml").read_text())
        row = next(r for r in doc["resources"] if r["id"] == CORPUS_ID)
        self.assertEqual(row["kind"], "corpus")
        self.assertEqual(row["plugin"], "context-fabric")
        self.assertEqual(row["upstream"]["repository"], "alexsosn/Pseudepigrapha-TF")
        self.assertEqual(row["upstream"]["ref"], COMMIT)
        self.assertEqual(row["acquisition"]["strategy"], "github-release-archive")
        self.assertTrue(row["acquisition"]["lazy"])
        self.assertEqual(row["acquisition"]["archive"], PIN)
        self.assertEqual(row["licenses"]["data"], "CC-BY-4.0")
        self.assertEqual(row["licenses"]["redistribution"], "permitted")
        self.assertEqual(row["licenses"]["evidence"]["status"], "resolved")
        license_sources = " ".join(row["licenses"]["evidence"]["sources"])
        self.assertIn("/blob/v1.1.0/DATA_LICENSE.md", license_sources)
        self.assertIn("c939dcbacad78c5d18d2c4282cad23c47e19ac07", license_sources)
        self.assertIn("/releases/tag/v1.1.0", row["source_snapshot"]["source"])
        self.assertIn("source_ref", " ".join(row["verification"]["notes"]))
        materializers = yaml.safe_load((ROOT / "registry/materializers.yaml").read_text())
        installer = next(x for x in materializers["plugins"] if x["id"] == "pseudepigrapha-tf")
        self.assertEqual(installer["ref"], COMMIT)
        self.assertEqual(installer["version"], "1.1.0")
        self.assertNotIn("materializer", row)

    def test_packaged_catalog_preserves_exact_pinned_asset(self):
        from scripts.generate_context_fabric_catalog import build_catalog_document
        catalog = build_catalog_document(ROOT)
        packaged = yaml.safe_load((ROOT / "plugins/context-fabric/resources/catalog.yaml").read_text())
        self.assertEqual(catalog, packaged)
        row = next(x for x in catalog["resources"] if x["id"] == CORPUS_ID)
        self.assertEqual(row["acquisition"]["archive"], PIN)
        frozen = yaml.safe_load((ROOT / "registry/v0.1.yaml").read_text())
        self.assertNotIn(CORPUS_ID, frozen["required_resources"])

    def test_native_consumer_requires_real_download_and_offline_reopen(self):
        smoke = (ROOT / "scripts/smoke_pseudepigrapha_release_226.py").read_text()
        workflow = (ROOT / ".github/workflows/pseudepigrapha-registered-corpus.yml").read_text()
        self.assertIn(ZIP_SHA, smoke)
        self.assertIn(COMMIT, smoke)
        self.assertIn('== "1.1"', smoke)
        self.assertIn('source_mode="require-fresh"', smoke)
        self.assertIn('source_mode="offline"', smoke)
        self.assertIn('"1En__Ethiopic"', smoke)
        self.assertIn("witness", smoke)
        self.assertIn("generated_translation", smoke)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("smoke_pseudepigrapha_release_226.py", workflow)


if __name__ == "__main__":
    unittest.main()
