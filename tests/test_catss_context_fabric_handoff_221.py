"""Issue #221 stage 2: a real CATSS producer -> Context-Fabric offline consumer contract.

The initial RED commit has no new workflow consumer steps. The positive
integration proof is required from the exact-head Actions runner after GREEN.
"""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/materializer-install.yml"


def catss_job() -> str:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    if "\n  catss-tf:\n" not in workflow:
        raise AssertionError("registered CATSS job is missing")
    return workflow.split("\n  catss-tf:\n", 1)[1]


class CatssContextFabricConsumerContractTests(unittest.TestCase):
    def test_real_consumer_runs_after_verified_native_producer(self):
        job = catss_job()
        self.assertIn("CATSS_AGORA_STANDALONE_OK", job)
        self.assertIn("CATSS_CF_CONSUMER_OK", job)
        self.assertLess(job.index("CATSS_AGORA_STANDALONE_OK"), job.index("CATSS_CF_CONSUMER_OK"))
        self.assertIn("python -m pip install -e ./plugins/context-fabric", job)
        self.assertIn("agora_context_fabric.server", job)
        self.assertIn("mcp.client.stdio", job)
        self.assertIn("CATSS_TF:", job)
        self.assertIn("catss-output", job)

    def test_local_import_is_offline_queryable_and_released(self):
        job = catss_job()
        self.assertIn('"install_local_corpus"', job)
        self.assertIn('"list_available_corpora"', job)
        self.assertIn('"prepare_corpus"', job)
        self.assertIn('"load_corpus"', job)
        self.assertIn('"describe_corpus"', job)
        self.assertIn('"search"', job)
        self.assertIn('template="alignment"', job)
        self.assertIn('matches.get("total_count") != 2', job)
        self.assertIn('"unload_corpus"', job)
        self.assertIn('"remove_cached_corpus"', job)
        self.assertIn('source_mode="offline"', job)
        self.assertIn('"catss_alignment_id"', job)
        self.assertIn('"catss_lxx_plus"', job)
        self.assertIn("source=str(SOURCE)", job)

    def test_registered_producer_security_contract_retained(self):
        job = catss_job()
        self.assertIn("github.event.pull_request.head.sha || github.sha", job)
        self.assertIn("python scripts/agora_install_materializer.py fetch catss-tf", job)
        self.assertIn("python scripts/agora_install_materializer.py install catss-tf", job)
        self.assertIn("--approve-code-execution", job)
        self.assertIn("--materializer catss-canonical", job)
        self.assertIn("--sandbox required", job)
        self.assertIn("provenance['sandbox'] == 'bubblewrap'", job)
        self.assertNotIn("--allow", job)


if __name__ == "__main__":
    unittest.main()
