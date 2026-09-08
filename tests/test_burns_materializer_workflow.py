from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/materializer-install.yml"


class BurnsMaterializerWorkflowTests(unittest.TestCase):
    def test_registered_install_workflow_exercises_burns_runtime_and_csv_materialization(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        for required in (
            "ugarit-context-parsing:",
            "fetch ugarit-context-parsing",
            "install ugarit-context-parsing",
            "burns-workbooks-csv-text-fabric",
            "burns-workbooks-pdf-text-fabric",
            "scripts/agora_materialize_registered.py",
            "--plugin ugarit-context-parsing",
            '--install-root "$RUNNER_TEMP/materializers"',
            "conversion-report.json",
            "cuc_tablet",
            "bubblewrap",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

        self.assertNotIn(
            '--manifest "$UGARIT_RUNTIME/agora.materializer.json"',
            text,
            "RED 3: Burns acceptance must no longer manually select the managed runtime manifest",
        )

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
