"""RED-first canonical registration contract for Agora issue #197."""
from __future__ import annotations

from pathlib import Path
import unittest

from scripts.agora_install_materializer import load_registry, select_plugin


ROOT = Path(__file__).resolve().parents[1]
COPTIC_TF_COMMIT = "ca0ee11bec734858628b2a237c11acb463a63863"


class CopticScriptoriumMaterializerRegistryTests(unittest.TestCase):
    def test_copticscriptorium_tf_is_registered_at_reviewed_immutable_commit(self):
        plugin = select_plugin(load_registry(), "copticscriptorium-tf")

        self.assertEqual(plugin["repository"], "alexsosn/CopticScriptorium-TF")
        self.assertEqual(plugin["ref"], COPTIC_TF_COMMIT)
        self.assertEqual(plugin["version"], "0.1.0")
        self.assertEqual(plugin["manifest"], "agora.materializer.json")
        self.assertEqual(plugin["materializers"], ["copticscriptorium-text-fabric"])
        self.assertEqual(plugin["package"]["type"], "python-project")
        self.assertEqual(plugin["package"]["path"], ".")
        self.assertEqual(
            plugin["package"]["install_trust"],
            "explicit-code-execution",
        )
        self.assertEqual(plugin["verification"]["status"], "community")

    def test_live_workflow_exercises_passive_install_and_registered_sandbox_run(self):
        workflow = (
            ROOT / ".github/workflows/materializer-install.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("copticscriptorium-tf:", workflow)
        self.assertIn(
            "python scripts/agora_install_materializer.py fetch copticscriptorium-tf",
            workflow,
        )
        self.assertIn(
            "python scripts/agora_install_materializer.py install copticscriptorium-tf",
            workflow,
        )
        self.assertIn("python scripts/agora_materialize_registered.py", workflow)
        self.assertIn("--plugin copticscriptorium-tf", workflow)
        self.assertIn("--materializer copticscriptorium-text-fabric", workflow)
        self.assertIn("--sandbox required", workflow)
        self.assertIn("github.event.pull_request.head.sha || github.sha", workflow)
        self.assertIn('test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"', workflow)

        self.assertIn("Coptic materializer → Context-Fabric handoff", workflow)
        self.assertIn("install_local_corpus", workflow)
        self.assertIn("load_corpus", workflow)
        self.assertIn("coptic-output/tf", workflow)

        self.assertIn("Coptic automatic Git acquisition", workflow)
        self.assertIn("coptic-acquired-output", workflow)
        acquired_block = workflow.split(
            "- name: Coptic automatic Git acquisition", 1
        )[1].split("- name:", 1)[0]
        self.assertNotIn("--source", acquired_block)
        self.assertIn("--sandbox required", acquired_block)


if __name__ == "__main__":
    unittest.main()
