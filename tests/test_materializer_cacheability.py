from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from scripts import agora_install_materializer as installer


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "registry/schema/materializers.schema.json").read_text(encoding="utf-8"))
REF = "0123456789abcdef0123456789abcdef01234567"
OTHER_REF = "89abcdef0123456789abcdef0123456789abcdef"
EXECUTION_ID = "a" * 64
OTHER_EXECUTION_ID = "b" * 64
EVIDENCE_REF = "fedcba9876543210fedcba9876543210fedcba98"


def _plugin() -> dict:
    return {
        "id": "example-converter",
        "name": "Example converter",
        "description": "Synthetic converter for cacheability contract tests.",
        "repository": "example/converter",
        "ref": REF,
        "version": "1.2.3",
        "manifest": "agora.materializer.json",
        "package": {
            "type": "python-project",
            "path": ".",
            "install_trust": "explicit-code-execution",
        },
        "materializers": ["example-to-tf", "other-to-tf"],
        "disciplines": ["digital-philology"],
        "licenses": {"software": "MIT", "data": "synthetic"},
        "verification": {"status": "experimental"},
    }


def _evidence(target: str = "tests/test_replay.py::test_repeatable") -> dict:
    return {
        "type": "managed-replay",
        "repository": "example/evidence",
        "ref": EVIDENCE_REF,
        "target": target,
    }


def _reusable(execution_identity: str = EXECUTION_ID) -> dict:
    return {
        "mode": "reusable",
        "reviewed_ref": REF,
        "reviewed_environments": [
            {
                "execution_identity_sha256": execution_identity,
                "evidence": [_evidence()],
            }
        ],
    }


def _errors(plugin: dict) -> list[str]:
    document = {"schema_version": 1, "plugins": [plugin]}
    return [error.message for error in Draft202012Validator(SCHEMA).iter_errors(document)]


