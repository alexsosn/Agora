from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
INSTALL = ROOT / "wiki" / "guides" / "installation.md"
LIVE_SMOKE = ROOT / ".github" / "workflows" / "external-mcp-smoke.yml"


class ReleaseFrontDoorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.readme = README.read_text(encoding="utf-8")
        self.install = INSTALL.read_text(encoding="utf-8")
        self.live_smoke = LIVE_SMOKE.read_text(encoding="utf-8")

    def test_first_user_docs_do_not_advertise_provider_wide_perseus_cts_navigation(self):
        self.assertNotIn("CTS navigation", self.readme)
        self.assertNotIn("CTS navigation", self.install)

    def test_readme_surfaces_chatgpt_desktop_only_import_limit(self):
        self.assertIn("Desktop only", self.readme)
        self.assertIn("ChatGPT", self.readme)

    def test_installation_documents_host_owned_single_plugin_removal(self):
        self.assertIn("claude plugin uninstall", self.install)
        self.assertIn("codex plugin remove", self.install)
        self.assertIn("Disable plugin", self.install)
        self.assertIn("not the same as uninstall", self.install)

    def test_installation_exposes_context_fabric_first_load_and_cache_recovery(self):
        for token in (
            "describe_available_corpus",
            "prepare_corpus",
            "load_corpus",
            "~/.cache/agora/context-fabric",
            "AGORA_CORPUS_CACHE",
            "corpus_cache_status",
            "prune_corpus_cache",
            "remove_cached_corpus",
            "context-fabric-cache.md",
        ):
            self.assertIn(token, self.install)

    def test_installation_has_compact_first_run_troubleshooting(self):
        self.assertIn("## Troubleshooting", self.install)
        for token in (
            "uv",
            "Python 3.13",
            "network",
            "Desktop only",
            "corpus_cache_status",
        ):
            self.assertIn(token, self.install)

    def test_public_install_docs_rerun_existing_eight_cell_live_smoke(self):
        self.assertIn('"README.md"', self.live_smoke)
        self.assertIn('"wiki/guides/installation.md"', self.live_smoke)
        self.assertIn("plugin: [context-fabric, perseus, sefaria, sedra]", self.live_smoke)
        self.assertIn("--client codex", self.live_smoke)
        self.assertIn("--client claude", self.live_smoke)


if __name__ == "__main__":
    unittest.main()
