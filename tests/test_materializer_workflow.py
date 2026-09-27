from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/materializer-install.yml"


class MaterializerWorkflowTests(unittest.TestCase):
    def test_registered_runner_changes_retrigger_live_install_smoke(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertGreaterEqual(
            text.count("'scripts/agora_materialize_registered.py'"),
            2,
            "registered runner must retrigger both push and pull_request workflow paths",
        )
        self.assertGreaterEqual(
            text.count("'tests/test_materializer_run_by_id.py'"),
            2,
            "runner contract changes must retrigger both push and pull_request workflow paths",
        )


if __name__ == "__main__":
    unittest.main()
