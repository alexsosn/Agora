from __future__ import annotations

import unittest
from datetime import datetime, timezone

from scripts.smoke_mcp_plugin import (
    ROOT,
    SMOKE_CASES,
    build_error_report,
    build_trace_metadata,
    load_plugin_launch,
)


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

    def test_trace_metadata_binds_report_to_check_run_revision_runtime_and_launch(self):
        env = {
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_REPOSITORY": "alexsosn/Agora",
            "GITHUB_RUN_ID": "123456789",
            "GITHUB_RUN_ATTEMPT": "2",
            "GITHUB_SHA": "a" * 40,
        }
        checked_at = datetime(2026, 9, 5, 12, 34, 56, tzinfo=timezone.utc)
        launch = load_plugin_launch("perseus")

        trace = build_trace_metadata(
            "perseus",
            launch=launch,
            env=env,
            checked_at=checked_at,
        )

        self.assertEqual(trace["check_id"], "mcp-live/perseus-codex")
        self.assertEqual(trace["checked_at"], "2026-09-05T12:34:56Z")
        self.assertEqual(trace["client"], "codex")
        self.assertEqual(trace["transport"], "stdio")
        self.assertEqual(trace["agora_revision"], "a" * 40)
        self.assertEqual(trace["github"]["repository"], "alexsosn/Agora")
        self.assertEqual(trace["github"]["run_id"], "123456789")
        self.assertEqual(trace["github"]["run_attempt"], "2")
        self.assertEqual(
            trace["github"]["run_url"],
            "https://github.com/alexsosn/Agora/actions/runs/123456789",
        )
        self.assertTrue(trace["runtime"]["python"])
        self.assertTrue(trace["runtime"]["platform"])
        self.assertIn("mcp_sdk", trace["runtime"])
        self.assertEqual(trace["launch"]["command"], "uvx")
        self.assertEqual(trace["launch"]["args"], list(launch.args))
        self.assertEqual(trace["launch"]["cwd"], "plugins/perseus")
        self.assertEqual(trace["verification_inputs"]["source"]["revision"], "self")
        self.assertIn("perseus-mcp==1.0.2", trace["verification_inputs"]["resolution"])

    def test_trace_metadata_remains_useful_outside_github_actions(self):
        trace = build_trace_metadata(
            "sedra",
            launch=load_plugin_launch("sedra"),
            env={},
            checked_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
        )
        self.assertEqual(trace["check_id"], "mcp-live/sedra-codex")
        self.assertIsNone(trace["github"]["run_id"])
        self.assertIsNone(trace["github"]["run_url"])
        self.assertTrue(trace["agora_revision"])
        self.assertEqual(trace["launch"]["cwd"], "plugins/sedra")

    def test_error_report_keeps_same_trace_envelope(self):
        env = {
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_REPOSITORY": "alexsosn/Agora",
            "GITHUB_RUN_ID": "987654321",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_SHA": "b" * 40,
        }
        report = build_error_report(
            "context-fabric",
            RuntimeError("synthetic failure"),
            launch=load_plugin_launch("context-fabric"),
            env=env,
            checked_at=datetime(2026, 9, 5, 13, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["check_id"], "mcp-live/context-fabric-codex")
        self.assertEqual(report["agora_revision"], "b" * 40)
        self.assertEqual(report["github"]["run_id"], "987654321")
        self.assertEqual(report["checked_at"], "2026-09-05T13:00:00Z")
        self.assertEqual(report["error"], "RuntimeError: synthetic failure")


if __name__ == "__main__":
    unittest.main()
