from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts import smoke_context_fabric_resources as smoke

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "context-fabric-load-smoke.yml"

EXPECTED_CELLS = (
    {"case": "bhsa", "check_id": "resource-load/bhsa"},
    {"case": "cuc", "check_id": "resource-load/cuc"},
    {"case": "greek-iliad", "check_id": "member-load/greek-iliad"},
    {"case": "greek-known-bad", "check_id": "member-canary/greek-argonautica"},
)


def _workflow_document():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _render(value: str, cell: dict[str, str]) -> str:
    rendered = value
    for key, selected in cell.items():
        rendered = rendered.replace(f"${{{{ matrix.{key} }}}}", selected)
    return rendered


class ResourceMemberLiveWorkflowRed3Tests(unittest.TestCase):
    def matrix_cells(self):
        job = (_workflow_document().get("jobs") or {}).get("representative-loads") or {}
        matrix = ((job.get("strategy") or {}).get("matrix") or {})
        return [cell for cell in matrix.get("include", []) if isinstance(cell, dict)]

    def representative_steps(self):
        job = (_workflow_document().get("jobs") or {}).get("representative-loads") or {}
        return [step for step in job.get("steps", []) if isinstance(step, dict)]

    def test_four_existing_cases_have_exact_matrix_cells_and_stable_check_ids(self):
        actual = tuple(
            {"case": cell.get("case"), "check_id": cell.get("check_id")}
            for cell in self.matrix_cells()
        )
        self.assertEqual(actual, EXPECTED_CELLS)

    def test_each_case_cell_uploads_a_unique_artifact(self):
        upload = next(
            (
                step
                for step in self.representative_steps()
                if isinstance(step.get("uses"), str)
                and step["uses"].startswith("actions/upload-artifact@")
            ),
            None,
        )
        self.assertIsNotNone(upload, "representative case matrix must upload evidence")
        template = ((upload or {}).get("with") or {}).get("name")
        self.assertIsInstance(template, str)
        rendered = [_render(template, cell) for cell in EXPECTED_CELLS]
        self.assertEqual(len(set(rendered)), len(EXPECTED_CELLS), rendered)

    def test_cold_load_smoke_executes_once_outside_case_matrix(self):
        jobs = _workflow_document().get("jobs") or {}
        owners = []
        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                continue
            for step in job.get("steps", []):
                run = step.get("run") if isinstance(step, dict) else None
                if isinstance(run, str) and "scripts/smoke_context_fabric_cold_load.py" in run:
                    owners.append(job_id)
        self.assertEqual(len(owners), 1, owners)
        self.assertNotEqual(owners[0] if owners else None, "representative-loads")

    def test_case_cells_do_not_share_one_mutable_cache_directory(self):
        cache_step = next(
            (
                step
                for step in self.representative_steps()
                if isinstance(step.get("uses"), str) and step["uses"].startswith("actions/cache@")
            ),
            None,
        )
        self.assertIsNotNone(cache_step)
        cache_path = (((cache_step or {}).get("with") or {}).get("path"))
        cache_key = (((cache_step or {}).get("with") or {}).get("key"))
        self.assertIsInstance(cache_path, str)
        self.assertIsInstance(cache_key, str)
        paths = [_render(cache_path, cell) for cell in EXPECTED_CELLS]
        keys = [_render(cache_key, cell) for cell in EXPECTED_CELLS]
        self.assertEqual(len(set(paths)), len(EXPECTED_CELLS), paths)
        self.assertEqual(len(set(keys)), len(EXPECTED_CELLS), keys)

    def test_verification_registry_and_schema_changes_retrigger_real_loads(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for watched_path in (
            "registry/verification-checks.yaml",
            "registry/schema/verification-checks.schema.json",
        ):
            line = f"      - '{watched_path}'"
            self.assertEqual(
                text.count(line),
                2,
                f"{watched_path} must retrigger pull_request and push representative loads",
            )

    def test_smoke_runner_accepts_check_id_and_exposes_exact_binding_validator(self):
        self.assertIn("check_id", inspect.signature(smoke.run_case).parameters)
        validator = getattr(smoke, "validate_case_check_binding", None)
        self.assertTrue(callable(validator), "smoke runner needs an exact case/check binding validator")

    def test_binding_validator_rejects_wrong_resource_subject(self):
        validator = getattr(smoke, "validate_case_check_binding", None)
        self.assertTrue(callable(validator), "smoke runner needs an exact case/check binding validator")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry"
            registry.mkdir()
            (registry / "verification-checks.yaml").write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "checks": [
                            {
                                "id": "resource-load/bhsa",
                                "kind": "live",
                                "plugin": "context-fabric",
                                "provider": "context-fabric",
                                "evidence_level": "community",
                                "subject": {"type": "resource", "resource_id": "cuc"},
                                "claims": ["materialization", "load", "representative-content"],
                            }
                        ],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "subject"):
                validator("bhsa", "resource-load/bhsa", member_id=None, root=root)


if __name__ == "__main__":
    unittest.main()
