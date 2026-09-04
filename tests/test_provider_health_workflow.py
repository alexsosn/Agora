from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProviderHealthWorkflowTests(unittest.TestCase):
    def test_provider_health_changes_trigger_live_observation_workflow(self):
        workflow = (ROOT / ".github/workflows/external-mcp-smoke.yml").read_text(encoding="utf-8")
        for path in (
            "registry/providers.yaml",
            "registry/schema/providers.schema.json",
        ):
            self.assertIn(f'"{path}"', workflow, path)


if __name__ == "__main__":
    unittest.main()
