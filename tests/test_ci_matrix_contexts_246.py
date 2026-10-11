"""#246 regression: docs-only PRs must retain expanded OS check contexts.

Research: real #265 Foundation run 38172482376 generated only two generic
skipped matrix jobs; full #264 run 38172436189 generated all six OS-specific
jobs. Branch-protection required checks are not readable (403), so retaining
their original identities is an explicit safety requirement.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github/workflows/foundation.yml"
)


class MatrixCheckIdentity246(unittest.TestCase):
    def test_all_six_os_matrix_jobs_exist_for_docs_scope(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        for job in ("context-fabric-cache-lifecycle", "materializer-install-locks"):
            with self.subTest(job=job):
                match = re.search(
                    rf"(?ms)^  {re.escape(job)}:\n(.*?)(?=^  [a-z][a-z-]*:\n|\\Z)",
                    source,
                )
                self.assertIsNotNone(match, "OS matrix job is missing")
                header, separator, steps = match.group(1).partition("    steps:\n")
                self.assertTrue(separator, "OS matrix must have steps")
                self.assertIn(
                    "os: [ubuntu-latest, macos-latest, windows-latest]",
                    header,
                )
                self.assertNotRegex(
                    header,
                    r"(?m)^    if:",
                    "A job-level docs skip collapses six OS checks into only "
                    "two generic skipped check contexts (observed in PR #265)",
                )
                blocks = steps.split("      - name: ")[1:]
                self.assertTrue(blocks)
                docs_stub = [
                    block for block in blocks
                    if block.startswith("Document docs-only validation skip\n")
                ]
                self.assertEqual(1, len(docs_stub))
                self.assertIn(
                    "        if: needs.scope.outputs.validation == 'docs'",
                    docs_stub[0],
                )
                runtime_steps = [
                    block for block in blocks if block not in docs_stub
                ]
                self.assertTrue(runtime_steps)
                for block in runtime_steps:
                    step_name = block.splitlines()[0]
                    with self.subTest(job=job, step=step_name):
                        self.assertIn(
                            "        if: needs.scope.outputs.validation == 'full'",
                            block,
                            "OS runtime setup and tests must not run for docs",
                        )


if __name__ == "__main__":
    unittest.main()
