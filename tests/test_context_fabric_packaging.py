from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "context-fabric"
PLUGIN_SRC = PLUGIN_ROOT / "src"
sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog
from scripts.generate_context_fabric_catalog import (
    build_catalog_document,
    build_feature_modules_document,
)


class ContextFabricPackagingTests(unittest.TestCase):
    def test_installed_plugin_catalog_contains_v01_scope_and_modules(self):
        catalog = Catalog.from_plugin_root(PLUGIN_ROOT)
        with (ROOT / "registry" / "v0.1.yaml").open("r", encoding="utf-8") as fh:
            scope = yaml.safe_load(fh)
        self.assertTrue(set(scope["required_resources"]).issubset(catalog.ids()))
        self.assertEqual(len(catalog.search(kind="feature-module")), 21)

    def test_bundled_catalog_is_a_lossless_projection_of_registry(self):
        expected = build_catalog_document(ROOT)
        with (PLUGIN_ROOT / "resources" / "catalog.yaml").open("r", encoding="utf-8") as fh:
            actual = yaml.safe_load(fh)
        self.assertEqual(actual, expected)

        expected_modules = build_feature_modules_document(ROOT)
        with (PLUGIN_ROOT / "resources" / "feature-modules.yaml").open("r", encoding="utf-8") as fh:
            actual_modules = yaml.safe_load(fh)
        self.assertEqual(actual_modules, expected_modules)

    def test_bundled_catalog_preserves_collection_metadata(self):
        catalog = Catalog.from_plugin_root(PLUGIN_ROOT)
        for resource_id in ("bible", "patristics", "greek_literature"):
            resource = catalog.get(resource_id)
            self.assertEqual(resource.kind, "collection")
            self.assertIsNotNone(resource.member_index)

    def test_bundled_catalog_preserves_feature_module_metadata(self):
        resource = Catalog.from_plugin_root(PLUGIN_ROOT).get("bhsa-cantillation-trees")
        self.assertEqual(resource.parent, "bhsa")
        self.assertEqual(resource.parent_versions, ("2021",))
        self.assertEqual(resource.module_path, "alexsosn/BHSA-cantillation-trees/tf")
        self.assertEqual(resource.tf_path, "tf/2021")
        self.assertEqual(resource.dependencies[0]["repository"], "openscriptures/morphhb")

    def test_bundled_catalog_preserves_resource_integration_metadata(self):
        resource = Catalog.from_plugin_root(PLUGIN_ROOT).get("TLHdig-TF")
        self.assertEqual(resource.verification_status, "community")
        self.assertEqual(resource.licenses["data"], "upstream-dependent")
        self.assertEqual(resource.integration_issues, ())
        self.assertEqual(resource.source_snapshot["source"], "alexsosn/TLHdig-TF")


if __name__ == "__main__":
    unittest.main()
