"""#217 RED: Context-Fabric manual, scheduled and main runs must never collide."""
from __future__ import annotations

from pathlib import Path
import unittest

import yaml


WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
NAMES = ("context-fabric-audit.yml", "context-fabric-load-smoke.yml")
EXPECTED_GROUP = (
    "${{ github.workflow }}-${{ github.event_name == 'pull_request' && "
    "format('pr-{0}', github.event.pull_request.number) || "
    "format('run-{0}-{1}', github.run_id, github.run_attempt) }}"
)
EXPECTED_CANCEL = "${{ github.event_name == 'pull_request' }}"


class ContextFabricIndependentRunCancellationRedTests(unittest.TestCase):
    def _read(self, name: str) -> dict:
        return yaml.load((WORKFLOWS / name).read_text(encoding="utf-8"),
                         Loader=yaml.BaseLoader)

    def test_context_fabric_audit_and_load_only_cancel_superseded_pr_runs(self):
        for name in NAMES:
            with self.subTest(name=name):
                doc = self._read(name)
                self.assertEqual(doc["concurrency"]["group"], EXPECTED_GROUP)
                self.assertEqual(doc["concurrency"]["cancel-in-progress"], EXPECTED_CANCEL)

    def test_pr_identity_and_nonpr_run_attempt_do_not_share_group(self):
        for name in NAMES:
            with self.subTest(name=name):
                group = self._read(name)["concurrency"]["group"]
                for token in ("github.workflow", "github.event_name == 'pull_request'",
                              "github.event.pull_request.number",
                              "github.run_id", "github.run_attempt"):
                    self.assertIn(token, group)

    def test_preserves_existing_dispatch_schedule_push_and_readonly_permissions(self):
        for name in NAMES:
            with self.subTest(name=name):
                doc = self._read(name)
                self.assertIn("workflow_dispatch", doc["on"])
                self.assertIn("schedule", doc["on"])
                self.assertIn("pull_request", doc["on"])
                self.assertIn("push", doc["on"])
                self.assertIn("main", doc["on"]["push"]["branches"])
                self.assertEqual(doc["permissions"], {"contents": "read"})
                self.assertTrue(doc["on"]["schedule"][0]["cron"].startswith("17 "))

    def test_unrelated_release_workflow_remains_serial_and_non_cancelable(self):
        doc = self._read("materializer-release-updates.yml")
        self.assertEqual(doc["concurrency"]["cancel-in-progress"], "false")


if __name__ == "__main__":
    unittest.main()
