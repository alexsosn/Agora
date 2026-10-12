"""Agora #221 stage 1 — registered CATSS standalone producer integration contract.

The old canonical registry/workflow intentionally fails these tests (RED)
until the real pinned producer is registered and sandboxed live.
"""

from __future__ import annotations

from pathlib import Path
import unittest

import yaml

from scripts.agora_install_materializer import load_registry, select_plugin

ROOT = Path(__file__).resolve().parents[1]
CATSS_SHA = "3ee63c4c054960b816b14496815815153e5e543d"


class CatssCanonicalRegistrationTests(unittest.TestCase):
    def test_immutable_pinned_standalone_producer_and_rights(self):
        plugin = select_plugin(load_registry(), "catss-tf")
        self.assertEqual(plugin["repository"], "alexsosn/CATSS-TF")
        self.assertEqual(plugin["name"], "CATSS Hebrew-Greek alignment Text-Fabric")
        self.assertEqual(plugin["ref"], CATSS_SHA)
        self.assertEqual(plugin["version"], "0.1.0")
        self.assertEqual(plugin["manifest"], "agora.materializer.json")
        self.assertEqual(plugin["release_tracking"], {"mode": "disabled"})
        self.assertEqual(plugin["package"], {
            "type": "python-project",
            "path": ".",
            "install_trust": "explicit-code-execution",
        })
        self.assertEqual(plugin["materializers"], ["catss-canonical"])
        self.assertEqual(plugin["licenses"]["software"], "MIT")
        self.assertEqual(plugin["licenses"]["data"], "upstream-dependent")
        self.assertEqual(plugin["verification"]["status"], "community")
        self.assertTrue(any("licensed" in n.lower() for n in plugin["verification"]["notes"]))

        manifest = yaml.safe_load((ROOT / "registry/materializers.yaml").read_text())
        self.assertEqual(
            len([p for p in manifest["plugins"] if p["id"] == "catss-tf"]), 1
        )

    def test_strict_source_only_no_unverified_projection_registered(self):
        plugin = select_plugin(load_registry(), "catss-tf")
        self.assertEqual(plugin["materializers"], ["catss-canonical"])
        self.assertNotIn("cacheability", plugin)
        self.assertNotIn("catss-bhsa", str(plugin))
        self.assertNotIn("catss-lxx", str(plugin))

    def test_exact_head_workflow_installs_and_runs_in_required_sandbox(self):
        workflow = (ROOT / ".github/workflows/materializer-install.yml").read_text()
        self.assertIn("tests/test_catss_canonical_registered_221.py", workflow)
        self.assertIn("catss-tf:", workflow)
        self.assertIn("github.event.pull_request.head.sha || github.sha", workflow)
        self.assertIn('test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"', workflow)
        self.assertIn("python scripts/validate_registry.py", workflow)
        self.assertIn("python -m unittest tests.test_catss_canonical_registered_221", workflow)
        self.assertIn("python scripts/agora_install_materializer.py fetch catss-tf", workflow)
        self.assertIn("python scripts/agora_install_materializer.py install catss-tf", workflow)
        self.assertIn("--approve-code-execution", workflow)
        self.assertIn("bwrap --unshare-all --ro-bind / / /bin/true", workflow)
        self.assertIn("python scripts/agora_materialize_registered.py", workflow)
        self.assertIn("--plugin catss-tf", workflow)
        self.assertIn("--materializer catss-canonical", workflow)
        self.assertIn("--source", workflow)
        self.assertIn("--sandbox required", workflow)
        self.assertIn("agora-materialization.json", workflow)
        self.assertIn("catss_alignment_id.tf", workflow)
        self.assertIn("CATSS_AGORA_STANDALONE_OK", workflow)

    def test_registered_smoke_explicitly_checks_user_local_provenance(self):
        text = (ROOT / ".github/workflows/materializer-install.yml").read_text()
        self.assertIn("provenance['source']['type'] == 'user-local'", text)
        self.assertIn("provenance['sandbox'] == 'bubblewrap'", text)
        self.assertIn("api.F.otype.slotType == 'alignment'", text)
        self.assertIn("api.F.otype.maxSlot == 2", text)
        self.assertIn("api.F.catss_lxx_plus.v(2) == 1", text)


if __name__ == "__main__":
    unittest.main()
