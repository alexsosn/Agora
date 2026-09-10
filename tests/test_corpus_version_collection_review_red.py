from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from scripts import check_corpus_versions as versions
from scripts import corpus_version_proposal as proposal
from scripts import generate_context_fabric_collection_indexes as collection_generator


OLD = "1" * 40
NEW = "2" * 40


def _collection_resource() -> dict:
    return {
        "id": "fixture-collection",
        "name": "Fixture collection",
        "plugin": "context-fabric",
        "provider": "context-fabric",
        "kind": "collection",
        "languages": ["greek"],
        "disciplines": ["classics"],
        "description": "Synthetic member-index collection.",
        "upstream": {"repository": "example/collection", "ref": OLD},
        "acquisition": {"strategy": "collection", "lazy": True},
        "collection": {
            "discovery": "indexed",
            "member_id_scheme": "stable-relative-id",
            "lazy_members": True,
            "member_index": "registry/collections/fixture-collection.yaml",
        },
        "licenses": {
            "data": "CC-BY-4.0",
            "redistribution": "permitted",
            "evidence": {
                "status": "resolved",
                "checked_at": "2026-09-10",
                "sources": ["https://example.invalid/license"],
            },
        },
        "verification": {
            "status": "verified",
            "evidence": [{"check_id": "resource-load/fixture-collection"}],
        },
        "version_tracking": {
            "discovery": {
                "mode": "github-releases",
                "channel": "stable",
                "tag_pattern": r"^v(?P<version>[0-9]+\.[0-9]+\.[0-9]+)$",
            },
            "dataset": {"mode": "member-index", "ordering": "none"},
            "promotion": {"mode": "proposal"},
            "accepted": {
                "publication_version": "1.0.0",
                "signal": "v1.0.0",
                "source_revision": OLD,
            },
        },
    }


def _registry_text() -> str:
    return f"""schema_version: 1
resources:
- id: fixture-collection
  name: Fixture collection
  plugin: context-fabric
  provider: context-fabric
  kind: collection
  languages: [greek]
  disciplines: [classics]
  description: Synthetic member-index collection. # preserve
  upstream: {{repository: example/collection, ref: {OLD}}}
  acquisition: {{strategy: collection, lazy: true}}
  collection:
    discovery: indexed
    member_id_scheme: stable-relative-id
    lazy_members: true
    member_index: registry/collections/fixture-collection.yaml
  licenses:
    data: CC-BY-4.0
    redistribution: permitted
    evidence: {{status: resolved, checked_at: '2026-09-10', sources: [https://example.invalid/license]}}
  verification:
    status: verified
    evidence:
    - check_id: resource-load/fixture-collection
  version_tracking:
    discovery: {{mode: github-releases, channel: stable, tag_pattern: '^v(?P<version>[0-9]+\\.[0-9]+\\.[0-9]+)$'}}
    dataset: {{mode: member-index, ordering: none}}
    promotion: {{mode: proposal}}
    accepted:
      publication_version: 1.0.0
      signal: v1.0.0
      source_revision: {OLD}
"""


