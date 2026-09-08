from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from scripts import agora_install_materializer as installer
from scripts import agora_materialize as host
from scripts import agora_materialize_registered as registered


REF = "0123456789abcdef0123456789abcdef01234567"
EXECUTION_ID = "a" * 64
OTHER_EXECUTION_ID = "b" * 64
THIRD_EXECUTION_ID = "c" * 64
EVIDENCE_REF = "fedcba9876543210fedcba9876543210fedcba98"


def _plugin() -> dict:
    return {
        "id": "example-converter",
        "name": "Example converter",
        "description": "Synthetic converter for trusted cacheability tests.",
        "repository": "example/converter",
        "ref": REF,
        "version": "1.2.3",
        "manifest": "agora.materializer.json",
        "package": {
            "type": "python-project",
            "path": ".",
            "install_trust": "explicit-code-execution",
        },
        "materializers": ["example-to-tf"],
        "disciplines": ["digital-philology"],
        "licenses": {"software": "MIT", "data": "synthetic"},
        "verification": {"status": "experimental"},
        "cacheability": {
            "example-to-tf": {
                "mode": "reusable",
                "reviewed_ref": REF,
                "reviewed_environments": [
                    {
                        "execution_identity_sha256": EXECUTION_ID,
                        "evidence": [
                            {
                                "type": "managed-replay",
                                "repository": "example/evidence",
                                "ref": EVIDENCE_REF,
                                "target": "tests/test_replay.py::test_runtime_a",
                            }
                        ],
                    },
                    {
                        "execution_identity_sha256": OTHER_EXECUTION_ID,
                        "evidence": [
                            {
                                "type": "managed-replay",
                                "repository": "example/evidence",
                                "ref": EVIDENCE_REF,
                                "target": "tests/test_replay.py::test_runtime_b",
                            }
                        ],
                    },
                ],
            }
        },
    }


def _receipt(execution_identity: str) -> dict:
    return {
        "schema_version": 2,
        "execution_identity_sha256": execution_identity,
    }


