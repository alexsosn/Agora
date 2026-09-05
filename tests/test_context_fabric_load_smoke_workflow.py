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


if __name__ == "__main__":
    unittest.main()
