"""Agora #187 stage-1: discover and execute IIP-TF through the real host.

The upstream scholarly parser, normalization and Text-Fabric node semantics
remain in IIP-TF. These tests only guard Agora's registry and installed-host
integration; a separate upstream gate validates the 5,535 source records.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from scripts.agora_install_materializer import load_registry, select_plugin

ROOT = Path(__file__).resolve().parents[1]
IIP_SHA = "31c5052c0bb5d3cd2fb8418616ffdaf519582d24"
BROWN_SHA = "0b7dc8358ccdfd0c9391f049da4839fbd91c26e5"


class IipTfRegisteredMaterializerTests(unittest.TestCase):
    def test_registry_links_immutable_release_producer_with_correct_rights(self) -> None:
        entry = select_plugin(load_registry(), "iip-tf")
        self.assertEqual(entry["name"], "IIP-TF")
        self.assertEqual(entry["repository"], "alexsosn/IIP-TF")
        self.assertEqual(entry["ref"], IIP_SHA)
        self.assertEqual(entry["version"], "0.1.0.dev0")
        self.assertEqual(entry["release_tracking"], {"mode": "disabled"})
        self.assertEqual(entry["manifest"], "agora.materializer.json")
        self.assertEqual(entry["materializers"], ["iip-epidoc-text-fabric"])
        self.assertEqual(
            entry["package"],
            {
                "type": "python-project",
                "path": ".",
                "install_trust": "explicit-code-execution",
            },
        )
        self.assertEqual(entry["licenses"], {"software": "MIT", "data": "CC-BY-NC-4.0"})
        self.assertEqual(entry["verification"]["status"], "community")
        notes = " ".join(entry["verification"]["notes"]).lower()
        self.assertIn("explicit", notes)
        self.assertIn("5,535", notes)
        self.assertIn("not final", notes)

    def test_existing_materializer_install_workflow_checks_real_host_acceptance(self) -> None:
        workflow = (ROOT / ".github/workflows/materializer-install.yml").read_text()
        job = workflow.split("  iip-tf:", 1)[1]
        self.assertIn("python scripts/validate_registry.py", job)
        self.assertIn("python scripts/agora_install_materializer.py fetch iip-tf", job)
        self.assertIn("python scripts/agora_install_materializer.py install iip-tf", job)
        self.assertIn("--approve-code-execution", job)
        self.assertIn("python scripts/agora_materialize_registered.py", job)
        self.assertIn("--plugin iip-tf", job)
        self.assertIn("--materializer iip-epidoc-text-fabric", job)
        self.assertIn("--sandbox required", job)
        self.assertIn("bubblewrap", job)
        self.assertIn(BROWN_SHA, job)
        self.assertIn("agora-materialization.json", job)
        self.assertIn("conversion-summary.json", job)
        self.assertIn("from tf.fabric import Fabric", job)
        self.assertIn("api.F.otype.s('inscription')", job)
        self.assertIn("source_revision_verified", job)
        self.assertIn("github.event.pull_request.head.sha || github.sha", job)
        self.assertNotIn("--sandbox off", job)
        # Crucially: automatic Git acquisition is exercised, not only a copied
        # local source fixture. The live host must use the manifest's source pin.
        self.assertNotIn(" --source ", job)


if __name__ == "__main__":
    unittest.main()
