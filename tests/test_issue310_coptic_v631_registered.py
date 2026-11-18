"""#310 RED-first: registered Coptic v6.3.1 source, no stale plugin release.

The full registered production workflow MUST still fetch/execute its immutable
producer commit in a network-denied sandbox, build the entire original TT
corpus and query it through Context-Fabric. Static tests alone are not E2E.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

from scripts.agora_install_materializer import load_registry, select_plugin

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_COPTIC_V631 = "6fb51458e7156dd5387c2b2dca207aac1692e4d0"
PREVIOUS_SOURCE = "3ac067f1709a0012daf39ea8da2fac79980176a5"
PREVIOUS_REGISTERED_PRODUCER = "3cde20ec41efb1cacf1710643f01f924f11cbf0b"


class CopticV631RegisteredSourceMigrationTests(unittest.TestCase):
    def test_registered_source_is_official_release_and_producer_is_new_immutable_commit(self):
        plugin = select_plugin(load_registry(), "copticscriptorium-tf")
        self.assertEqual(plugin["repository"], "alexsosn/CopticScriptorium-TF")
        self.assertRegex(plugin["ref"], r"^[0-9a-f]{40}$")
        self.assertNotEqual(plugin["ref"], PREVIOUS_REGISTERED_PRODUCER)
        existing_contract = (ROOT / "tests/test_coptic_single_source_pin_235.py").read_text(encoding="utf-8")
        match = re.search(r'^IMMUTABLE_COPTIC_TT_SOURCE = "([a-f0-9]{40})"$',
                          existing_contract, re.MULTILINE)
        self.assertIsNotNone(match, "missing existing independently pinned source check")
        self.assertEqual(match.group(1), OFFICIAL_COPTIC_V631)
        self.assertNotEqual(match.group(1), PREVIOUS_SOURCE)
        self.assertEqual(plugin["package"]["install_trust"], "explicit-code-execution")

    def test_real_registered_full_acceptance_is_source_locked_and_lifecycle_complete(self):
        verifier = (ROOT / "tests/live_issue214_full_coptic.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/coptic-registered-full-source.yml").read_text(encoding="utf-8")
        self.assertIn('UPSTREAM_COMMIT = "' + OFFICIAL_COPTIC_V631 + '"', verifier)
        self.assertIn('source["requested_ref"] == UPSTREAM_COMMIT', verifier)
        self.assertIn('source["resolved_commit"] == UPSTREAM_COMMIT', verifier)
        self.assertIn('receipt["plugin"]["commit"] == plugin["ref"]', verifier)
        self.assertIn('summary["source_records"] == EXPECTED_RECORDS', verifier)
        self.assertIn('summary["slots"] == EXPECTED_SLOTS', verifier)
        for op in (
            "install_local_corpus", "prepare_corpus", "load_corpus", "search",
            "unload_corpus", "remove_cached_corpus",
        ):
            self.assertIn(op, verifier)
        self.assertIn("--sandbox required", workflow)
        self.assertNotIn("--source ", workflow.split(
            "python scripts/agora_materialize_registered.py", 1,
        )[1].split("\n      - name:", 1)[0])
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("Full registered automatic pinned Git acquisition", workflow)

    def test_old_source_is_not_passed_off_as_a_new_registered_release(self):
        for path in (
            "tests/test_copticscriptorium_materializer_registry.py",
            "tests/test_issue214_coptic_full_registered.py",
            "tests/live_issue214_full_coptic.py",
            ".github/workflows/materializer-install.yml",
        ):
            with self.subTest(path=path):
                content = (ROOT / path).read_text(encoding="utf-8")
                self.assertNotIn(PREVIOUS_SOURCE, content)
                self.assertIn(OFFICIAL_COPTIC_V631, content)


if __name__ == "__main__":
    unittest.main()
