"""#227 RED: actual registered cantillation tree module over the BHSA warp."""
from __future__ import annotations

import ast
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SMOKE_PATH = ROOT / "scripts/smoke_context_fabric_resources.py"
WORKFLOW = ROOT / ".github/workflows/context-fabric-load-smoke.yml"
CF_SRC = ROOT / "plugins/context-fabric/src"
if str(CF_SRC) not in sys.path:
    sys.path.insert(0, str(CF_SRC))


class BhsaCantillationRealSourceRedTests(unittest.TestCase):
    def test_optional_case_is_bhsa_2021_and_not_a_new_corpus(self):
        from scripts import smoke_context_fabric_resources as smoke
        case = smoke.LOAD_CASES["bhsa-cantillation"]
        self.assertEqual(case.resource_id, "bhsa")
        self.assertEqual(case.modules, ("bhsa-cantillation-trees",))
        self.assertEqual(case.version, "2021")
        self.assertIn("bhsa", smoke.LOAD_CASES)
        self.assertEqual(smoke.LOAD_CASES["bhsa"].modules, ())

    def test_semantics_cover_actual_upstream_verse_and_bhsa_genesis_words(self):
        from scripts import smoke_context_fabric_resources as smoke
        expectations = {
            (x.feature, x.node, x.expected)
            for x in smoke.SEMANTIC_EXPECTATIONS["bhsa-cantillation"]
        }
        self.assertIn(("g_cons", 1, "B"), expectations)
        self.assertIn(("g_cons", 2, "R>CJT"), expectations)
        # @node BHSA verse 1414389 from real published module.
        self.assertIn(("cantillation_system", 1414389, "prose"), expectations)
        self.assertIn(("cantillation_depth", 1414389, "2"), expectations)
        self.assertIn(("cantillation_alignment", 1414389, "exact"), expectations)

    def test_runtime_passes_explicit_parent_version_to_context_fabric(self):
        program = ast.parse(SMOKE_PATH.read_text(encoding="utf-8"))
        assignments = [
            node for node in ast.walk(program)
            if isinstance(node, ast.Assign)
            and any(isinstance(x, ast.Name) and x.id == "load_kwargs" for x in node.targets)
        ]
        self.assertTrue(assignments)
        text = SMOKE_PATH.read_text(encoding="utf-8")
        self.assertIn('load_kwargs["version"] = case.version', text)

    def test_exact_head_real_cold_load_is_executed_by_workflow(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("bhsa-cantillation", content)
        self.assertIn("python scripts/smoke_context_fabric_resources.py", content)
        self.assertIn("--cache-dir", content)
        self.assertIn("persist-credentials: false", content)
        self.assertIn("github.event.pull_request.head.sha || github.sha", content)
        self.assertIn("Install Context-Fabric runtime", content)

    def test_incompatible_parent_version_and_unknown_module_fail_before_acquisition(self):
        from agora_context_fabric.catalog import Catalog
        from agora_context_fabric.resolver import ContextFabricResolver, PreparedCorpus
        from unittest import mock
        catalog = Catalog.from_plugin_root(ROOT / "plugins/context-fabric")
        store = mock.Mock()
        resolver = ContextFabricResolver(catalog, store)
        wrong = PreparedCorpus(
            resource_id="bhsa", member_id=None, logical_name="bhsa@1935",
            relative_path="tf/1935", path=Path("/unused-parent"),
            version="1935", source_revision="a" * 40,
        )
        with self.assertRaisesRegex(ValueError, "compatible|not compatible"):
            resolver._prepare_feature_modules(wrong, ["bhsa-cantillation-trees"])
        store.materialize_feature_module.assert_not_called()
        store.ensure_metadata.assert_not_called()

        valid = PreparedCorpus(
            resource_id="bhsa", member_id=None, logical_name="bhsa@2021",
            relative_path="tf/2021", path=Path("/unused-parent"),
            version="2021", source_revision="a" * 40,
        )
        with self.assertRaises(KeyError):
            resolver._prepare_feature_modules(valid, ["missing-module"])
        store.materialize_feature_module.assert_not_called()

    def test_missing_cantillation_feature_is_a_failure_not_a_core_bhsa_failure(self):
        from scripts import smoke_context_fabric_resources as smoke
        from types import SimpleNamespace

        api = SimpleNamespace(
            F=SimpleNamespace(g_cons=SimpleNamespace(v=lambda node: "B"))
        )
        with self.assertRaisesRegex(RuntimeError, "cantillation_system"):
            smoke.check_semantic_expectations(
                "bhsa-cantillation", api,
                (smoke.SemanticExpectation("cantillation_system", 1414389, "prose"),),
            )
        self.assertNotIn("cantillation_system", [x.feature for x in
                          smoke.SEMANTIC_EXPECTATIONS["bhsa"]])

    def test_pinned_source_not_incorrectly_promoted_to_verified(self):
        from agora_context_fabric.catalog import Catalog
        catalog = Catalog.from_plugin_root(ROOT / "plugins/context-fabric")
        module = catalog.get("bhsa-cantillation-trees")
        self.assertEqual(module.kind, "feature-module")
        self.assertEqual(module.parent, "bhsa")
        self.assertEqual(module.verification_status, "community")
        self.assertEqual(module.parent_versions, ("2021",))
        self.assertEqual(module.acquisition_strategy, "repository")


if __name__ == "__main__":
    unittest.main()
