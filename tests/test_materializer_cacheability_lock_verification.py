from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from scripts import agora_install_materializer as installer
from scripts import agora_materialize_registered as registered


REF = "0123456789abcdef0123456789abcdef01234567"
EXECUTION_ID = "a" * 64


def _plugin() -> dict:
    return {
        "id": "example-converter",
        "name": "Example converter",
        "description": "Synthetic converter for lock-bound authorization tests.",
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
    }


class CacheabilityLockVerificationRegressionTests(unittest.TestCase):
    def test_verified_receipt_is_obtained_while_runtime_lock_is_held(self):
        plugin = _plugin()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "managed-environment"
            runtime = target / "runtime"
            runtime.mkdir(parents=True)
            (runtime / plugin["manifest"]).write_text("{}", encoding="utf-8")
            lock_held = False

            @contextmanager
            def observing_lock(_path: Path):
                nonlocal lock_held
                lock_held = True
                try:
                    yield
                finally:
                    lock_held = False

            def observing_verified_receipt(_plugin: dict, _target: Path) -> dict:
                self.assertTrue(
                    lock_held,
                    "integrity-verified receipt must be obtained while the runtime lock is held",
                )
                return {"execution_identity_sha256": EXECUTION_ID}

            with (
                mock.patch.object(
                    registered,
                    "_registered_target",
                    return_value=(plugin, target),
                ),
                mock.patch.object(installer, "_lock", side_effect=observing_lock),
                mock.patch.object(
                    installer,
                    "_verified_environment_receipt",
                    side_effect=observing_verified_receipt,
                ) as verifier,
                mock.patch.object(installer, "_validate_binding", return_value={}),
                mock.patch.object(
                    installer,
                    "compare_cacheability_policy",
                    return_value={
                        "mode": "unknown",
                        "reuse_allowed": False,
                        "attestation_sha256": None,
                    },
                ),
            ):
                result = registered.resolve_cacheability_authorization(
                    "example-converter",
                    "example-to-tf",
                    install_root=target.parent,
                )

            verifier.assert_called_once_with(plugin, target)
            self.assertEqual(result["execution_identity_sha256"], EXECUTION_ID)
            self.assertFalse(result["reuse_allowed"])


if __name__ == "__main__":
    unittest.main()
