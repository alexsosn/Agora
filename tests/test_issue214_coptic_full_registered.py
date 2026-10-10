"""RED-first contract for composed registered real Coptic #214 acceptance.

This static contract is intentionally insufficient alone: the corresponding
GitHub Actions job must run and check the full real source and MCP lifecycle.
"""
from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/coptic-registered-full-source.yml"
ACCEPTANCE = ROOT / "tests/live_issue214_full_coptic.py"
COPTIC_COMMIT = "60fec735dd6ef9aefe2cfb9e6459e9f7f15924e7"
UPSTREAM_COMMIT = "3ac067f1709a0012daf39ea8da2fac79980176a5"


class RegisteredCopticFullSourceAcceptanceContract(unittest.TestCase):
    def test_full_source_workflow_uses_registered_automatic_acquisition(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python scripts/agora_materialize_registered.py", workflow)
        self.assertIn("--plugin copticscriptorium-tf", workflow)
        self.assertIn("--materializer copticscriptorium-text-fabric", workflow)
        self.assertIn("--sandbox required", workflow)
        command = workflow.split(
            "python scripts/agora_materialize_registered.py", 1
        )[1].split("\n      - name:", 1)[0]
        self.assertNotIn("--source ", command,
                         "registered invocation must acquire remote Git automatically")
        self.assertIn("--approve-code-execution", workflow)
        self.assertIn("tests/live_issue214_full_coptic.py", workflow)
        self.assertIn("timeout-minutes: 75", workflow)
        self.assertIn("/usr/bin/time -v", workflow)
        self.assertIn("if: always()", workflow)
        self.assertIn("github.event.pull_request.head.sha || github.sha", workflow)

    def test_verifier_asserts_real_provenance_complete_native_tf_and_cfabric(self):
        source = ACCEPTANCE.read_text(encoding="utf-8")
        for marker in (
            COPTIC_COMMIT,
            UPSTREAM_COMMIT,
            '"git"',
            '"sparse_patterns"',
            "2_628",
            "2_394_354",
            '"otype.tf"',
            '"oslots.tf"',
            '"otext.tf"',
            "Fabric(",
            "install_local_corpus",
            "prepare_corpus",
            "load_corpus",
            "search",
            "unload_corpus",
            "remove_cached_corpus",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()
