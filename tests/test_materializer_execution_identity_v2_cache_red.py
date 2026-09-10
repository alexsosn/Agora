from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import agora_install_materializer as installer
from scripts import agora_materialize_registered as registered
from test_materializer_cacheability_authorization import (
    MaterializerCacheabilityAuthorizationRedTests,
    _plugin,
    _reusable,
    _write_registry,
)


class MaterializerExecutionIdentityV2CacheRedTests(unittest.TestCase):
    """Receipt v2 remains executable compatibility data, never cache authorization."""

    def _legacy_installed_fixture(self, root: Path) -> tuple[Path, Path, str]:
        fixture = MaterializerCacheabilityAuthorizationRedTests()
        registry_path, target, _v3_identity = fixture._installed_fixture(root)

        receipt_path = target / installer.INSTALLATION_RECEIPT
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["schema_version"] = 2
        receipt["environment"].pop("execution_tree_sha256")
        legacy_identity = installer._json_hash(
            {
                "source_tree_sha256": receipt["source"]["tree_sha256"],
                "environment_tree_sha256": receipt["environment"]["tree_sha256"],
                "runtime": receipt["runtime"],
            }
        )
        receipt["execution_identity_sha256"] = legacy_identity
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        return registry_path, target, legacy_identity

    def test_valid_v2_receipt_verifies_but_cannot_authorize_reusable_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path, target, legacy_identity = self._legacy_installed_fixture(root)

            # Compatibility contract: a genuine historical v2 receipt remains
            # a valid installation for direct execution/manifest resolution.
            verified = installer._verified_environment_receipt(_plugin(), target)
            self.assertIsNotNone(verified)
            manifest = registered.resolve_installed_manifest(
                "example-converter",
                install_root=root / "installed",
                registry_path=registry_path,
            )
            self.assertTrue(manifest.is_file())

            # Authorization contract: v2 identity included raw ephemeral install
            # provenance and is not the reproducible identity reviewed for reuse.
            _write_registry(registry_path, _plugin(cacheability=_reusable(legacy_identity)))
            result = registered.resolve_cacheability_authorization(
                "example-converter",
                "example-to-tf",
                install_root=root / "installed",
                registry_path=registry_path,
            )
            self.assertEqual(result["mode"], "unknown")
            self.assertFalse(result["reuse_allowed"])
            self.assertIsNone(result["attestation_sha256"])

    def test_valid_v2_receipt_preserves_explicit_non_reusable_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path, _target, _legacy_identity = self._legacy_installed_fixture(root)
            plugin = _plugin(
                cacheability={"example-to-tf": {"mode": "non-reusable"}}
            )
            _write_registry(registry_path, plugin)

            result = registered.resolve_cacheability_authorization(
                "example-converter",
                "example-to-tf",
                install_root=root / "installed",
                registry_path=registry_path,
            )
            self.assertEqual(result["mode"], "non-reusable")
            self.assertFalse(result["reuse_allowed"])
            self.assertIsNone(result["attestation_sha256"])


if __name__ == "__main__":
    unittest.main()
