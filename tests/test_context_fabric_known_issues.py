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


ISSUE_ID = "context-fabric/duplicate-structure-levels"
ISSUE = {
    "id": ISSUE_ID,
    "severity": "blocking",
    "signature": "duplicate-structure-levels",
    "summary": "Some members declare duplicate structureTypes.",
    "upstream": [
        {"repository": "Context-Fabric/context-fabric"},
        {"repository": "pthu/greek_literature"},
    ],
}


class KnownIssueResolver:
    def list_members(self, resource_id: str, *, revision: str | None = None):
        return [
            CollectionMember(
                id="broken-a1b2c3d4",
                resource_id=resource_id,
                relative_path="Greek/Broken/tf/1.0",
                identity_path="Greek/Broken",
                author="Fixture",
                title="Broken",
                verification_known_issues=(ISSUE_ID,),
                source_revision=revision or "a" * 40,
            )
        ]

    def search_members(
        self,
        resource_id: str,
        query: str,
        *,
        revision: str | None = None,
    ):
        return self.list_members(resource_id, revision=revision)


class NoopLoader:
    pass


class KnownIssueDiscoveryTests(unittest.TestCase):
    def make_service(self) -> ContextFabricService:
        resource = ResourceSpec(
            id="greek",
            name="Greek fixture",
            plugin="context-fabric",
            provider="context-fabric",
            kind="collection",
            repository="unused/repository",
            languages=("greek",),
            disciplines=("classics",),
            verification_known_issues=(ISSUE,),
        )
        return ContextFabricService(
            Catalog([resource]),
            KnownIssueResolver(),
            NoopLoader(),
        )

    def test_resource_description_surfaces_structured_known_issue(self):
        described = self.make_service().describe_resource("greek")
        self.assertEqual(described["verification"]["known_issues"], [ISSUE])

    def test_member_listing_resolves_compact_issue_reference(self):
        page = self.make_service().list_collection_members("greek", limit=10)
        self.assertEqual(page["items"][0]["verification"]["known_issues"], [ISSUE])


if __name__ == "__main__":
    unittest.main()
