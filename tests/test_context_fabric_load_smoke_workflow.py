from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "context-fabric-load-smoke.yml"


class ContextFabricLoadSmokeWorkflowTests(unittest.TestCase):
    def test_collection_index_changes_retrigger_pull_request_and_push_smoke(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for watched_path in (
            "registry/collections/**",
            "plugins/context-fabric/resources/collections/**",
        ):
            line = f"      - '{watched_path}'"
            self.assertEqual(
                text.count(line),
                2,
                f"{watched_path} must trigger both pull_request and push smoke runs",
            )

    def test_cold_load_smoke_is_executed_and_retriggers_on_changes(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        watched = "      - 'scripts/smoke_context_fabric_cold_load.py'"
        self.assertEqual(
            text.count(watched),
            2,
            "the contained cold-load smoke must retrigger both pull_request and push runs",
        )
        self.assertIn(
            "run: python scripts/smoke_context_fabric_cold_load.py",
            text,
        )


if __name__ == "__main__":
    unittest.main()
