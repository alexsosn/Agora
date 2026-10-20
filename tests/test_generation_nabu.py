"""Deterministic manifest checks for the nabu plugin launch metadata.

These back the verification-checks entries manifest/nabu-claude and
manifest/nabu-codex. They assert that the generated client configurations
launch the user's own Nabu checkout (resolved via NABU_HOME) with Bundler
pinned to that checkout's Gemfile, and nothing else.
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_ARGS = ["exec", "${NABU_HOME}/bin/nabu", "mcp"]
EXPECTED_ENV = {"BUNDLE_GEMFILE": "${NABU_HOME}/Gemfile"}


class NabuManifestTests(unittest.TestCase):
    def test_nabu_claude_mcp_launches_user_checkout(self):
        with (ROOT / "plugins/nabu/.claude-plugin/mcp.json").open(
            "r", encoding="utf-8"
        ) as fh:
            server = json.load(fh)["nabu"]
        self.assertEqual(server["command"], "bundle")
        self.assertEqual(server["args"], EXPECTED_ARGS)
        self.assertEqual(server["env"], EXPECTED_ENV)

    def test_nabu_codex_mcp_launches_user_checkout(self):
        with (ROOT / "plugins/nabu/.codex-plugin/mcp.json").open(
            "r", encoding="utf-8"
        ) as fh:
            server = json.load(fh)["mcpServers"]["nabu"]
        self.assertEqual(server["type"], "stdio")
        self.assertEqual(server["command"], "bundle")
        self.assertEqual(server["args"], EXPECTED_ARGS)
        self.assertEqual(server["env"], EXPECTED_ENV)


if __name__ == "__main__":
    unittest.main()
