from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import agora_install_materializer as installer
from test_materializer_execution_identity_research import (
    _plugin,
    _populate,
    _registry,
)


class MaterializerExecutionIdentityV3Red1Tests(unittest.TestCase):
    """Desired-state RED1 for the merged #111 receipt-v3 design."""

    def test_two_clean_installs_share_canonical_v3_identity_after_staging_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = _registry(root / "materializers.yaml")
            installs: list[tuple[Path, dict]] = []

            with mock.patch.object(installer, "_checkout", side_effect=_populate):
                for name in ("install-a", "install-b"):
                    target = installer.install_materializer(
                        "research-probe",
                        install_root=root / name,
                        registry_path=registry,
                        approve_code_execution=True,
                    )
                    receipt = json.loads(
                        (target / installer.INSTALLATION_RECEIPT).read_text(encoding="utf-8")
                    )
                    installs.append((target, receipt))

            (left_target, left), (right_target, right) = installs

            # The research proved the raw PEP-610/RECORD provenance differs.
            # Receipt v3 must preserve that raw tamper-sensitive observation.
            self.assertNotEqual(
                left["environment"]["tree_sha256"],
                right["environment"]["tree_sha256"],
            )
            self.assertNotEqual(
                left["environment"]["pip_report_sha256"],
                right["environment"]["pip_report_sha256"],
            )

            self.assertEqual(left["schema_version"], 3)
            self.assertEqual(right["schema_version"], 3)
            self.assertRegex(
                left["environment"]["execution_tree_sha256"], r"^[0-9a-f]{64}$"
            )
            self.assertEqual(
                left["environment"]["execution_tree_sha256"],
                right["environment"]["execution_tree_sha256"],
            )
            self.assertEqual(
                left["execution_identity_sha256"],
                right["execution_identity_sha256"],
            )

            # install_materializer has already deleted each random build root by
            # the time it returns. Verification therefore proves replay from the
            # stored raw pip report + installed bytes, not staging existence.
            left_verified = installer._verified_environment_receipt(_plugin(), left_target)
            right_verified = installer._verified_environment_receipt(_plugin(), right_target)
            self.assertIsNotNone(left_verified)
            self.assertIsNotNone(right_verified)
            self.assertEqual(
                left_verified["environment"]["execution_tree_sha256"],
                left["environment"]["execution_tree_sha256"],
            )
            self.assertEqual(
                right_verified["execution_identity_sha256"],
                right["execution_identity_sha256"],
            )

    def test_raw_runtime_tamper_remains_detected_under_v3(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = _registry(root / "materializers.yaml")
            with mock.patch.object(installer, "_checkout", side_effect=_populate):
                target = installer.install_materializer(
                    "research-probe",
                    install_root=root / "installed",
                    registry_path=registry,
                    approve_code_execution=True,
                )

            receipt = json.loads(
                (target / installer.INSTALLATION_RECEIPT).read_text(encoding="utf-8")
            )
            self.assertEqual(receipt["schema_version"], 3)
            runtime_file = target / "runtime" / "research_probe" / "cli.py"
            runtime_file.write_text("def main():\n    return 99\n", encoding="utf-8")
            self.assertIsNone(installer._verified_environment_receipt(_plugin(), target))

    def test_canonical_execution_tree_changes_when_runtime_code_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = _registry(root / "materializers.yaml")
            with mock.patch.object(installer, "_checkout", side_effect=_populate):
                target = installer.install_materializer(
                    "research-probe",
                    install_root=root / "installed",
                    registry_path=registry,
                    approve_code_execution=True,
                )

            receipt = json.loads(
                (target / installer.INSTALLATION_RECEIPT).read_text(encoding="utf-8")
            )
            original = receipt["environment"]["execution_tree_sha256"]
            runtime_file = target / "runtime" / "research_probe" / "cli.py"
            runtime_file.write_text("def main():\n    return 99\n", encoding="utf-8")
            changed = installer.canonical_execution_tree_hash(
                target / "runtime",
                target / installer.PIP_REPORT,
                excludes=installer.RUNTIME_TREE_EXCLUDES,
            )
            self.assertNotEqual(original, changed)


if __name__ == "__main__":
    unittest.main()