class CollectionPromotionReviewRedTests(unittest.TestCase):
    def test_member_index_candidate_uses_frozen_source_without_scalar_tf_path(self):
        resource = _collection_resource()
        source = versions.SourceCandidate(
            resource_id=resource["id"],
            publication_version="1.1.0",
            signal="v1.1.0",
            source_revision=NEW,
        )

        class NoTfRootApi:
            def list_tf_roots(self, *args, **kwargs):
                raise AssertionError("member-index collection discovery must not invent or select one TF root")

        candidate = versions.discover_dataset_candidate(resource, source, NoTfRootApi())
        self.assertIsNone(candidate.tf_path)
        self.assertEqual(candidate.source_revision, NEW)

    def test_collection_promotion_updates_source_and_accepted_state_without_tf_path(self):
        original = _registry_text()
        parsed = yaml.safe_load(original)
        changed = proposal.apply_promotions_to_text(
            original,
            parsed,
            [
                {
                    "resource_id": "fixture-collection",
                    "previous": {
                        "publication_version": "1.0.0",
                        "signal": "v1.0.0",
                        "source_revision": OLD,
                    },
                    "candidate": {
                        "publication_version": "1.1.0",
                        "signal": "v1.1.0",
                        "source_revision": NEW,
                    },
                    "verification_status": "community",
                }
            ],
        )
        updated = yaml.safe_load(changed)["resources"][0]
        self.assertEqual(updated["upstream"]["ref"], NEW)
        self.assertNotIn("tf_path", updated["upstream"])
        self.assertEqual(
            updated["version_tracking"]["accepted"],
            {
                "publication_version": "1.1.0",
                "signal": "v1.1.0",
                "source_revision": NEW,
            },
        )
        self.assertEqual(updated["verification"], {"status": "community"})
        self.assertIn("description: Synthetic member-index collection. # preserve\n", changed)

    def test_discover_promotions_supports_release_tracked_member_index_collection(self):
        resource = _collection_resource()
        registry = {"schema_version": 1, "resources": [resource]}
        source = versions.SourceCandidate(
            resource_id=resource["id"],
            publication_version="1.1.0",
            signal="v1.1.0",
            source_revision=NEW,
            release_url="https://example.invalid/release/v1.1.0",
        )
        with mock.patch.object(versions, "discover_source_candidate", return_value=source):
            promotions, observations = proposal.discover_promotions(registry, [], api=object())

        self.assertEqual(len(promotions), 1)
        self.assertEqual(promotions[0]["candidate"]["source_revision"], NEW)
        self.assertNotIn("tf_path", promotions[0]["candidate"])
        self.assertEqual(promotions[0]["verification_status"], "community")
        self.assertEqual(observations[0]["resource_kind"], "collection")
        self.assertTrue(observations[0]["member_index"])

    def test_candidate_revision_override_keeps_old_canonical_revision_visible_to_trust_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            member_index = root / "registry" / "collections" / "fixture-collection.yaml"
            member_index.parent.mkdir(parents=True)
            member_index.write_text(
                f"schema_version: 1\ncollection_id: fixture-collection\nsource_revision: {OLD}\nindex_status: complete\nmembers: []\n",
                encoding="utf-8",
            )

            class Resource:
                id = "fixture-collection"
                kind = "collection"
                member_index_path = member_index

            catalog = mock.Mock()
            catalog.get.return_value = Resource()
            generated_index = collection_generator.CollectionIndex(
                collection_id="fixture-collection",
                source_revision=NEW,
                index_status="complete",
                members=(),
            )
            observed_canonical = []

            def preserve(index, canonical_document):
                observed_canonical.append(canonical_document["source_revision"])
                return index

            with (
                mock.patch.object(collection_generator.Catalog, "from_registry", return_value=catalog),
                mock.patch.object(collection_generator, "GitStore"),
                mock.patch.object(collection_generator, "configured_revision", side_effect=AssertionError("override must bypass old configured revision")),
                mock.patch.object(collection_generator, "generate_resource_index", return_value=generated_index) as generate,
                mock.patch.object(collection_generator, "preserve_canonical_verification", side_effect=preserve),
            ):
                documents = collection_generator.generate_documents(
                    root,
                    resource_ids=("fixture-collection",),
                    cache_dir=root / "cache",
                    source_revisions={"fixture-collection": NEW},
                )

            self.assertIn("fixture-collection", documents)
            self.assertEqual(generate.call_args.kwargs["source_revision"], NEW)
            self.assertEqual(observed_canonical, [OLD])

    def test_workflow_regenerates_member_indexes_at_candidate_revision_before_projection(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "corpus-version-updates.yml").read_text(encoding="utf-8")
        collection_generate = workflow.find("generate_context_fabric_collection_indexes.py")
        projection = workflow.find("generate_context_fabric_catalog.py")
        self.assertGreaterEqual(collection_generate, 0, workflow)
        self.assertGreaterEqual(projection, 0, workflow)
        self.assertLess(collection_generate, projection)
        self.assertIn("--source-revision", workflow)
        self.assertIn("registry/collections", workflow)
        self.assertIn("plugins/context-fabric/resources/collections", workflow)


if __name__ == "__main__":
    unittest.main()
