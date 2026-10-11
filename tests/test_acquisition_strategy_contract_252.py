"""#252 RED: registry and consumer refuse imaginary acquisition strategies."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "context-fabric"
PLUGIN_SRC = PLUGIN_ROOT / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog
from scripts.validate_registry import validate_registry


class AcquisitionStrategyValidation252Tests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(
            (ROOT / "registry/schema/resources.schema.json").read_text(encoding="utf-8")
        )
        self.resources = yaml.safe_load(
            (ROOT / "registry/resources.yaml").read_text(encoding="utf-8")
        )
        self.modules = yaml.safe_load(
            (ROOT / "registry/feature-modules.yaml").read_text(encoding="utf-8")
        )
        self.validator = Draft202012Validator(self.schema)

    def test_real_corpus_collection_and_burns_local_module_remain_valid(self):
        self.assertEqual([], validate_registry())
        allowed = {"repository", "collection", "local-module"}
        values = {
            row["acquisition"]["strategy"]
            for doc in (self.resources, self.modules)
            for row in doc["resources"]
        }
        self.assertEqual(allowed, values)
        self.assertFalse(list(self.validator.iter_errors(self.resources)))
        self.assertFalse(list(self.validator.iter_errors(self.modules)))
        registry = Catalog.from_registry(ROOT)
        bundled = Catalog.from_plugin_root(PLUGIN_ROOT)
        self.assertTrue(registry.ids())
        self.assertTrue(bundled.ids())
        self.assertEqual("local-module", registry.get("cuc-burns").acquisition_strategy)

    def test_schema_rejects_misspelled_or_speculative_unimplemented_strategies(self):
        for document in (self.resources, self.modules):
            for value in ("reposiotry", "github-release-archive", "auto-git", ""):
                with self.subTest(value=value):
                    mutated = copy.deepcopy(document)
                    mutated["resources"][0]["acquisition"]["strategy"] = value
                    errors = list(self.validator.iter_errors(mutated))
                    self.assertTrue(errors, "unknown strategy must fail schema validation")
                    self.assertTrue(
                        any("strategy" in str(e.path) for e in errors), errors
                    )

    def test_runtime_catalog_rejects_explicit_unknown_strategy_before_discovery(self):
        for doc in (self.resources, self.modules):
            for value in ("reposiotry", "github-release-archive", "", None):
                with self.subTest(value=value):
                    mutated = copy.deepcopy(doc["resources"][0])
                    mutated["acquisition"]["strategy"] = value
                    with self.assertRaisesRegex(
                        ValueError, "unsupported acquisition strategy"
                    ):
                        Catalog._resources_from_document({"resources": [mutated]})

    def test_schema_enumeration_matches_runtime_known_values(self):
        acquisition = self.schema["properties"]["resources"]["items"]["properties"]["acquisition"]
        enum = acquisition["properties"]["strategy"]["enum"]
        self.assertEqual({"repository", "collection", "local-module"}, set(enum))


if __name__ == "__main__":
    unittest.main()