class TrustedInstalledCacheabilityRed2Tests(unittest.TestCase):
    def _resolver(self):
        resolver = getattr(registered, "resolve_installed_cacheability", None)
        self.assertTrue(
            callable(resolver),
            "RED 2: registered runner must expose authoritative installed cacheability resolution",
        )
        return resolver

    def test_authoritative_resolver_does_not_accept_caller_execution_identity(self):
        resolver = self._resolver()
        parameters = inspect.signature(resolver).parameters
        self.assertNotIn("execution_identity", parameters)
        self.assertNotIn("verified_execution_identity", parameters)

    def test_exact_verified_receipt_identity_authorizes_reuse_under_runtime_lock(self):
        resolver = self._resolver()
        plugin = _plugin()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "managed-environment"
            runtime = target / "runtime"
            runtime.mkdir(parents=True)
            manifest = runtime / plugin["manifest"]
            manifest.write_text("{}", encoding="utf-8")
            (target / installer.INSTALLATION_RECEIPT).write_text(
                json.dumps(_receipt(EXECUTION_ID)), encoding="utf-8"
            )
            lock_held = False

            @contextmanager
            def fake_lock(path):
                nonlocal lock_held
                self.assertEqual(path, target.parent / f".{target.name}.lock")
                self.assertFalse(lock_held)
                lock_held = True
                try:
                    yield
                finally:
                    lock_held = False

            def verified_manifest(*args, **kwargs):
                self.assertTrue(lock_held, "installation integrity must be verified while runtime lock is held")
                return manifest

            with (
                mock.patch.object(registered, "_registered_target", return_value=(plugin, target)) as target_mock,
                mock.patch.object(registered, "resolve_installed_manifest", side_effect=verified_manifest) as manifest_mock,
                mock.patch.object(installer, "_lock", side_effect=fake_lock) as lock_mock,
                mock.patch.object(installer, "_validate_binding", return_value={}) as binding_mock,
                mock.patch.object(installer, "fetch_materializer") as fetch_mock,
                mock.patch.object(installer, "install_materializer") as install_mock,
            ):
                result = resolver(
                    "example-converter",
                    "example-to-tf",
                    install_root=root,
                    registry_path=root / "materializers.yaml",
                )

            self.assertEqual(result["mode"], "reusable")
            self.assertTrue(result["reuse_allowed"])
            self.assertRegex(result["attestation_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(target_mock.call_count, 2)
            manifest_mock.assert_called_once()
            lock_mock.assert_called_once()
            binding_mock.assert_called_once_with(plugin, runtime)
            fetch_mock.assert_not_called()
            install_mock.assert_not_called()

    def test_unreviewed_verified_environment_fails_closed_without_install_side_effects(self):
        resolver = self._resolver()
        plugin = _plugin()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "managed-environment"
            runtime = target / "runtime"
            runtime.mkdir(parents=True)
            manifest = runtime / plugin["manifest"]
            manifest.write_text("{}", encoding="utf-8")
            (target / installer.INSTALLATION_RECEIPT).write_text(
                json.dumps(_receipt(THIRD_EXECUTION_ID)), encoding="utf-8"
            )
            with (
                mock.patch.object(registered, "_registered_target", return_value=(plugin, target)),
                mock.patch.object(registered, "resolve_installed_manifest", return_value=manifest),
                mock.patch.object(installer, "_lock", return_value=mock.MagicMock(__enter__=lambda self: None, __exit__=lambda self, *args: False)),
                mock.patch.object(installer, "_validate_binding", return_value={}),
                mock.patch.object(installer, "fetch_materializer") as fetch_mock,
                mock.patch.object(installer, "install_materializer") as install_mock,
            ):
                result = resolver(
                    "example-converter",
                    "example-to-tf",
                    install_root=root,
                    registry_path=root / "materializers.yaml",
                )
            self.assertEqual(result["mode"], "unknown")
            self.assertFalse(result["reuse_allowed"])
            self.assertIsNone(result["attestation_sha256"])
            fetch_mock.assert_not_called()
            install_mock.assert_not_called()

    def test_integrity_failure_prevents_policy_authorization(self):
        resolver = self._resolver()
        plugin = _plugin()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "managed-environment"
            target.mkdir(parents=True)
            with (
                mock.patch.object(registered, "_registered_target", return_value=(plugin, target)),
                mock.patch.object(installer, "_lock", return_value=mock.MagicMock(__enter__=lambda self: None, __exit__=lambda self, *args: False)),
                mock.patch.object(
                    registered,
                    "resolve_installed_manifest",
                    side_effect=installer.MaterializerInstallError("integrity verification failed"),
                ),
                mock.patch.object(installer, "compare_cacheability_policy") as compare_mock,
            ):
                with self.assertRaisesRegex(installer.MaterializerInstallError, "integrity"):
                    resolver("example-converter", "example-to-tf", install_root=Path(tmp))
            compare_mock.assert_not_called()

    def test_direct_execution_does_not_consult_cacheability_policy(self):
        plugin = _plugin()
        plugin.pop("cacheability")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "managed-environment"
            runtime = target / "runtime"
            runtime.mkdir(parents=True)
            manifest = runtime / plugin["manifest"]
            output = root / "out"
            with (
                mock.patch.object(registered, "_registered_target", return_value=(plugin, target)),
                mock.patch.object(registered, "resolve_installed_manifest", return_value=manifest),
                mock.patch.object(installer, "_lock", return_value=mock.MagicMock(__enter__=lambda self: None, __exit__=lambda self, *args: False)),
                mock.patch.object(installer, "_validate_binding", return_value={}),
                mock.patch.object(installer, "compare_cacheability_policy") as compare_mock,
                mock.patch.object(host, "materialize", return_value=output),
            ):
                result = registered.materialize_registered(
                    plugin_id="example-converter",
                    materializer_id="example-to-tf",
                    output=output,
                    install_root=root,
                )
            self.assertEqual(result, output)
            compare_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
