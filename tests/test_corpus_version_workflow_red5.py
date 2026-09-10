from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "corpus-version-updates.yml"


class CorpusVersionWorkflowRed5Tests(unittest.TestCase):
    def _workflow(self) -> tuple[str, dict]:
        if not WORKFLOW.is_file():
            raise AssertionError("RED5: corpus-version-updates workflow is missing")
        text = WORKFLOW.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        self.assertIsInstance(data, dict)
        return text, data

    def test_workflow_is_scheduled_and_manually_dispatchable(self):
        _text, workflow = self._workflow()
        triggers = workflow.get("on", workflow.get(True, {}))
        self.assertIn("schedule", triggers)
        self.assertIn("workflow_dispatch", triggers)

    def test_manual_or_scheduled_run_starts_from_canonical_main(self):
        _text, workflow = self._workflow()
        steps = next(iter(workflow["jobs"].values()))["steps"]
        checkout = next(step for step in steps if str(step.get("uses", "")).startswith("actions/checkout@"))
        self.assertEqual(checkout.get("with", {}).get("ref"), "main")

    def test_permissions_allow_only_review_pr_writes_and_workflow_never_auto_merges(self):
        text, workflow = self._workflow()
        permissions = workflow.get("permissions", {})
        self.assertEqual(permissions.get("contents"), "write")
        self.assertEqual(permissions.get("pull-requests"), "write")
        self.assertEqual(set(permissions), {"contents", "pull-requests"})
        lowered = text.lower()
        self.assertNotIn("gh pr merge", lowered)
        self.assertNotIn("enable-auto-merge", lowered)

    def test_discovery_does_not_receive_repo_scoped_token(self):
        text, _workflow = self._workflow()
        lines = text.splitlines()
        discovery_lines = [line for line in lines if "check_corpus_versions.py" in line]
        self.assertTrue(discovery_lines, text)
        for line in discovery_lines:
            self.assertNotIn("GITHUB_TOKEN", line)
            self.assertNotIn("--token", line)

    def test_workflow_uses_one_fixed_bot_branch_and_validates_before_push(self):
        text, _workflow = self._workflow()
        self.assertIn("automation/corpus-version-updates", text)
        validate = text.find("scripts/validate_registry.py")
        generate = text.find("scripts/generate_context_fabric_catalog.py")
        push = text.find("git push")
        self.assertGreaterEqual(validate, 0, text)
        self.assertGreaterEqual(generate, 0, text)
        self.assertGreaterEqual(push, 0, text)
        self.assertLess(validate, push)
        self.assertLess(generate, push)

    def test_workflow_refreshes_bot_branch_from_main_and_creates_or_updates_one_pr(self):
        text, _workflow = self._workflow()
        self.assertRegex(text, r"git (checkout|switch).*(automation/corpus-version-updates)")
        self.assertRegex(text, r"gh pr (create|edit)")
        self.assertIn("--base main", text)
        self.assertIn("--head automation/corpus-version-updates", text)


if __name__ == "__main__":
    unittest.main()
