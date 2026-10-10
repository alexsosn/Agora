"""Issue #201: exact safe concurrency contract for long read-only PR workflows.

RED before workflow edits. GitHub scheduler cancellation must additionally be
observed on two successive PR pushes before calling the issue complete.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    "foundation.yml",
    "materialization-sandbox.yml",
    "materializer-install.yml",
    "materialization-sparse-coptic.yml",
)
GROUP = (
    "${{ github.workflow }}-"
    "${{ github.event_name == 'pull_request' && "
    "format('pr-{0}', github.event.pull_request.number) || "
    "format('run-{0}-{1}', github.run_id, github.run_attempt) }}"
)
CANCEL = "${{ github.event_name == 'pull_request' }}"


class PrConcurrencyRedTests(unittest.TestCase):
    def test_readonly_integration_workflows_cancel_only_superseded_pr_heads(self):
        for filename in TARGETS:
            with self.subTest(filename=filename):
                path = ROOT / ".github" / "workflows" / filename
                doc = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
                self.assertEqual(doc["concurrency"], {
                    "group": GROUP,
                    "cancel-in-progress": CANCEL,
                })

    def test_all_pr_event_filters_and_separate_main_manual_runs_are_preserved(self):
        for filename in TARGETS:
            with self.subTest(filename=filename):
                path = ROOT / ".github" / "workflows" / filename
                doc = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
                events = doc["on"]
                self.assertIn("pull_request", events)
                self.assertIn("push", events)
                self.assertIn("main", events["push"]["branches"])
                self.assertTrue(doc["jobs"])
                self.assertEqual(doc["permissions"], {"contents": "read"})
                # PR number uniquely namespaces successive heads *within*
                # a workflow. Non-PR runs get run ID + attempt to avoid
                # quietly replacing queued main or manual runs.
                group = doc["concurrency"]["group"]
                self.assertIn("github.workflow", group)
                self.assertIn("github.event.pull_request.number", group)
                self.assertIn("github.run_id", group)
                self.assertIn("github.run_attempt", group)
                self.assertEqual(
                    doc["concurrency"]["cancel-in-progress"], CANCEL,
                )

    def test_live_external_mutation_and_release_automation_are_unmodified(self):
        for filename in (
            "materializer-release-updates.yml",
            "external-mcp-smoke.yml",
            "context-fabric-collection-index-generation.yml",
        ):
            with self.subTest(filename=filename):
                path = ROOT / ".github" / "workflows" / filename
                doc = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
                group = doc.get("concurrency")
                if filename == "materializer-release-updates.yml":
                    self.assertEqual(group["cancel-in-progress"], "false")
                else:
                    self.assertFalse(group)


if __name__ == "__main__":
    unittest.main()
