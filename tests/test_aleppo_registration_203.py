"""#203 RED: integrate the actual published Aleppo 1.0 Text-Fabric corpus.

Primary data audited at MartijnNaaijer/aleppo@db38ddc918fd5d6e47a118f24545bd925975a597:
otype.tf has 426562 word slots; otext.tf cites Hebrew Wikisource,
CC BY-SA 4.0, and explicitly warns of the lost-codex supplied passages.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "plugins/context-fabric/src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agora_context_fabric.catalog import Catalog
from scripts.generate_context_fabric_catalog import build_catalog_document, check

PIN = "db38ddc918fd5d6e47a118f24545bd925975a597"


class AleppoNativeCorpusRegistration203Tests(unittest.TestCase):
    def setUp(self):
        doc = yaml.safe_load((ROOT / "registry/resources.yaml").read_text(encoding="utf-8"))
        self.rows = [row for row in doc["resources"] if row["id"] == "aleppo"]
        self.canonical = Catalog.from_registry(ROOT)
        self.bundled = Catalog.from_plugin_root(ROOT / "plugins/context-fabric")

    def test_single_version_pinned_native_corpus_registration(self):
        self.assertEqual(1, len(self.rows))
        row = self.rows[0]
        resource = self.canonical.get("aleppo")
        self.assertEqual(resource, self.bundled.get("aleppo"))
        self.assertEqual(resource.kind, "corpus")
        self.assertEqual(resource.plugin, "context-fabric")
        self.assertEqual(resource.provider, "context-fabric")
        self.assertEqual(resource.repository, "MartijnNaaijer/aleppo")
        self.assertEqual(resource.ref, PIN)
        self.assertEqual(resource.tf_path, "tf/1.0")
        self.assertEqual(resource.acquisition_strategy, "repository")
        self.assertIsNone(resource.release_archive)
        self.assertEqual(resource.verification_status, "community")
        self.assertEqual(row["acquisition"]["lazy"], True)
        self.assertEqual(row["upstream"]["ref"], PIN)
        self.assertEqual(row["upstream"]["tf_path"], "tf/1.0")
        self.assertFalse(row.get("collection"))
        self.assertFalse(row.get("materializer"))

    def test_upstream_rights_lost_sections_and_alignment_are_not_misstated(self):
        row = self.rows[0]
        self.assertIn("hebrew", row["languages"])
        self.assertIn("biblical-studies", row["disciplines"])
        self.assertEqual(row["licenses"]["data"], "CC-BY-SA-4.0")
        self.assertEqual(row["licenses"]["evidence"]["status"], "resolved")
        self.assertEqual(row["licenses"]["redistribution"], "permitted")
        license_text = " ".join((
            row["licenses"]["notes"], row["description"],
            *row["verification"]["notes"],
        )).lower()
        for phrase in (
            "hebrew wikisource", "sharealike", "aleppo_extant",
            "lost", "bhsa 2021", "verse",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, license_text)
        self.assertNotEqual(row["verification"]["status"], "verified")
        evidence = " ".join(row["licenses"]["evidence"]["sources"])
        self.assertIn("/blob/" + PIN + "/tf/1.0/otext.tf", evidence)

    def test_schema_bundled_projection_and_no_reverse_module_shortcut(self):
        row = self.rows[0]
        schema = json.loads((ROOT / "registry/schema/resources.schema.json").read_text())
        self.assertEqual([], list(Draft202012Validator(schema).iter_errors({
            "schema_version": 1, "resources": [row],
        })))
        generated = build_catalog_document(ROOT)
        bundled = yaml.safe_load((
            ROOT / "plugins/context-fabric/resources/catalog.yaml"
        ).read_text(encoding="utf-8"))
        self.assertEqual(generated, bundled)
        self.assertEqual(1, sum(1 for item in generated["resources"] if item["id"] == "aleppo"))
        self.assertFalse(check(ROOT), "generated runtime catalog must be fresh")
        modules = yaml.safe_load((ROOT / "registry/feature-modules.yaml").read_text())
        self.assertFalse(any(
            item.get("id") == "aleppo" or item.get("upstream", {}).get("repository") == "MartijnNaaijer/aleppo"
            for item in modules["resources"]
        ), "reverse BHSA 2021 projection needs a separate alignment contract")
        mats = yaml.safe_load((ROOT / "registry/materializers.yaml").read_text())
        self.assertFalse(any(item.get("id") == "aleppo" for item in mats["plugins"]))
        self.assertNotIn("aleppo", yaml.safe_load((ROOT / "registry/v0.1.yaml").read_text())["required_resources"])


if __name__ == "__main__":
    unittest.main()
