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
            "scripts/agora_materialize.py",
            "conversion-report.json",
            "cuc_tablet",
            "bubblewrap",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
