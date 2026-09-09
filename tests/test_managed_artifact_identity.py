from __future__ import annotations

import importlib
import json
import unittest


TREE_A = "a" * 64
TREE_B = "b" * 64
EXEC_A = "c" * 64
EXEC_B = "d" * 64
ATTEST_A = "e" * 64
MANIFEST_A = "f" * 64
CONTRACT_A = "1" * 64
PLUGIN_REF_A = "2" * 40
PLUGIN_REF_B = "3" * 40
SOURCE_REV_A = "4" * 40
SOURCE_REV_B = "5" * 40


def _module():
    try:
        return importlib.import_module("scripts.agora_managed_artifacts")
    except ModuleNotFoundError:
        return None


def _authorization(*, mode: str = "reusable", execution: str = EXEC_A, attestation: str | None = ATTEST_A):
    reusable = mode == "reusable"
    return {
        "mode": mode,
        "reuse_allowed": reusable,
        "attestation_sha256": attestation if reusable else None,
        "plugin_id": "synthetic-materializer",
        "materializer_id": "csv-text-fabric",
        "plugin_ref": PLUGIN_REF_A,
        "execution_identity_sha256": execution,
    }


def _request_kwargs():
    return {
        "authorization": _authorization(),
        "source": {
            "type": "local-directory",
            "tree_sha256": TREE_A,
            "resolved_commit": SOURCE_REV_A,
        },
        "plugin_repository": "example/synthetic-materializer",
        "plugin_version": "1.2.3",
        "manifest_sha256": MANIFEST_A,
        "materializer_contract_sha256": CONTRACT_A,
        "output_format": "text-fabric",
        "sandbox_policy": "required",
        "options": {"alpha": 1, "nested": {"x": True, "y": ["a", "b"]}},
    }


class ManagedArtifactIdentityRed1Tests(unittest.TestCase):
    def require_module(self):
        module = _module()
        self.assertIsNotNone(module, "RED1: managed artifact identity module is missing")
        return module

    def build(self, **changes):
        module = self.require_module()
        kwargs = _request_kwargs()
        kwargs.update(changes)
        return module.build_reusable_request_identity(**kwargs)

    def test_same_semantic_request_has_same_key_and_canonical_document(self):
        first = self.build()
        reordered = self.build(
            options={"nested": {"y": ["a", "b"], "x": True}, "alpha": 1}
        )
        self.assertEqual(first.key, reordered.key)
        self.assertEqual(first.canonical_json, reordered.canonical_json)
        self.assertRegex(first.key, r"^[0-9a-f]{64}$")
        self.assertEqual(json.loads(first.canonical_json)["schema_version"], 1)

    def test_source_tree_and_resolved_revision_are_identity_inputs(self):
        baseline = self.build()
        changed_tree = self.build(
            source={"type": "local-directory", "tree_sha256": TREE_B, "resolved_commit": SOURCE_REV_A}
        )
        changed_revision = self.build(
            source={"type": "local-directory", "tree_sha256": TREE_A, "resolved_commit": SOURCE_REV_B}
        )
        self.assertNotEqual(baseline.key, changed_tree.key)
        self.assertNotEqual(baseline.key, changed_revision.key)

    def test_plugin_runtime_policy_manifest_contract_options_and_format_are_identity_inputs(self):
        baseline = self.build()
        mutations = [
            {"authorization": {**_authorization(), "plugin_ref": PLUGIN_REF_B}},
            {"plugin_repository": "example/other-materializer"},
            {"plugin_version": "1.2.4"},
            {"authorization": _authorization(execution=EXEC_B)},
            {"authorization": _authorization(attestation="6" * 64)},
            {"manifest_sha256": "7" * 64},
            {"materializer_contract_sha256": "8" * 64},
            {"output_format": "other-format"},
            {"sandbox_policy": "different-policy"},
            {"options": {"alpha": 2, "nested": {"x": True, "y": ["a", "b"]}}},
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertNotEqual(baseline.key, self.build(**mutation).key)

    def test_non_identity_local_observations_cannot_perturb_or_leak_into_request(self):
        module = self.require_module()
        kwargs = _request_kwargs()
        first = module.build_reusable_request_identity(
            **kwargs,
            local_observations={
                "source_path": "/SECRET/location/Alpha Corpus",
                "source_basename": "Alpha Corpus",
                "output_path": "/SECRET/output",
                "cache_root": "/SECRET/cache-a",
                "created_at": "2026-09-09T01:02:03Z",
            },
        )
        second = module.build_reusable_request_identity(
            **kwargs,
            local_observations={
                "source_path": "/DIFFERENT/location/Beta Corpus",
                "source_basename": "Beta Corpus",
                "output_path": "/DIFFERENT/output",
                "cache_root": "/DIFFERENT/cache-b",
                "created_at": "2030-01-01T00:00:00Z",
            },
        )
        self.assertEqual(first.key, second.key)
        self.assertEqual(first.canonical_json, second.canonical_json)
        serialized = first.canonical_json
        for secret in ("SECRET", "Alpha Corpus", "source_path", "output_path", "cache_root", "created_at"):
            self.assertNotIn(secret, serialized)

    def test_unknown_and_non_reusable_authorization_never_build_reusable_key(self):
        module = self.require_module()
        for authorization in (
            {
                **_authorization(mode="non-reusable"),
                "mode": "unknown",
                "reuse_allowed": False,
            },
            _authorization(mode="non-reusable"),
        ):
            with self.subTest(mode=authorization["mode"]):
                with self.assertRaisesRegex(ValueError, r"reuse|reusable|authorization"):
                    module.build_reusable_request_identity(
                        **{**_request_kwargs(), "authorization": authorization}
                    )

    def test_inconsistent_reusable_authorization_fails_closed(self):
        module = self.require_module()
        cases = [
            {**_authorization(), "reuse_allowed": False},
            {**_authorization(), "attestation_sha256": None},
            {**_authorization(), "execution_identity_sha256": "not-a-digest"},
            {**_authorization(), "plugin_ref": "main"},
        ]
        for authorization in cases:
            with self.subTest(authorization=authorization):
                with self.assertRaises((ValueError, TypeError)):
                    module.build_reusable_request_identity(
                        **{**_request_kwargs(), "authorization": authorization}
                    )

    def test_one_shot_artifact_ids_are_unique_even_for_identical_requests(self):
        module = self.require_module()
        first = module.new_artifact_id()
        second = module.new_artifact_id()
        self.assertNotEqual(first, second)
        self.assertEqual(module.validate_artifact_id(first), first)
        self.assertEqual(module.validate_artifact_id(second), second)

    def test_artifact_id_validation_rejects_paths_traversal_empty_and_overlong_values(self):
        module = self.require_module()
        invalid = [
            "",
            ".",
            "..",
            "../escape",
            "a/b",
            "a\\b",
            "/absolute",
            "C:\\absolute",
            "a" * 300,
            "contains space",
        ]
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises((ValueError, TypeError)):
                    module.validate_artifact_id(value)

    def test_artifact_id_validation_is_pure_and_does_not_touch_filesystem(self):
        module = self.require_module()
        generated = module.new_artifact_id()
        # RED1 is a pure identity slice: validation returns a normalized/validated
        # opaque ID and has no store root/path parameter through which to touch IO.
        self.assertEqual(module.validate_artifact_id(generated), generated)


if __name__ == "__main__":
    unittest.main()
