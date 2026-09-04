from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog, ResourceSpec
from agora_context_fabric.resolver import CollectionMember
from agora_context_fabric.service import ContextFabricService


class LegacyResolver:
    def list_members(self, resource_id: str):
        return [
            CollectionMember(
                id="member-a",
                resource_id=resource_id,
                relative_path="Homer/Iliad/tf/1.0",
                identity_path="Homer/Iliad",
                author="Homer",
                title="Iliad",
            )
        ]

    def search_members(self, resource_id: str, _query: str):
        return self.list_members(resource_id)


class NoopLoader:
    pass


class CollectionSnapshotFailClosedTests(unittest.TestCase):
    def setUp(self):
        collection = ResourceSpec(
            id="greek",
            name="Greek fixture",
            plugin="context-fabric",
            provider="context-fabric",
            kind="collection",
            repository="unused/repository",
            languages=("greek",),
            disciplines=("classics",),
        )
        self.service = ContextFabricService(
            Catalog([collection]),
            LegacyResolver(),
            NoopLoader(),
        )

    def test_supplied_revision_is_never_echoed_if_resolver_cannot_honor_it(self):
        revision = "a" * 40
        with self.assertRaisesRegex(RuntimeError, "cannot honor collection source_revision"):
            self.service.list_collection_members(
                "greek",
                source_revision=revision,
            )

    def test_legacy_no_token_discovery_remains_usable_without_false_revision(self):
        result = self.service.list_collection_members("greek")
        self.assertIsNone(result["source_revision"])
        self.assertEqual([item["id"] for item in result["items"]], ["member-a"])


if __name__ == "__main__":
    unittest.main()
