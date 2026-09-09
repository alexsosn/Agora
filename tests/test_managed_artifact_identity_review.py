from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from scripts import agora_managed_artifacts as managed


TREE = "a" * 64
EXECUTION = "b" * 64
ATTESTATION = "c" * 64
MANIFEST = "d" * 64
CONTRACT = "e" * 64
REF = "1" * 40
REVISION = "2" * 40


def _kwargs() -> dict:
    return {
        "authorization": {
            "mode": "reusable",
            "reuse_allowed": True,
            "attestation_sha256": ATTESTATION,
            "plugin_id": "synthetic-materializer",
            "materializer_id": "csv-text-fabric",
            "plugin_ref": REF,
            "execution_identity_sha256": EXECUTION,
        },
        "source": {
            "type": "local-directory",
            "tree_sha256": TREE,
            "resolved_commit": REVISION,
        },
        "plugin_repository": "example/synthetic-materializer",
        "plugin_version": "1.2.3",
        "manifest_sha256": MANIFEST,
        "materializer_contract_sha256": CONTRACT,
        "output_format": "text-fabric",
        "sandbox_policy": "required",
        "options": {},
    }


class ManagedArtifactIdentityReviewTests(unittest.TestCase):
    def test_host_contract_version_is_authoritative_identity_input(self):
        self.assertIsInstance(managed.MATERIALIZATION_HOST_SCHEMA_VERSION, int)
        baseline = managed.build_reusable_request_identity(**_kwargs())
        document = json.loads(baseline.canonical_json)
        self.assertEqual(
            document["host_schema_version"],
            managed.MATERIALIZATION_HOST_SCHEMA_VERSION,
        )

        with patch.object(
            managed,
            "MATERIALIZATION_HOST_SCHEMA_VERSION",
            managed.MATERIALIZATION_HOST_SCHEMA_VERSION + 1,
        ):
            changed = managed.build_reusable_request_identity(**_kwargs())

        self.assertNotEqual(baseline.key, changed.key)

    def test_host_contract_version_is_not_caller_selectable(self):
        import inspect

        parameters = inspect.signature(managed.build_reusable_request_identity).parameters
        self.assertNotIn("host_schema_version", parameters)


if __name__ == "__main__":
    unittest.main()
