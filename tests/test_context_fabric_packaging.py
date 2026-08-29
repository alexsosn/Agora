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
from scripts.generate_context_fabric_catalog import build_catalog_document, catalog_text


class ContextFabricPackagingTests(unittest.TestCase):
    def test_installed_plugin_catalog_contains_exact_v01_scope(self):
        catalog = Catalog.from_plugin_root(PLUGIN_ROOT)
        with (ROOT / "registry" / "v0.1.yaml").open("r", encoding="utf-8") as fh:
            scope = yaml.safe_load(fh)
        self.assertEqual(catalog.ids(), scope["required_resources"])
        self.assertEqual(len(catalog.ids()), 36)

    def test_bundled_catalog_is_a_fresh_projection_of_registry(self):
        expected = catalog_text(build_catalog_document(ROOT))
        actual = (PLUGIN_ROOT / "resources" / "catalog.yaml").read_text(encoding="utf-8")
        self.assertEqual(actual, expected)

    def test_bundled_catalog_preserves_collection_metadata(self):
        catalog = Catalog.from_plugin_root(PLUGIN_ROOT)
        for resource_id in ("bible", "patristics", "greek_literature"):
            resource = catalog.get(resource_id)
            self.assertEqual(resource.kind, "collection")
            self.assertIsNotNone(resource.member_index)


if __name__ == "__main__":
    unittest.main()