class MaterializerCacheabilitySchemaRedTests(unittest.TestCase):
    def test_legacy_plugin_without_cacheability_remains_valid(self):
        self.assertEqual(_errors(_plugin()), [])

    def test_non_reusable_is_a_valid_terminal_shape(self):
        plugin = _plugin()
        plugin["cacheability"] = {"example-to-tf": {"mode": "non-reusable"}}
        self.assertEqual(_errors(plugin), [])

    def test_non_reusable_rejects_stale_review_fields(self):
        plugin = _plugin()
        plugin["cacheability"] = {
            "example-to-tf": {"mode": "non-reusable", "reviewed_ref": REF}
        }
        self.assertTrue(_errors(plugin))

    def test_reusable_requires_exact_ref_environment_and_evidence(self):
        plugin = _plugin()
        plugin["cacheability"] = {"example-to-tf": _reusable()}
        self.assertEqual(_errors(plugin), [])

        for mutate in (
            lambda policy: policy.pop("reviewed_ref"),
            lambda policy: policy.update(reviewed_ref="main"),
            lambda policy: policy.update(reviewed_environments=[]),
            lambda policy: policy["reviewed_environments"][0].update(
                execution_identity_sha256="short"
            ),
            lambda policy: policy["reviewed_environments"][0].update(evidence=[]),
        ):
            candidate = _plugin()
            policy = _reusable()
            mutate(policy)
            candidate["cacheability"] = {"example-to-tf": policy}
            self.assertTrue(_errors(candidate), candidate)

    def test_duplicate_reviewed_execution_identities_are_rejected(self):
        plugin = _plugin()
        policy = _reusable()
        policy["reviewed_environments"].append(copy.deepcopy(policy["reviewed_environments"][0]))
        plugin["cacheability"] = {"example-to-tf": policy}
        self.assertTrue(_errors(plugin))

    def test_cacheability_key_must_name_a_registered_materializer(self):
        plugin = _plugin()
        plugin["cacheability"] = {"removed-to-tf": {"mode": "non-reusable"}}
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "materializers.yaml"
            registry.write_text(
                yaml.safe_dump({"schema_version": 1, "plugins": [plugin]}, sort_keys=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                installer.MaterializerRegistryError,
                r"cacheability.*registered materializer",
            ):
                installer.load_registry(registry)


class MaterializerCacheabilityPolicyRedTests(unittest.TestCase):
    def _compare(self, plugin: dict, materializer_id: str, execution_identity: str):
        return installer.compare_cacheability_policy(
            plugin,
            materializer_id,
            verified_execution_identity=execution_identity,
        )

    def test_absent_policy_is_unknown_and_reuse_denied(self):
        result = self._compare(_plugin(), "example-to-tf", EXECUTION_ID)
        self.assertEqual(result["mode"], "unknown")
        self.assertFalse(result["reuse_allowed"])
        self.assertIsNone(result["attestation_sha256"])

    def test_non_reusable_is_explicitly_reuse_denied(self):
        plugin = _plugin()
        plugin["cacheability"] = {"example-to-tf": {"mode": "non-reusable"}}
        result = self._compare(plugin, "example-to-tf", EXECUTION_ID)
        self.assertEqual(result["mode"], "non-reusable")
        self.assertFalse(result["reuse_allowed"])
        self.assertIsNone(result["attestation_sha256"])

    def test_reusable_requires_exact_reviewed_ref_and_execution_identity(self):
        plugin = _plugin()
        plugin["cacheability"] = {"example-to-tf": _reusable()}

        accepted = self._compare(plugin, "example-to-tf", EXECUTION_ID)
        self.assertEqual(accepted["mode"], "reusable")
        self.assertTrue(accepted["reuse_allowed"])
        self.assertRegex(accepted["attestation_sha256"], r"^[0-9a-f]{64}$")

        wrong_environment = self._compare(plugin, "example-to-tf", OTHER_EXECUTION_ID)
        self.assertEqual(wrong_environment["mode"], "unknown")
        self.assertFalse(wrong_environment["reuse_allowed"])
        self.assertIsNone(wrong_environment["attestation_sha256"])

        moved = copy.deepcopy(plugin)
        moved["ref"] = OTHER_REF
        stale_ref = self._compare(moved, "example-to-tf", EXECUTION_ID)
        self.assertEqual(stale_ref["mode"], "unknown")
        self.assertFalse(stale_ref["reuse_allowed"])
        self.assertIsNone(stale_ref["attestation_sha256"])

    def test_attestation_digest_binds_registration_coordinates_and_environment(self):
        plugin = _plugin()
        plugin["cacheability"] = {
            "example-to-tf": _reusable(),
            "other-to-tf": _reusable(),
        }
        first = self._compare(plugin, "example-to-tf", EXECUTION_ID)["attestation_sha256"]
        other_materializer = self._compare(plugin, "other-to-tf", EXECUTION_ID)[
            "attestation_sha256"
        ]

        renamed = copy.deepcopy(plugin)
        renamed["id"] = "renamed-converter"
        other_plugin = self._compare(renamed, "example-to-tf", EXECUTION_ID)[
            "attestation_sha256"
        ]

        second_environment = copy.deepcopy(plugin)
        second_environment["cacheability"]["example-to-tf"]["reviewed_environments"].append(
            {
                "execution_identity_sha256": OTHER_EXECUTION_ID,
                "evidence": [_evidence("tests/test_replay.py::test_other_runtime")],
            }
        )
        other_environment = self._compare(
            second_environment, "example-to-tf", OTHER_EXECUTION_ID
        )["attestation_sha256"]

        self.assertNotEqual(first, other_materializer)
        self.assertNotEqual(first, other_plugin)
        self.assertNotEqual(first, other_environment)

    def test_evidence_order_is_canonical_for_attestation_identity(self):
        plugin = _plugin()
        policy = _reusable()
        policy["reviewed_environments"][0]["evidence"] = [
            _evidence("target-b"),
            _evidence("target-a"),
        ]
        plugin["cacheability"] = {"example-to-tf": policy}
        forward = self._compare(plugin, "example-to-tf", EXECUTION_ID)["attestation_sha256"]

        reversed_plugin = copy.deepcopy(plugin)
        reversed_plugin["cacheability"]["example-to-tf"]["reviewed_environments"][0][
            "evidence"
        ].reverse()
        reversed_digest = self._compare(
            reversed_plugin, "example-to-tf", EXECUTION_ID
        )["attestation_sha256"]
        self.assertEqual(forward, reversed_digest)


if __name__ == "__main__":
    unittest.main()
