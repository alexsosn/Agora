"""#267 RED: opt-in pinned Tischendorf 2.8 morphology feature module.

Fixture filenames are derived from the actual canonical Git tree
codykingham/tischendorf_tf@ca96bd44f38fd716d4a1faa6d451f3716f0dce46.
No upstream network access in deterministic unit tests.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "plugins/context-fabric/src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agora_context_fabric.catalog import Catalog
from agora_context_fabric.gitstore import GitStore
from scripts.generate_context_fabric_catalog import build_feature_modules_document

ID = "tischendorf-morphology-additions"
PIN = "ca96bd44f38fd716d4a1faa6d451f3716f0dce46"
NAMES = frozenset((
    "case.tf", "freq_lex_og.tf", "gn.tf", "lex_abc.tf",
    "lex_og.tf", "mood.tf", "nountype.tf", "nu.tf",
    "originterrdiff.tf", "prntyp.tf", "ps.tf", "sp.tf",
    "voice.tf", "vt.tf",
))
PARENT_FEATURES = frozenset((
    "anlex_lem.tf", "book.tf", "book_code.tf", "chapter.tf",
    "freq_lex.tf", "gloss.tf", "ketiv.tf", "morph.tf",
    "oslots.tf", "otext.tf", "otype.tf", "para.tf", "qere.tf",
    "str_lem.tf", "strongs.tf", "verse.tf", "vrsnum.tf",
))


class TischendorfMorphology267Tests(unittest.TestCase):
    def setUp(self):
        modules = yaml.safe_load((ROOT / "registry/feature-modules.yaml").read_text())
        self.rows = [row for row in modules["resources"] if row["id"] == ID]
        self.catalog = Catalog.from_registry(ROOT)
        self.bundled = Catalog.from_plugin_root(ROOT / "plugins/context-fabric")

    def test_opt_in_with_exact_parent_source_and_direct_directory(self):
        self.assertEqual(1, len(self.rows))
        row = self.rows[0]
        feature = self.catalog.get(ID)
        self.assertEqual(feature, self.bundled.get(ID))
        self.assertEqual(feature.parent, "tischendorf_tf")
        self.assertEqual(feature.parent_versions, ("2.8",))
        self.assertEqual(feature.kind, "feature-module")
        self.assertEqual(feature.module_status, "optional")
        self.assertEqual(feature.repository, "codykingham/tischendorf_tf")
        self.assertEqual(feature.ref, PIN)
        self.assertEqual(feature.tf_path, "FeatureAdditions")
        self.assertEqual(feature.module_path, "codykingham/tischendorf_tf/FeatureAdditions")
        self.assertEqual(feature.acquisition_strategy, "repository")
        self.assertTrue(row["acquisition"]["lazy"])
        self.assertEqual(self.catalog.get("tischendorf_tf").kind, "corpus")
        self.assertIn(ID, [item.id for item in self.catalog.modules_for("tischendorf_tf")])
        self.assertNotIn(ID, self.catalog.ids()[:37])
        self.assertEqual(feature.dependencies, (
            {"repository": "codykingham/tischendorf_tf", "ref": PIN, "role": "parent-base"},
        ))

    def test_rights_and_provenance_preserve_canonical_source_credits(self):
        row = self.rows[0]
        self.assertEqual(row["licenses"]["data"], "public-domain")
        self.assertEqual(row["licenses"]["redistribution"], "permitted")
        self.assertEqual(row["verification"]["status"], "community")
        rights = " ".join([row["description"], row["licenses"]["notes"]]).lower()
        for phrase in ("tischendorf", "kingham", "glanz", "public domain"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rights)
        self.assertIn("/blob/" + PIN + "/LICENSE", row["licenses"]["evidence"]["sources"][0])
        schema = json.loads((ROOT / "registry/schema/resources.schema.json").read_text())
        self.assertEqual([], list(Draft202012Validator(schema).iter_errors({
            "schema_version": 1, "resources": [row]
        })))

    def test_no_warp_or_parent_filename_collisions_and_catalog_is_fresh(self):
        self.assertEqual(14, len(NAMES))
        self.assertFalse(NAMES & PARENT_FEATURES)
        self.assertFalse(NAMES & GitStore.FORBIDDEN_FEATURE_MODULE_FILES)
        expected = build_feature_modules_document(ROOT)
        actual = yaml.safe_load((
            ROOT / "plugins/context-fabric/resources/feature-modules.yaml"
        ).read_text())
        self.assertEqual(expected, actual)
        self.assertEqual(1, sum(r["id"] == ID for r in actual["resources"]))
        guide = (ROOT / "wiki/guides/resources.md").read_text()
        self.assertEqual(1, guide.count("<!-- feature-module:" + ID + " -->"))
        # Same parent is available with no opt-in: its corpus contract is unchanged.
        parent = self.catalog.get("tischendorf_tf")
        self.assertEqual(parent.acquisition_strategy, "repository")
        self.assertEqual(parent.repository, "codykingham/tischendorf_tf")
        self.assertIsNone(parent.release_archive)


if __name__ == "__main__":
    unittest.main()
