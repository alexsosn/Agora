"""#314: register a reverse alignment, not a second BHSA or Aleppo corpus."""
from pathlib import Path
import sys
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/context-fabric/src"))

from agora_context_fabric.catalog import Catalog
from agora_context_fabric.resolver import ContextFabricResolver, PreparedCorpus

MODULE = "bhsa-aleppo-alignment"
ALEPPO_PIN = "db38ddc918fd5d6e47a118f24545bd925975a597"
BHSA_PIN = "4db00e2157915495e1a4d3d57e41223df24775da"


class BhsaAleppoAlignment314Tests(unittest.TestCase):
    def test_exact_optional_module_metadata_and_provenance(self):
        registry = yaml.safe_load((ROOT / "registry/feature-modules.yaml").read_text())
        rows = [row for row in registry["resources"] if row["id"] == MODULE]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["kind"], "feature-module")
        self.assertEqual(row["parent"], "bhsa")
        self.assertEqual(row["compatibility"]["parent_versions"], ["2021"])
        self.assertEqual(row["module"]["status"], "optional")
        self.assertEqual(row["upstream"]["repository"], "MartijnNaaijer/aleppo")
        self.assertEqual(row["upstream"]["ref"], ALEPPO_PIN)
        self.assertEqual(row["upstream"]["tf_path"], "tf/bhsa-mapping/2021")
        self.assertIn(
            {"repository": "ETCBC/bhsa", "ref": BHSA_PIN, "role": "parent-base"},
            row["upstream"]["dependencies"],
        )
        self.assertEqual(row["licenses"]["data"], "CC-BY-SA-4.0")
        self.assertIn("מקרא על פי המסורה", row["licenses"]["notes"])
        self.assertEqual(row["verification"]["status"], "community")

    def test_parent_pin_does_not_narrow_versions_and_native_aleppo_is_unchanged(self):
        resources = yaml.safe_load((ROOT / "registry/resources.yaml").read_text())
        by_id = {row["id"]: row for row in resources["resources"]}
        parent = by_id["bhsa"]
        self.assertEqual(parent["upstream"]["repository"], "ETCBC/bhsa")
        self.assertEqual(parent["upstream"]["ref"], BHSA_PIN)
        self.assertNotIn("tf_path", parent["upstream"])
        self.assertEqual(parent["licenses"]["data"], "CC-BY-NC-4.0")
        self.assertEqual(by_id["aleppo"]["kind"], "corpus")
        self.assertEqual(by_id["aleppo"]["upstream"]["ref"], ALEPPO_PIN)
        self.assertEqual(by_id["aleppo"]["upstream"]["tf_path"], "tf/1.0")
        self.assertNotIn(MODULE, by_id)

    def test_installed_catalog_matches_registry(self):
        original = Catalog.from_registry(ROOT)
        bundled = Catalog.from_plugin_root(ROOT / "plugins/context-fabric")
        for key in ("bhsa", "aleppo", MODULE):
            self.assertEqual(original.get(key), bundled.get(key))

    def test_wrong_parent_version_or_revision_rejected_before_module_acquisition(self):
        from unittest.mock import Mock
        catalog = Catalog.from_registry(ROOT)
        store = Mock()
        resolver = ContextFabricResolver(catalog, store)
        for version, revision in (("1935", BHSA_PIN), ("2021", "a" * 40)):
            with self.subTest(version=version, revision=revision):
                prepared = PreparedCorpus(
                    resource_id="bhsa", member_id=None,
                    logical_name=f"bhsa@{version}", relative_path=f"tf/{version}",
                    path=Path("/unused"), version=version, source_revision=revision,
                )
                with self.assertRaises(ValueError):
                    resolver._prepare_feature_modules(prepared, [MODULE])
        store.ensure_metadata.assert_not_called()
        store.materialize_feature_module.assert_not_called()


if __name__ == "__main__":
    unittest.main()
