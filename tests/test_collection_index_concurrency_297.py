"""#297: concurrent index PR runs may cancel only superseded runs of same PR."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / ".github/workflows/context-fabric-collection-index-generation.yml"
FOUNDATION = ROOT / ".github/workflows/foundation.yml"


def concurrency_block(source: str) -> str:
    match = re.search(
        r"(?ms)^concurrency:\n(.*?)(?=^[a-z][a-z-]*:|\Z)", source
    )
    if match is None:
        raise AssertionError("missing top-level workflow concurrency block")
    return match.group(1)


class CollectionIndexConcurrency297(unittest.TestCase):
    def test_cancellation_uses_proven_foundation_pr_group_contract(self):
        index = concurrency_block(INDEX.read_text(encoding="utf-8"))
        foundation = concurrency_block(FOUNDATION.read_text(encoding="utf-8"))
        # Reuse the already reviewed expression rather than inventing a new one.
        self.assertEqual(foundation, index)
        self.assertIn("github.event_name == 'pull_request'", index)
        self.assertIn("format('pr-{0}', github.event.pull_request.number)", index)
        self.assertIn("format('run-{0}-{1}', github.run_id, github.run_attempt)", index)
        self.assertIn("cancel-in-progress: ${{ github.event_name == 'pull_request' }}", index)
        self.assertNotIn("github.ref", index)
        self.assertNotIn("github.head_ref", index)

    def test_no_changes_to_existing_required_four_matrix_jobs(self):
        source = INDEX.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", source)
        self.assertIn("pull_request:", source)
        self.assertIn("needs: scope", source)
        self.assertIn("timeout-minutes: 25", source)
        self.assertIn("if: needs.scope.outputs.regenerate == 'true'", source)
        self.assertIn("if: needs.scope.outputs.regenerate == 'false'", source)
        for collection in ("bible", "patristics", "greek_literature", "translatin-manif"):
            self.assertIn(f"- {collection}", source)
        self.assertNotRegex(source, r"(?m)^  generate:.*\n(?:.*\n)*?    if:")

    def test_concurrency_is_workflow_level_not_per_job_or_global_branch(self):
        source = INDEX.read_text(encoding="utf-8")
        block = concurrency_block(source)
        self.assertEqual(1, source.count("\nconcurrency:\n"))
        self.assertIn("group: ", block)
        self.assertIn("cancel-in-progress: ", block)
        jobs = source[source.index("\njobs:\n"):]
        self.assertNotIn("concurrency:", jobs)
        self.assertNotIn("github.workflow_ref", block)


if __name__ == "__main__":
    unittest.main()
