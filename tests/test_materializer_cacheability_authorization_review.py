from __future__ import annotations

import contextlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import agora_install_materializer as installer
from scripts import agora_materialize_registered as registered
from test_materializer_cacheability_authorization import (
    MaterializerCacheabilityAuthorizationRedTests,
    _fake_install,
    _plugin,
    _reusable,
    _write_fixture_plugin,
    _write_registry,
)


class MaterializerCacheabilityAuthorizationReviewTests(
    MaterializerCacheabilityAuthorizationRedTests
):
    def test_verified_receipt_snapshot_is_obtained_under_runtime_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path, _target, actual_identity = self._installed_fixture(root)
            _write_registry(registry_path, _plugin(cacheability=_reusable(actual_identity)))

            original_lock = installer._lock
            original_verified_receipt = installer._verified_environment_receipt
            lock_held = False

            @contextlib.contextmanager
            def observing_lock(path: Path, *, timeout: float = installer.LOCK_WAIT_SECONDS):
                nonlocal lock_held
                with original_lock(path, timeout=timeout):
                    lock_held = True
                    try:
                        yield
                    finally:
                        lock_held = False

            def observing_verified_receipt(plugin: dict, target: Path):
                self.assertTrue(
                    lock_held,
                    "the receipt snapshot used for authorization must be verified under the runtime lock",
                )
                return original_verified_receipt(plugin, target)

            with mock.patch.object(installer, "_lock", observing_lock), mock.patch.object(
                installer,
                "_verified_environment_receipt",
                side_effect=observing_verified_receipt,
            ):
                result = registered.resolve_cacheability_authorization(
                    "example-converter",
                    "example-to-tf",
                    install_root=root / "installed",
                    registry_path=registry_path,
                )

            self.assertTrue(result["reuse_allowed"])

    def test_authorization_accepts_installer_supported_nested_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = root / "materializers.yaml"
            plugin = _plugin()
            plugin["manifest"] = "example_converter/agora.materializer.json"
            _write_registry(registry_path, plugin)

            def populate(_plugin_metadata: dict, destination: Path) -> str:
                _write_fixture_plugin(destination)
                nested = destination / plugin["manifest"]
                nested.parent.mkdir(parents=True, exist_ok=True)
                (destination / "agora.materializer.json").replace(nested)
                return plugin["ref"]

            with mock.patch.object(installer, "_checkout", side_effect=populate), mock.patch.object(
                installer,
                "_install_python",
                side_effect=_fake_install,
            ):
                target = installer.install_materializer(
                    "example-converter",
                    install_root=root / "installed",
                    registry_path=registry_path,
                    approve_code_execution=True,
                )

            receipt = installer._verified_environment_receipt(plugin, target)
            self.assertIsNotNone(receipt, "nested manifest installation must remain integrity-valid")
            assert receipt is not None
            identity = receipt["execution_identity_sha256"]

            plugin["cacheability"] = _reusable(identity)
            _write_registry(registry_path, plugin)
            result = registered.resolve_cacheability_authorization(
                "example-converter",
                "example-to-tf",
                install_root=root / "installed",
                registry_path=registry_path,
            )

            self.assertTrue(result["reuse_allowed"])
            self.assertEqual(result["execution_identity_sha256"], identity)


if __name__ == "__main__":
    unittest.main()
