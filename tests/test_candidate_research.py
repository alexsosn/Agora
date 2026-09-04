from __future__ import annotations

import copy
import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

from scripts.query_candidates import filter_candidates, main as query_main
from scripts.validate_registry import ROOT, validate_registry


class CandidateResearchValidationTests(unittest.TestCase):
    def make_root(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        shutil.copytree(ROOT / "registry", root / "registry")
        shutil.copytree(ROOT / "research", root / "research")
        return root

    def mutate_candidates(self, mutate):
        root = self.make_root()
        path = root / "research/candidates.yaml"
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        mutate(doc)
        path.write_text(
            yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return validate_registry(root)

    def test_current_candidate_research_is_valid(self):
        self.assertEqual(validate_registry(), [])

    def test_duplicate_candidate_id_is_rejected(self):
        def mutate(doc):
            doc["candidates"].append(copy.deepcopy(doc["candidates"][0]))

        errors = self.mutate_candidates(mutate)
        self.assertTrue(any("candidate research: duplicate id" in error for error in errors), errors)

    def test_unknown_canonical_taxonomy_values_are_rejected(self):
        def mutate(doc):
            candidate = doc["candidates"][0]
            candidate["taxonomy"]["capabilities"] = ["made-up-capability"]
            candidate["taxonomy"]["disciplines"] = ["made-up-discipline"]
            candidate["taxonomy"]["resource_kinds"] = ["made-up-kind"]

        errors = self.mutate_candidates(mutate)
        self.assertTrue(any("made-up-capability" in error for error in errors), errors)
        self.assertTrue(any("made-up-discipline" in error for error in errors), errors)
        self.assertTrue(any("made-up-kind" in error for error in errors), errors)

    def test_missing_narrative_source_path_is_rejected(self):
        def mutate(doc):
            doc["candidates"][0]["sources"][0]["notes"] = "wiki/backlog/does-not-exist.md"

        errors = self.mutate_candidates(mutate)
        self.assertTrue(any("missing narrative source" in error for error in errors), errors)

    def test_duplicate_evidence_snapshot_date_is_rejected(self):
        def mutate(doc):
            candidate = doc["candidates"][0]
            candidate["evidence"].append(copy.deepcopy(candidate["evidence"][0]))

        errors = self.mutate_candidates(mutate)
        self.assertTrue(any("duplicate evidence checked_at" in error for error in errors), errors)

    def test_promoted_candidate_requires_release_target(self):
        def mutate(doc):
            candidate = doc["candidates"][0]
            candidate["promotion"] = {"status": "promoted", "targets": []}

        errors = self.mutate_candidates(mutate)
        self.assertTrue(any("promoted candidate requires at least one target" in error for error in errors), errors)


class CandidateResearchQueryTests(unittest.TestCase):
    def setUp(self):
        self.candidates = [
            {
                "id": "p0-unknown",
                "priority": "P0",
                "assessment": {"technical_readiness": "blocked"},
                "legal": {
                    "data_license": {"status": "unknown"},
                    "authentication": "unknown",
                },
                "annotation_maturity": "unknown",
                "evidence": [{"live_smoke": {"status": "not-tested"}}],
            },
            {
                "id": "p0-smoked",
                "priority": "P0",
                "assessment": {"technical_readiness": "ready"},
                "legal": {
                    "data_license": {"status": "known"},
                    "authentication": "none",
                },
                "annotation_maturity": "manually-reviewed",
                "evidence": [{"live_smoke": {"status": "success"}}],
            },
            {
                "id": "p1-smoked",
                "priority": "P1",
                "assessment": {"technical_readiness": "promising"},
                "legal": {
                    "data_license": {"status": "unknown"},
                    "authentication": "required",
                },
                "annotation_maturity": "mixed",
                "evidence": [{"live_smoke": {"status": "success"}}],
            },
        ]

    def test_filters_are_conjunctive(self):
        matches = filter_candidates(
            self.candidates,
            priority="P0",
            data_license_status="unknown",
        )
        self.assertEqual([candidate["id"] for candidate in matches], ["p0-unknown"])

    def test_live_smoke_filter_uses_latest_evidence_snapshot(self):
        candidates = copy.deepcopy(self.candidates)
        candidates[0]["evidence"].append({"live_smoke": {"status": "success"}})
        matches = filter_candidates(candidates, live_smoke="success")
        self.assertEqual(
            [candidate["id"] for candidate in matches],
            ["p0-smoked", "p0-unknown", "p1-smoked"],
        )

    def test_ids_only_cli_is_stable_and_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "candidates.yaml"
            path.write_text(
                yaml.safe_dump(
                    {"schema_version": 1, "candidates": list(reversed(self.candidates))},
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            output = io.StringIO()
            argv = [
                "query_candidates.py",
                "--file",
                str(path),
                "--live-smoke",
                "success",
                "--ids-only",
            ]
            with patch("sys.argv", argv), redirect_stdout(output):
                self.assertEqual(query_main(), 0)

        self.assertEqual(output.getvalue().splitlines(), ["p0-smoked", "p1-smoked"])


if __name__ == "__main__":
    unittest.main()
