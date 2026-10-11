"""#171: first-contact support decisions must match canonical client evidence."""
from __future__ import annotations

from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "wiki/guides/compatibility.md"
REGISTRY = ROOT / "registry/plugins.yaml"


class CompatibilityDecisionFirstContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = PAGE.read_text(encoding="utf-8")
        cls.plugins = {
            item["id"]: item for item in
            yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["plugins"]
        }

    def test_user_decision_precedes_internal_evidence_taxonomy(self):
        decision = self.page.index("## Can I use this plugin?")
        taxonomy = self.page.index("## What the evidence means")
        paths = self.page.index("## Generated client paths")
        self.assertLess(decision, taxonomy)
        self.assertLess(decision, paths)
        first = self.page[decision:taxonomy]
        for phrase in ("Claude Code", "Codex", "Context-Fabric", "Perseus",
                       "Sefaria", "SEDRA", "ChatGPT web", "Desktop only"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, first)

    def test_decision_table_matches_canonical_verified_transport_per_client(self):
        decisions = self.page.split("## Can I use this plugin?", 1)[1].split(
            "## What the evidence means", 1
        )[0]
        expected = {
            "context-fabric": ("Context-Fabric", "stdio", "stdio"),
            "perseus": ("Perseus", "stdio", "stdio"),
            "sefaria": ("Sefaria", "direct SSE", "stdio via SSE proxy"),
            "sedra": ("SEDRA", "stdio", "stdio"),
        }
        for key, (name, claude, codex) in expected.items():
            with self.subTest(plugin=key):
                canonical = self.plugins[key]["verification"]["clients"]
                self.assertEqual(canonical["claude"]["status"], "verified")
                self.assertEqual(canonical["codex"]["status"], "verified")
                self.assertEqual(canonical["claude"]["transport"], {
                    "direct SSE": "sse", "stdio": "stdio"
                }[claude])
                self.assertEqual(canonical["codex"]["transport"], {
                    "stdio via SSE proxy": "stdio-via-sse-proxy", "stdio": "stdio"
                }[codex])
                self.assertIn(
                    f"| {name} | Verified path ({claude}) | Verified path ({codex}) |",
                    decisions,
                )
        self.assertIn("does not launch the Claude Code or Codex application executable", decisions)

    def test_platform_scope_does_not_overclaim_native_clients_or_chatgpt(self):
        decisions = self.page.split("## Can I use this plugin?", 1)[1].split(
            "## What the evidence means", 1
        )[0]
        for snippet in ("Linux x86_64", "Intel macOS x86_64",
                        "Windows x86_64", "Apple Silicon",
                        "startup-only", "Context-Fabric and SEDRA",
                        "cannot run in ChatGPT web", "plan", "workspace"):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, decisions)
        checks = yaml.safe_load(
            (ROOT / "registry/verification-checks.yaml").read_text(encoding="utf-8")
        )
        # Startup evidence must exist on exactly these supported local-runtime cells.
        ids = {c["id"] for c in checks["checks"]}
        for plugin in ("context-fabric", "sedra"):
            for os in ("linux", "macos", "windows"):
                self.assertIn(f"platform-startup/{plugin}-{os}-x86-64", ids)

    def test_known_issues_link_to_plugin_guidance_and_symptom_recovery(self):
        advisories = self.page.split("## Current upstream limitations", 1)[1].split(
            "## Reading the matrix safely", 1
        )[0]
        issue_links = {
            "sefaria/search-version-duplicates": "[Sefaria](plugins/sefaria.md)",
            "context-fabric/search-count-cache-cap": "[Context-Fabric](plugins/context-fabric.md)",
            "context-fabric/cuc-text-format-discovery": "[Context-Fabric](plugins/context-fabric.md)",
            "perseus/legacy-cts-malformed-navigation": "[Perseus](plugins/perseus.md)",
        }
        for issue, link in issue_links.items():
            with self.subTest(issue=issue):
                row = next(line for line in advisories.splitlines() if issue in line)
                self.assertIn(link, row)
        self.assertIn("[troubleshooting](installation.md#troubleshooting)", advisories)
        self.assertIn("[cache guidance](context-fabric-cache.md)", advisories)

    def test_evidence_and_known_upstream_caveats_are_preserved(self):
        for marker in ("manifest/context-fabric-claude", "mcp-live/context-fabric-codex",
                       "mcp-live/sefaria-claude", "mcp-live/sefaria-codex",
                       "platform-startup/sedra-macos-x86-64",
                       "sefaria/search-version-duplicates",
                       "context-fabric/search-count-cache-cap",
                       "context-fabric/cuc-text-format-discovery",
                       "perseus/legacy-cts-malformed-navigation",
                       "provider/service health", "scholarly"):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.page)


if __name__ == "__main__":
    unittest.main()
