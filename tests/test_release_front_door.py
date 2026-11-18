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

    def test_first_user_docs_do_not_present_1_0_front_door_as_v0_1_plugins(self):
        self.assertNotIn("v0.1 plugins", self.readme)
        self.assertNotIn("v0.1 plugins", self.install)

    def test_readme_surfaces_chatgpt_desktop_only_import_limit(self):
        self.assertIn("Desktop only", self.readme)
        self.assertIn("ChatGPT", self.readme)

    def test_front_door_defers_mutable_resource_counts_to_generated_catalog(self):
        for doc in (self.readme, self.install):
            self.assertNotRegex(doc, r"\b\d+\s+registered (?:upstream )?resources\b")
        self.assertIn("[resource catalog](wiki/guides/resources.md)", self.readme)
        self.assertIn("[resource catalog](resources.md)", self.install)

    def test_cal_first_contact_prerequisites_and_prompt_are_visible(self):
        self.assertIn("CAL uses `uvx`", self.install)
        self.assertIn("live Comprehensive Aramaic Lexicon (CAL)", self.install)
        self.assertIn("cal_lexicon_lookup", self.readme)
        self.assertIn("br N", self.readme)
        self.assertIn("first-success/cal.md", self.readme)

    def test_installation_documents_host_owned_removal_without_marketplace_deletion(self):
        self.assertIn("claude plugin uninstall", self.install)
        self.assertIn("codex plugin remove", self.install)
        self.assertIn("installation policy", self.install)
        self.assertIn("deleting the imported marketplace", self.install)
        self.assertIn("every plugin imported from that marketplace", self.install)
        self.assertNotIn("Disable plugin is not the same as uninstall", self.install)

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
        self.assertIn("[troubleshooting by symptom](troubleshooting.md)", self.install)
        for token in ("uv", "Python 3.13", "Desktop only", "corpus_cache_status"):
            self.assertIn(token, self.install)
        recovery = (ROOT / "wiki" / "guides" / "troubleshooting.md").read_text(encoding="utf-8")
        for symptom in (
            "uv, uvx or Python is not found",
            "Remote lookup fails",
            "Corpus acquisition or compilation appears stuck",
            "Plugin works in one client but not another",
        ):
            self.assertIn("## " + symptom, recovery)
        self.assertIn("network", recovery.lower())

    def test_docs_only_push_does_not_trigger_unrelated_live_mcp_matrix(self):
        # This workflow's live matrix runs packaged plugin transports, not the
        # README/installation commands or actual Codex/Claude applications.
        # A text-only first-user guide correction stays on Foundation's docs gate.
        paths = self.live_smoke.split("\n  push:\n    paths:\n", 1)[1].split(
            "\npermissions:", 1
        )[0]
        self.assertNotIn('"README.md"', paths)
        self.assertNotIn('"wiki/guides/installation.md"', paths)

        # Preserve the actual runtime, registry/verification, and compatibility
        # triggers: a mixed or substantive change must still invoke live MCP.
        for required in (
            '".gitattributes"',
            '"registry/plugins.yaml"',
            '"registry/providers.yaml"',
            '"registry/verification-checks.yaml"',
            '"registry/schema/plugins.schema.json"',
            '"wiki/guides/compatibility.md"',
            '"plugins/context-fabric/src/**"',
            '"plugins/context-fabric/uv.lock"',
            '"plugins/perseus/runtime-constraints.txt"',
            '"plugins/sefaria/runtime-constraints.txt"',
            '"plugins/sedra/uv.lock"',
            '"verification/mcp-smoke/uv.lock"',
            '"scripts/generate_marketplaces.py"',
            '"scripts/smoke_mcp_plugin.py"',
            '"tests/test_verification_evidence.py"',
            '".github/workflows/external-mcp-smoke.yml"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, paths)

        self.assertIn("workflow_dispatch:", self.live_smoke)
        self.assertIn("schedule:", self.live_smoke)
        self.assertIn("plugin: [context-fabric, perseus, sefaria, sedra]", self.live_smoke)
        self.assertIn("--client codex", self.live_smoke)
        self.assertIn("--client claude", self.live_smoke)
        self.assertIn("local-runtime-platform:", self.live_smoke)


if __name__ == "__main__":
    unittest.main()
