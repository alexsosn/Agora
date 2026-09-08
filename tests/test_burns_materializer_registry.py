from __future__ import annotations

import unittest

from scripts.agora_install_materializer import load_registry, select_plugin


UGARIT_CONTEXT_PARSING_COMMIT = "e1218b88d9d849c58ee25541339f32b0d8f5a7d3"


class BurnsMaterializerRegistryTests(unittest.TestCase):
    def test_burns_converter_is_registered_at_reviewed_immutable_commit(self):
        plugin = select_plugin(load_registry(), "ugarit-context-parsing")

        self.assertEqual(plugin["repository"], "alexsosn/ugarit-context-parsing")
        self.assertEqual(plugin["ref"], UGARIT_CONTEXT_PARSING_COMMIT)
        self.assertEqual(plugin["version"], "0.2.0")
        self.assertEqual(plugin["manifest"], "agora.materializer.json")
        self.assertEqual(plugin["package"]["type"], "python-project")
        self.assertEqual(plugin["package"]["install_trust"], "explicit-code-execution")
        self.assertEqual(plugin["release_tracking"], {"mode": "disabled"})
        self.assertEqual(
            plugin["materializers"],
            [
                "burns-workbooks-csv-text-fabric",
                "burns-workbooks-pdf-text-fabric",
            ],
        )
        self.assertEqual(plugin["licenses"]["software"], "NOASSERTION")
        self.assertIn("CC BY-NC-ND 2.5", plugin["licenses"]["data"])


if __name__ == "__main__":
    unittest.main()
