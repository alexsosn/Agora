from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from scripts import agora_install_materializer as installer
from scripts import agora_materialize_registered as registered


REF = "0123456789abcdef0123456789abcdef01234567"
ACTUAL_IDENTITY = "a" * 64
REVIEWED_IDENTITY = "f" * 64
EVIDENCE_REF = "fedcba9876543210fedcba9876543210fedcba98"


def _plugin() -> dict:
    return {
        "id": "example-converter",
        "name": "Example converter",
        "description": "Synthetic converter for receipt-binding race tests.",
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
                        "execution_identity_sha256": REVIEWED_IDENTITY,
                        "evidence": [
                            {
                                "type": "managed-replay",
                                "repository": "example/evidence",
                                "ref": EVIDENCE_REF,
                                "target": "tests/test_replay.py::test_repeatable",
                            }
                        ],
                    }
                ],
            }
        },
    }


class CacheabilityReceiptBindingRed3Tests(unittest.TestCase):
    def test_receipt_swap_after_integrity_verification_cannot_authorize_reuse(self):
        """Authorization must use the exact receipt snapshot that was verified.

        A non-cooperating filesystem writer is not serialized by Agora's runtime
        lock. Simulate the receipt changing immediately after the integrity
        verifier has accepted ACTUAL_IDENTITY but before the authorization path
        consumes the identity. The replacement identity is deliberately one that
        the registry reviews, so a second unbound receipt read would authorize
        the wrong managed runtime.
        """
        plugin = _plugin()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "managed-environment"
            runtime = target / "runtime"
            runtime.mkdir(parents=True)
            (runtime / plugin["manifest"]).write_text("{}", encoding="utf-8")
            receipt_path = target / installer.INSTALLATION_RECEIPT
            receipt_path.write_text(
                json.dumps({"schema_version": 2, "execution_identity_sha256": ACTUAL_IDENTITY}),
                encoding="utf-8",
            )

            @contextmanager
            def fake_lock(_path: Path):
                yield

            def verify_then_swap(_plugin: dict, _target: Path) -> bool:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                self.assertEqual(receipt["execution_identity_sha256"], ACTUAL_IDENTITY)
                receipt["execution_identity_sha256"] = REVIEWED_IDENTITY
                receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
                return True

            with (
                mock.patch.object(registered, "_registered_target", return_value=(plugin, target)),
                mock.patch.object(installer, "_lock", side_effect=fake_lock),
                mock.patch.object(installer, "_environment_current", side_effect=verify_then_swap),
                mock.patch.object(installer, "_validate_binding", return_value={}),
            ):
                try:
                    result = registered.resolve_cacheability_authorization(
                        "example-converter",
                        "example-to-tf",
                        install_root=root,
                    )
                except installer.MaterializerInstallError:
                    return

            self.assertFalse(
                result["reuse_allowed"],
                "a receipt identity not present in the verified snapshot must not authorize reuse",
            )


if __name__ == "__main__":
    unittest.main()
