from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.smoke_context_fabric_resources import (
    LOAD_CASES,
    summarize_loaded_corpus,
    select_collection_member,
)


class ContextFabricLoadSmokeTests(unittest.TestCase):
    def test_cases_cover_two_core_corpora_and_one_lazy_greek_member(self):
        self.assertEqual(set(LOAD_CASES), {"bhsa", "cuc", "greek-iliad"})

        self.assertEqual(LOAD_CASES["bhsa"].resource_id, "bhsa")
        self.assertIsNone(LOAD_CASES["bhsa"].member_path_contains)

        self.assertEqual(LOAD_CASES["cuc"].resource_id, "cuc")
        self.assertIsNone(LOAD_CASES["cuc"].member_path_contains)

        iliad = LOAD_CASES["greek-iliad"]
        self.assertEqual(iliad.resource_id, "greek_literature")
        self.assertEqual(
            iliad.member_path_contains,
            "canonical-greekLit/tlg0012/tlg001/perseus-grc2/1/tf/1.0",
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

    def test_loaded_corpus_summary_requires_materialized_tf_data_and_loader_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "tf" / "1.0"
            dataset.mkdir(parents=True)
            (dataset / "otype.tf").write_text("@node\n", encoding="utf-8")

            result = {
                "resource_id": "example",
                "member_id": None,
                "logical_name": "example",
                "relative_path": "tf/1.0",
                "path": str(dataset),
                "corpus": {"name": "example", "loaded": True},
            }

            summary = summarize_loaded_corpus("example", result)
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(summary["resource_id"], "example")
            self.assertEqual(summary["relative_path"], "tf/1.0")
            self.assertTrue(summary["has_otype"])
            self.assertEqual(summary["corpus_info_type"], "dict")

            (dataset / "otype.tf").unlink()
            with self.assertRaisesRegex(RuntimeError, "otype.tf"):
                summarize_loaded_corpus("example", result)

            (dataset / "otype.tf").write_text("@node\n", encoding="utf-8")
            result["corpus"] = None
            with self.assertRaisesRegex(RuntimeError, "no corpus information"):
                summarize_loaded_corpus("example", result)


if __name__ == "__main__":
    unittest.main()
