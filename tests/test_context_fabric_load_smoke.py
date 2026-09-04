from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.smoke_context_fabric_resources import (
    LOAD_CASES,
    SEMANTIC_EXPECTATIONS,
    SemanticExpectation,
    check_semantic_expectations,
    select_collection_member,
    summarize_loaded_corpus,
)


class _Feature:
    def __init__(self, values):
        self.values = values

    def v(self, node):
        return self.values.get(node)


class ContextFabricLoadSmokeTests(unittest.TestCase):
    def test_cases_cover_two_core_corpora_and_one_lazy_greek_member(self):
        self.assertEqual(set(LOAD_CASES), {"bhsa", "cuc", "greek-iliad"})

        self.assertEqual(LOAD_CASES["bhsa"].resource_id, "bhsa")
        self.assertIsNone(LOAD_CASES["bhsa"].member_path_contains)
        self.assertEqual(LOAD_CASES["bhsa"].features, ("g_cons", "sp"))

        self.assertEqual(LOAD_CASES["cuc"].resource_id, "cuc")
        self.assertIsNone(LOAD_CASES["cuc"].member_path_contains)
        self.assertEqual(LOAD_CASES["cuc"].features, ("sign", "usign"))

        iliad = LOAD_CASES["greek-iliad"]
        self.assertEqual(iliad.resource_id, "greek_literature")
        self.assertEqual(
            iliad.member_path_contains,
            "canonical-greekLit/tlg0012/tlg001/perseus-grc2/1/tf/1.0",
        )
        self.assertEqual(iliad.features, ("orig", "main"))

    def test_each_real_case_has_narrow_semantic_expectations(self):
        self.assertEqual(set(SEMANTIC_EXPECTATIONS), set(LOAD_CASES))
        self.assertEqual(
            [(item.feature, item.node) for item in SEMANTIC_EXPECTATIONS["bhsa"]],
            [("g_cons", 1), ("g_cons", 2), ("sp", 1), ("sp", 2)],
        )
        self.assertEqual(
            [(item.feature, item.node) for item in SEMANTIC_EXPECTATIONS["cuc"]],
            [("sign", 1), ("usign", 1)],
        )
        self.assertEqual(
            [(item.feature, item.node) for item in SEMANTIC_EXPECTATIONS["greek-iliad"]],
            [("orig", 1), ("main", 1)],
        )

    def test_collection_member_selection_requires_one_exact_path_match(self):
        members = [
            SimpleNamespace(
                id="iliad",
                relative_path=(
                    "canonical-greekLit/tlg0012/tlg001/perseus-grc2/1/tf/1.0"
                ),
            ),
            SimpleNamespace(
                id="odyssey",
                relative_path=(
                    "canonical-greekLit/tlg0012/tlg002/perseus-grc2/1/tf/1.0"
                ),
            ),
        ]

        selected = select_collection_member(
            members,
            "canonical-greekLit/tlg0012/tlg001/perseus-grc2/1/tf/1.0",
        )
        self.assertEqual(selected.id, "iliad")

        with self.assertRaisesRegex(ValueError, "no collection member"):
            select_collection_member(members, "tlg9999")

        duplicate = SimpleNamespace(
            id="iliad-copy",
            relative_path=(
                "copy/canonical-greekLit/tlg0012/tlg001/perseus-grc2/1/tf/1.0"
            ),
        )
        with self.assertRaisesRegex(ValueError, "multiple collection members"):
            select_collection_member(
                [*members, duplicate],
                "canonical-greekLit/tlg0012/tlg001/perseus-grc2/1/tf/1.0",
            )

    def test_semantic_comparison_normalizes_unicode_and_reports_the_check(self):
        api = SimpleNamespace(
            F=SimpleNamespace(token=_Feature({1: "μῆνιν "}))
        )
        checks = check_semantic_expectations(
            "example",
            api,
            (SemanticExpectation("token", 1, "μῆνιν"),),
        )

        self.assertEqual(
            checks,
            [
                {
                    "feature": "token",
                    "node": 1,
                    "expected": "μῆνιν",
                    "actual": "μῆνιν",
                }
            ],
        )

    def test_semantic_comparison_fails_closed_on_missing_or_wrong_values(self):
        api = SimpleNamespace(F=SimpleNamespace(token=_Feature({1: "wrong"})))
        expectation = (SemanticExpectation("token", 1, "expected"),)

        with self.assertRaisesRegex(RuntimeError, "expected.*wrong"):
            check_semantic_expectations("example", api, expectation)

        missing_feature_api = SimpleNamespace(F=SimpleNamespace())
        with self.assertRaisesRegex(RuntimeError, "feature.*token"):
            check_semantic_expectations("example", missing_feature_api, expectation)

    def test_loaded_corpus_summary_requires_tf_data_loader_result_revision_and_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "tf" / "1.0"
            dataset.mkdir(parents=True)
            (dataset / "otype.tf").write_text("@node\n", encoding="utf-8")

            result = {
                "resource_id": "example",
                "member_id": "member-1",
                "logical_name": "example:member-1",
                "relative_path": "tf/1.0",
                "path": str(dataset),
                "source_revision": "a" * 40,
                "corpus": {"name": "example", "loaded": True},
            }
            checks = [
                {
                    "feature": "token",
                    "node": 1,
                    "expected": "known",
                    "actual": "known",
                }
            ]

            summary = summarize_loaded_corpus("example", result, checks)
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(summary["resource_id"], "example")
            self.assertEqual(summary["member_id"], "member-1")
            self.assertEqual(summary["relative_path"], "tf/1.0")
            self.assertEqual(summary["source_revision"], "a" * 40)
            self.assertTrue(summary["has_otype"])
            self.assertEqual(summary["corpus_info_type"], "dict")
            self.assertEqual(summary["semantic_checks"], checks)

            (dataset / "otype.tf").unlink()
            with self.assertRaisesRegex(RuntimeError, "otype.tf"):
                summarize_loaded_corpus("example", result, checks)

            (dataset / "otype.tf").write_text("@node\n", encoding="utf-8")
            result["corpus"] = None
            with self.assertRaisesRegex(RuntimeError, "no corpus information"):
                summarize_loaded_corpus("example", result, checks)

            result["corpus"] = {"name": "example", "loaded": True}
            result["source_revision"] = None
            with self.assertRaisesRegex(RuntimeError, "source revision"):
                summarize_loaded_corpus("example", result, checks)

            result["source_revision"] = "a" * 40
            with self.assertRaisesRegex(RuntimeError, "semantic checks"):
                summarize_loaded_corpus("example", result, [])


if __name__ == "__main__":
    unittest.main()
