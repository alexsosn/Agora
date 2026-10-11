"""#237 RED2: real registered user-local Burns → managed CUC → Context-Fabric E2E.

Only the CI job downloads the source, from the original thesis repository.
The test contract itself neither downloads nor packages licensed Workbooks.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ctc-burns-registered-e2e.yml"
VERIFIER = ROOT / "tests/live_ctc_burns_registered_237.py"


class RegisteredCucBurnsFullAcceptanceContracts(unittest.TestCase):
    def test_real_workbooks_and_registered_producer_with_explicit_approval(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for marker in (
            "f58b162197ad8f113b7cd6fc0088ae5dd39a096d",
            "0408967b1808c1f22c69e299d302b1e7b5e26354",
            "scripts/parse_workbooks_to_csv.py",
            "agora_install_materializer.py fetch cuc-burns",
            "agora_install_materializer.py install cuc-burns",
            "--approve-code-execution",
            "bubblewrap",
            "AGORA_CORPUS_MIN_FREE_GB",
            "tests.live_ctc_burns_registered_237",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, workflow)
        self.assertNotIn("upload-artifact", workflow)
        self.assertNotIn("--source-archive", workflow)

    def test_real_acceptance_is_reachable_from_existing_required_sandbox_workflow(self):
        # A brand-new GitHub Actions workflow may not register its first PR
        # event until the file exists on the default branch. Reuse an existing
        # required workflow and avoid caller/callee concurrency self-cancel.
        workflow = WORKFLOW.read_text(encoding="utf-8")
        caller = (ROOT / ".github/workflows/materialization-sandbox.yml").read_text()
        self.assertIn("workflow_call:", workflow)
        self.assertIn("./.github/workflows/ctc-burns-registered-e2e.yml", caller)
        self.assertIn("'tests/live_ctc_burns_registered_237.py'", caller)
        self.assertIn("'.github/workflows/ctc-burns-registered-e2e.yml'", caller)
        self.assertIn("ctc-burns-registered-", workflow)
        self.assertNotIn("group: ${{ github.workflow }}-", workflow)

    def test_real_data_native_tf_and_parent_identity_preserved(self):
        script = VERIFIER.read_text(encoding="utf-8")
        for marker in (
            "materialize_requested_feature_module",
            '"cuc-burns"',
            '"cuc-burns-csv"',
            "0408967b1808c1f22c69e299d302b1e7b5e26354",
            "Fabric(",
            "burns_headword_1",
            "maxSlot",
            "maxNode",
            "prepare_with_modules",
            "otype.tf",
            "oslots.tf",
            "otext.tf",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, script)


if __name__ == "__main__":
    unittest.main()
