"""#270 RED: the published BHSA cantillation module must use its reviewed Git commit.

Real upstream tree check (2026-10-12): 23 tf/2021/*.tf blobs identical in
reviewed 445413f and moving upstream 19a2fab. Pin revision identity rather
than weakening the semantic smoke's exact-source assertion.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/context-fabric/src"))

from agora_context_fabric.catalog import Catalog

MODULE_ID = "bhsa-cantillation-trees"
PIN = "445413fa5267b5c1c637d523f07f8a4cf0b3dded"


class CantillationPinnedSource270Tests(unittest.TestCase):
    def test_canonical_and_installed_module_pin_exact_semantic_smoke_revision(self):
        registry = yaml.safe_load((ROOT / "registry/feature-modules.yaml").read_text())
        rows = [r for r in registry["resources"] if r["id"] == MODULE_ID]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["upstream"]["ref"], PIN)
        self.assertEqual(row["upstream"]["tf_path"], "tf/2021")
        self.assertEqual(row["upstream"]["repository"], "alexsosn/BHSA-cantillation-trees")
        original = Catalog.from_registry(ROOT).get(MODULE_ID)
        packaged = Catalog.from_plugin_root(ROOT / "plugins/context-fabric").get(MODULE_ID)
        self.assertEqual(original, packaged)
        self.assertEqual(original.ref, PIN)
        self.assertEqual(original.parent, "bhsa")
        self.assertEqual(original.parent_versions, ("2021",))
        self.assertEqual(original.verification_status, "community")
        from scripts import smoke_context_fabric_resources as smoke
        self.assertEqual(smoke.LOAD_CASES["bhsa-cantillation"].expected_module_revision, PIN)
        self.assertNotEqual(PIN, "19a2fab1cf4e5c418782539c507301d3fa353bd1")

    def test_cantillation_data_upstream_remains_separate_from_bhsa_parent(self):
        parent = Catalog.from_registry(ROOT).get("bhsa")
        module = Catalog.from_registry(ROOT).get(MODULE_ID)
        self.assertNotEqual(parent.repository, module.repository)
        self.assertEqual(parent.kind, "corpus")
        self.assertEqual(module.kind, "feature-module")
        self.assertEqual(module.module_path, "alexsosn/BHSA-cantillation-trees/tf")
        self.assertEqual(module.acquisition_strategy, "repository")
        self.assertEqual(module.dependencies[0]["repository"], "openscriptures/morphhb")


if __name__ == "__main__":
    unittest.main()
