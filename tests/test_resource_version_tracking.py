from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts import validate_registry as registry_validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "registry/schema/resources.schema.json").read_text(encoding="utf-8"))
COMMIT = "1" * 40
OTHER_COMMIT = "2" * 40


def _resource(*, kind: str = "corpus") -> dict:
    resource = {
        "id": "example-corpus" if kind == "corpus" else "example-collection",
        "name": "Example resource",
        "plugin": "context-fabric",
        "provider": "context-fabric",
        "kind": kind,
        "languages": ["greek"],
        "disciplines": ["classics"],
        "description": "Synthetic resource for version-tracking contract tests.",
        "upstream": {
            "repository": "example/corpus",
            "ref": COMMIT,
            **({"tf_path": "tf/1.2.3"} if kind == "corpus" else {}),
        },
        "acquisition": {
            "strategy": "repository" if kind == "corpus" else "collection",
            "lazy": True,
        },
        "licenses": {
            "data": "CC-BY-4.0",
            "redistribution": "permitted",
            "evidence": {
                "status": "resolved",
                "checked_at": "2026-09-09",
                "sources": ["https://example.org/license"],
            },
        },
        "verification": {"status": "community"},
    }
    if kind == "collection":
        resource["collection"] = {
            "discovery": "indexed",
            "member_id_scheme": "stable-relative-id",
            "lazy_members": True,
            "member_index": "registry/collections/example.yaml",
        }
    return resource


def _proposal_tracking() -> dict:
    return {
        "discovery": {
            "mode": "github-releases",
            "channel": "stable",
            "tag_pattern": "^v(?P<version>[0-9]+\\.[0-9]+\\.[0-9]+)$",
        },
        "dataset": {
            "mode": "release-version-match",
            "root": "tf",
            "ordering": "semver",
        },
        "promotion": {"mode": "proposal"},
        "accepted": {
            "publication_version": "1.2.3",
            "signal": "v1.2.3",
            "source_revision": COMMIT,
            "tf_path": "tf/1.2.3",
        },
    }


def _schema_errors(resource: dict) -> list[str]:
    document = {"schema_version": 1, "resources": [resource]}
    return [error.message for error in Draft202012Validator(SCHEMA).iter_errors(document)]


def _semantic_errors(resource: dict) -> list[str]:
    helper = getattr(registry_validator, "validate_version_tracking", None)
    if not callable(helper):
        return ["RED: validate_version_tracking helper is missing"]
    errors: list[str] = []
    helper(resource, errors)
    return errors


class ResourceVersionTrackingSchemaRed1Tests(unittest.TestCase):
    def test_legacy_resource_without_tracking_remains_valid(self):
        self.assertEqual(_schema_errors(_resource()), [])

    def test_proposal_corpus_accepts_distinct_publication_commit_and_tf_identity(self):
        resource = _resource()
        resource["version_tracking"] = _proposal_tracking()
        self.assertEqual(_schema_errors(resource), [])

    def test_discovery_only_may_have_no_historical_accepted_state(self):
        resource = _resource()
        resource["upstream"] = {"repository": "example/corpus"}
        resource["version_tracking"] = {
            "discovery": {"mode": "default-branch"},
            "dataset": {"mode": "latest-root", "root": "tf", "ordering": "natural"},
            "promotion": {"mode": "discovery-only"},
        }
        self.assertEqual(_schema_errors(resource), [])

    def test_collection_member_index_tracking_has_no_scalar_tf_path(self):
        resource = _resource(kind="collection")
        resource["version_tracking"] = {
            "discovery": {"mode": "default-branch"},
            "dataset": {"mode": "member-index", "ordering": "none"},
            "promotion": {"mode": "proposal"},
            "accepted": {
                "publication_version": "snapshot-2026-09-09",
                "signal": "main@2026-09-09",
                "source_revision": COMMIT,
            },
        }
        self.assertEqual(_schema_errors(resource), [])

    def test_feature_module_cannot_define_parent_default_tracking(self):
        resource = _resource()
        resource.update(
            id="example-module",
            kind="feature-module",
            parent="example-corpus",
            compatibility={"parent_versions": ["1.2.3"]},
            module={"status": "optional"},
        )
        resource.pop("version_tracking", None)
        self.assertEqual(_schema_errors(resource), [])
        resource["version_tracking"] = _proposal_tracking()
        self.assertTrue(_schema_errors(resource))

    def test_mode_specific_unknown_fields_and_values_fail_closed(self):
        resource = _resource()
        tracking = _proposal_tracking()
        tracking["promotion"]["mode"] = "auto-merge"
        resource["version_tracking"] = tracking
        self.assertTrue(_schema_errors(resource))


class ResourceVersionTrackingSemanticRed1Tests(unittest.TestCase):
    def test_proposal_accepted_source_revision_matches_runtime_ref(self):
        resource = _resource()
        resource["version_tracking"] = _proposal_tracking()
        self.assertEqual(_semantic_errors(resource), [])

        drifted = copy.deepcopy(resource)
        drifted["upstream"]["ref"] = OTHER_COMMIT
        errors = _semantic_errors(drifted)
        self.assertTrue(any("source_revision" in error or "upstream.ref" in error for error in errors))

    def test_proposal_accepted_tf_path_matches_runtime_tf_path(self):
        resource = _resource()
        resource["version_tracking"] = _proposal_tracking()
        drifted = copy.deepcopy(resource)
        drifted["upstream"]["tf_path"] = "tf/9.9.9"
        errors = _semantic_errors(drifted)
        self.assertTrue(any("tf_path" in error for error in errors))

    def test_proposal_corpus_requires_immutable_runtime_ref_when_accepted(self):
        resource = _resource()
        resource["version_tracking"] = _proposal_tracking()
        resource["upstream"]["ref"] = "main"
        errors = _semantic_errors(resource)
        self.assertTrue(any("immutable" in error or "upstream.ref" in error for error in errors))

    def test_collection_member_index_rejects_accepted_scalar_tf_path(self):
        resource = _resource(kind="collection")
        resource["version_tracking"] = {
            "discovery": {"mode": "default-branch"},
            "dataset": {"mode": "member-index", "ordering": "none"},
            "promotion": {"mode": "proposal"},
            "accepted": {
                "publication_version": "snapshot",
                "signal": "main",
                "source_revision": COMMIT,
                "tf_path": "tf/1.0",
            },
        }
        errors = _semantic_errors(resource)
        self.assertTrue(any("tf_path" in error and "collection" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
