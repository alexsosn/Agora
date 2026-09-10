from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "foundation.yml"


class ManagedArtifactLockWorkflowRed3bTests(unittest.TestCase):
    def test_foundation_runs_managed_artifact_lock_regressions_on_all_supported_platforms(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        workflow = yaml.safe_load(text)
        jobs = workflow["jobs"]
        matching = []
        for job_id, job in jobs.items():
            steps = job.get("steps", []) if isinstance(job, dict) else []
            commands = "\n".join(str(step.get("run", "")) for step in steps if isinstance(step, dict))
            if "test_managed_artifact_locks_red3" in commands:
                matching.append((job_id, job, commands))

        self.assertEqual(len(matching), 1, matching)
        _job_id, job, commands = matching[0]
        matrix = job.get("strategy", {}).get("matrix", {})
        self.assertEqual(
            set(matrix.get("os", [])),
            {"ubuntu-latest", "macos-latest", "windows-latest"},
        )
        self.assertEqual(job.get("runs-on"), "${{ matrix.os }}")
        self.assertIn("tests.test_managed_artifact_locks_red3", commands)


if __name__ == "__main__":
    unittest.main()
