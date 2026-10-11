"""#237 RED: canonical, immutable CUC Burns parent-bound producer registration.

Contract deliberately checks only executable registry wiring, not redistribution
of Burns Workbooks or unreviewed upstream head state.
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
CF_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(CF_SRC) not in sys.path:
    sys.path.insert(0, str(CF_SRC))

from agora_context_fabric.catalog import Catalog

UPSTREAM_COMMIT = "f58b162197ad8f113b7cd6fc0088ae5dd39a096d"
CUC_COMMIT = "0408967b1808c1f22c69e299d302b1e7b5e26354"


class CtcBurnsCanonicalProducerRegistrationRedTests(unittest.TestCase):
    @staticmethod
    def registry():
        return yaml.safe_load((ROOT / "registry/materializers.yaml").read_text())

    def test_ctc_burns_is_pinned_to_reviewed_real_upstream_manifest(self):
        plugins = self.registry()["plugins"]
        matches = [p for p in plugins if p["id"] == "cuc-burns"]
        self.assertEqual(len(matches), 1)
        p = matches[0]
        self.assertEqual(p["repository"], "alexsosn/CTC-TF")
        self.assertEqual(p["ref"], UPSTREAM_COMMIT)
        self.assertEqual(p["version"], "0.3.0")
        self.assertEqual(p["manifest"], "agora.materializer.json")
        self.assertEqual(p["materializers"], ["cuc-burns-csv"])
        self.assertEqual(p["package"], {
            "type": "python-project", "path": ".",
            "install_trust": "explicit-code-execution",
        })
        self.assertEqual(p["release_tracking"], {"mode": "disabled"})
        self.assertEqual(p["licenses"]["software"], "MIT")

    def test_local_feature_module_is_bound_to_only_pinned_cuc_burns_producer(self):
        catalog = Catalog.from_plugin_root(ROOT / "plugins/context-fabric")
        parent = catalog.get("cuc")
        module = catalog.get("cuc-burns")
        self.assertEqual(parent.kind, "corpus")
        self.assertEqual(parent.ref, CUC_COMMIT)
        self.assertEqual(parent.tf_path, "tf/0.2.8")
        self.assertEqual(module.kind, "feature-module")
        self.assertEqual(module.parent, "cuc")
        self.assertEqual(module.parent_versions, ("0.2.8",))
        self.assertEqual(module.acquisition_strategy, "local-module")
        self.assertEqual(module.materializer, {
            "plugin": "cuc-burns", "id": "cuc-burns-csv"
        })
        self.assertEqual(module.dependencies[0]["role"], "parent-base")
        self.assertEqual(module.dependencies[0]["ref"], parent.ref)

    def test_producer_binding_is_mirrored_to_canonical_and_bundled_resource(self):
        for path in (
            ROOT / "registry/feature-modules.yaml",
            ROOT / "plugins/context-fabric/resources/feature-modules.yaml",
        ):
            with self.subTest(file=str(path)):
                doc = yaml.safe_load(path.read_text())
                matches = [m for m in doc["resources"] if m["id"] == "cuc-burns"]
                self.assertEqual(len(matches), 1)
                m = matches[0]
                self.assertEqual(m["acquisition"]["strategy"], "local-module")
                self.assertEqual(m["acquisition"]["materializer"], {
                    "plugin": "cuc-burns", "id": "cuc-burns-csv"
                })
                self.assertEqual(m["licenses"]["redistribution"], "restricted")

    def test_no_deprecated_standalone_row_slot_burns_converter_registered(self):
        plugins = self.registry()["plugins"]
        for p in plugins:
            self.assertFalse(
                any(x.startswith("burns-convert") or x == "convert" for x in p["materializers"]),
                p["id"],
            )


if __name__ == "__main__":
    unittest.main()
