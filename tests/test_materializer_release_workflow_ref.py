from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/materializer-release-updates.yml"


class MaterializerReleaseWorkflowRefTests(unittest.TestCase):
    def test_checkout_step_explicitly_starts_from_canonical_main(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        checkout_start = text.index("uses: actions/checkout@v4")
        setup_start = text.index("- name: Set up Python", checkout_start)
        checkout_block = text[checkout_start:setup_start]
        self.assertIn(
            "ref: main",
            checkout_block,
            "workflow_dispatch may select a non-main ref; the bot branch must always start from canonical main",
        )


if __name__ == "__main__":
    unittest.main()
