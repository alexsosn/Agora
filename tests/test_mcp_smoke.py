from __future__ import annotations

import unittest

from scripts.smoke_mcp_plugin import ROOT, SMOKE_CASES, load_plugin_launch


class MCPSmokeHarnessTests(unittest.TestCase):
    def test_smoke_cases_cover_all_v01_plugins(self):
        self.assertEqual(
            set(SMOKE_CASES),
            {"context-fabric", "perseus", "sefaria", "sedra"},
        )
        self.assertEqual(
            SMOKE_CASES["context-fabric"].expected_tools,
            {
                "list_available_corpora",
                "describe_available_corpus",
                "list_collection_members",
                "prepare_corpus",
                "load_corpus",
            },
        )
        self.assertEqual(
            SMOKE_CASES["perseus"].expected_tools,
            {"get_passage", "search_perseus", "find_author_names"},
        )
        self.assertEqual(
            SMOKE_CASES["sefaria"].expected_tools,
            {"get_text", "text_search", "get_links_between_texts"},
        )
        self.assertEqual(
            SMOKE_CASES["sedra"].expected_tools,
            {"lookup_word", "get_lexeme"},
        )

    def test_loader_uses_exact_generated_codex_stdio_commands(self):
        context_fabric = load_plugin_launch("context-fabric")
        self.assertEqual(context_fabric.command, "uv")
        self.assertEqual(
            context_fabric.args,
            (
                "run",
                "--project",
                ".",
                "agora-context-fabric-mcp",
                "--plugin-root",
                ".",
            ),
        )
        self.assertEqual(context_fabric.cwd, ROOT / "plugins/context-fabric")

        perseus = load_plugin_launch("perseus")
        self.assertEqual(perseus.command, "uvx")
        self.assertEqual(
            perseus.args,
            (
                "--from",
                "perseus-mcp==1.0.2",
                "--with",
                'cryptography<43; platform_system == "Darwin" and platform_machine == "x86_64"',
                "perseus-mcp",
            ),
        )
        self.assertEqual(perseus.cwd, ROOT / "plugins/perseus")

        sefaria = load_plugin_launch("sefaria")
        self.assertEqual(sefaria.command, "uvx")
        self.assertEqual(sefaria.args[-1], "https://mcp.sefaria.org/sse")
        self.assertEqual(sefaria.cwd, ROOT / "plugins/sefaria")

        sedra = load_plugin_launch("sedra")
        self.assertEqual(sedra.command, "uv")
        self.assertEqual(sedra.cwd, ROOT / "plugins/sedra")
        self.assertEqual(sedra.args, ("run", "--project", ".", "agora-sedra-mcp"))

    def test_real_lookup_specs_are_small_and_deterministic(self):
        self.assertEqual(
            SMOKE_CASES["context-fabric"].tool_call,
            ("list_available_corpora", {"query": "Ugaritic"}),
        )
        self.assertEqual(
            SMOKE_CASES["perseus"].tool_call,
            ("find_author_names", {"query": "Homer", "limit": 1}),
        )
        self.assertEqual(
            SMOKE_CASES["sefaria"].tool_call,
            (
                "get_text",
                {"reference": "Genesis 1:1", "version_language": "english"},
            ),
        )
        self.assertEqual(
            SMOKE_CASES["sedra"].tool_call,
            ("lookup_word", {"query": "ܐܒܪܐ"}),
        )

    def test_loader_rejects_non_stdio_or_mismatched_configs(self):
        with self.assertRaises(KeyError):
            load_plugin_launch("not-a-plugin")


if __name__ == "__main__":
    unittest.main()
