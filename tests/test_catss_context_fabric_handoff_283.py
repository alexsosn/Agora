"""RED-first #283 contract: registered CATSS output must be a CFM local corpus."""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/materializer-install.yml"


class CatssContextFabricHandoffTests(unittest.TestCase):
    @staticmethod
    def catss_job() -> dict:
        document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        return document["jobs"]["catss-tf"]

    def test_consumer_step_is_inside_exact_registered_catss_sandbox_job(self):
        steps = self.catss_job()["steps"]
        names = [step.get("name", "") for step in steps]
        self.assertIn("CATSS materializer → Context-Fabric handoff", names)
        producer_idx = next(
            i for i, step in enumerate(steps)
            if step.get("name", "").startswith("Run installed CATSS producer")
        )
        consumer_idx = names.index("CATSS materializer → Context-Fabric handoff")
        self.assertGreater(consumer_idx, producer_idx)

    def test_handoff_uses_offline_local_import_and_alignment_not_word_slots(self):
        text = "\n".join(str(step.get("run", "")) for step in self.catss_job()["steps"])
        for required in (
            "agora_context_fabric.server",
            "install_local_corpus",
            "list_available_corpora",
            "prepare_corpus",
            "load_corpus",
            "describe_corpus",
            "unload_corpus",
            "remove_cached_corpus",
            "source_mode=\"offline\"",
            'template="alignment"',
            'features=["catss_alignment_id", "catss_lxx_plus"]',
            "CATSS_CONTEXT_FABRIC_HANDOFF_OK",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        self.assertNotIn('template="word"', text[text.index("CATSS materializer → Context-Fabric handoff") :])

    def test_consumer_flow_is_tied_to_immutable_synthetic_producer_output(self):
        text = "\n".join(str(step.get("run", "")) for step in self.catss_job()["steps"])
        self.assertIn("catss-output", text)
        self.assertIn("AGORA_CORPUS_MIN_FREE_GB", text)
        self.assertIn("prepared[\"source_revision\"]", text)
        self.assertIn('resource_id=resource_id', text)
        self.assertIn('if result.isError:', text)
        self.assertIn('installed["source_revision"]', text)


if __name__ == "__main__":
    unittest.main()
