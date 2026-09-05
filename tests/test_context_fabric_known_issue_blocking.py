from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog, ResourceSpec
from agora_context_fabric.collection_index import CollectionIndex, CollectionIndexMember
from agora_context_fabric.resolver import ContextFabricResolver


REVISION = "a" * 40
ISSUE_ID = "context-fabric/duplicate-structure-levels"


def issue(severity: str) -> dict[str, str]:
    return {
        "id": ISSUE_ID,
        "severity": severity,
        "signature": "duplicate-structure-levels",
        "summary": "Some members declare duplicate structureTypes.",
    }


def resource(*, severity: str) -> ResourceSpec:
    return ResourceSpec(
        id="greek",
        name="Greek fixture",
        plugin="context-fabric",
        provider="context-fabric",
        kind="collection",
        repository="unused/repository",
        languages=("greek",),
        disciplines=("classics",),
        verification_known_issues=(issue(severity),),
    )


def index() -> CollectionIndex:
    return CollectionIndex(
        collection_id="greek",
        source_revision=REVISION,
        index_status="complete",
        members=(
            CollectionIndexMember(
                id="broken-a1b2c3d4",
                path="Greek/Broken",
                tf_path="Greek/Broken/tf/1.0",
                languages=("greek",),
                verification_known_issues=(ISSUE_ID,),
            ),
        ),
    )


class RecordingStore:
    def __init__(self) -> None:
        self.materialize_calls: list[tuple[Path, str, str]] = []

    def materialize(self, repo: Path, path: str, revision: str) -> Path:
        self.materialize_calls.append((repo, path, revision))
        return Path("/tmp/agora-known-issue-fixture")


class StaticIndexResolver(ContextFabricResolver):
    def __init__(self, catalog: Catalog, store: RecordingStore) -> None:
        super().__init__(catalog, store)  # type: ignore[arg-type]
        self.static_index = index()

    def _collection_repo(self, resource, source_revision):
        return Path("/unused/repository"), REVISION

    def _collection_index(self, resource, repo, revision, *, requested_revision):
        return self.static_index


class KnownIssueBlockingTests(unittest.TestCase):
    def test_blocking_member_is_rejected_before_materialization(self):
        store = RecordingStore()
        resolver = StaticIndexResolver(Catalog([resource(severity="blocking")]), store)

        with self.assertRaisesRegex(
            ValueError,
            r"known blocking issue.*context-fabric/duplicate-structure-levels",
        ):
            resolver.prepare("greek", member_id="broken-a1b2c3d4")

        self.assertEqual(store.materialize_calls, [])

    def test_advisory_member_remains_materializable(self):
        store = RecordingStore()
        resolver = StaticIndexResolver(Catalog([resource(severity="advisory")]), store)

        prepared = resolver.prepare("greek", member_id="broken-a1b2c3d4")

        self.assertEqual(prepared.member_id, "broken-a1b2c3d4")
        self.assertEqual(
            store.materialize_calls,
            [(Path("/unused/repository"), "Greek/Broken/tf/1.0", REVISION)],
        )


if __name__ == "__main__":
    unittest.main()
