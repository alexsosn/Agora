"""Deterministic checks for the nabu plugin's launch metadata.

These back the verification-checks entries manifest/nabu-claude and
manifest/nabu-codex. Unlike their first version, they assert against the
GENERATOR's rendered outputs and only then against the committed files, so
they cannot drift from what `scripts/generate_marketplaces.py` actually
derives from the canonical registry: the launch starts the user's own Nabu
checkout (resolved via NABU_HOME) with Bundler pinned to that checkout's
Gemfile, and nothing else.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.generate_marketplaces import ROOT, render_outputs

EXPECTED_COMMAND = "bundle"
EXPECTED_ARGS = ["exec", "${NABU_HOME}/bin/nabu", "mcp"]
EXPECTED_ENV = {"BUNDLE_GEMFILE": "${NABU_HOME}/Gemfile"}


def _rendered(relative: str) -> dict:
    outputs = {path.relative_to(ROOT): content for path, content in render_outputs().items()}
    return json.loads(outputs[Path(relative)])


def _committed(relative: str) -> dict:
    with (ROOT / relative).open("r", encoding="utf-8") as fh:
        return json.load(fh)


class NabuManifestTests(unittest.TestCase):
    def _assert_launch(self, server: dict) -> None:
        self.assertEqual(server["command"], EXPECTED_COMMAND)
        self.assertEqual(server["args"], EXPECTED_ARGS)
        self.assertEqual(server["env"], EXPECTED_ENV)

    def test_nabu_claude_mcp_launches_user_checkout(self):
        relative = "plugins/nabu/.claude-plugin/mcp.json"
        for source in (_rendered(relative), _committed(relative)):
            self._assert_launch(source["nabu"])

    def test_nabu_codex_mcp_launches_user_checkout(self):
        relative = "plugins/nabu/.codex-plugin/mcp.json"
        for source in (_rendered(relative), _committed(relative)):
            server = source["mcpServers"]["nabu"]
            self.assertEqual(server["type"], "stdio")
            self._assert_launch(server)

    def test_nabu_is_discoverable_from_both_generated_marketplaces(self):
        for relative in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
            for source in (_rendered(relative), _committed(relative)):
                names = [item["name"] for item in source["plugins"]]
                self.assertIn("nabu", names)

    def test_nabu_manifests_match_the_generator_exactly(self):
        for relative in (
            "plugins/nabu/.claude-plugin/plugin.json",
            "plugins/nabu/.codex-plugin/plugin.json",
            "plugins/nabu/.claude-plugin/mcp.json",
            "plugins/nabu/.codex-plugin/mcp.json",
        ):
            with self.subTest(path=relative):
                self.assertEqual(_committed(relative), _rendered(relative))


if __name__ == "__main__":
    unittest.main()
