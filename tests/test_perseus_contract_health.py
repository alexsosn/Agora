from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml

from scripts import smoke_mcp_plugin as smoke

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "registry/plugins.yaml"
PERSEUS_SKILL = ROOT / "plugins/perseus/skills/perseus-research/SKILL.md"
KNOWN_ISSUE_ID = "perseus/cts-scaife-inventory-routing"
TARGET_WORK = "urn:cts:greekLit:tlg0006.tlg020"


class FakeSession:
    def __init__(self, results: dict[str, object]):
        self.results = results
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def call_tool(self, name: str, arguments: dict[str, object]):
        self.calls.append((name, arguments))
        return self.results[name]


def text_result(payload: object, *, is_error: bool = False):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(
        is_error=is_error,
        content=[SimpleNamespace(type="text", text=text)],
        structured_content=None,
        structuredContent=None,
    )


class PerseusContractHealthTests(unittest.TestCase):
    def test_perseus_declares_structured_cts_scaife_routing_advisory(self):
        document = yaml.safe_load(PLUGINS.read_text(encoding="utf-8"))
        plugins = {plugin["id"]: plugin for plugin in document["plugins"]}
        perseus = plugins["perseus"]

        known_issues = perseus["verification"].get("known_issues", [])
        issue = next(
            (item for item in known_issues if item.get("id") == KNOWN_ISSUE_ID),
            None,
        )
        self.assertIsNotNone(issue, f"missing plugin known issue {KNOWN_ISSUE_ID}")
        self.assertEqual(issue["severity"], "advisory")
        self.assertIn("Scaife", issue["summary"])
        self.assertIn("CTS", issue["summary"])
        self.assertEqual(issue["upstream"][0]["repository"], "tonyjurg/Perseus-mcp")

    def test_perseus_skill_routes_scaife_only_merged_discovery(self):
        skill = PERSEUS_SKILL.read_text(encoding="utf-8")

        self.assertIn("`find_author_names` merges CTS and Scaife", skill)
        self.assertIn(
            "`get_author_resources` and `get_work_resources` are CTS-oriented",
            skill,
        )
        self.assertIn("`get_scaife_library_metadata`", skill)
        self.assertIn("not proof that the work is unavailable", skill)
        self.assertIn(
            "Do not infer that CTS and Scaife edition or translation URNs are equivalent",
            skill,
        )

    def test_perseus_smoke_declares_canonical_routing_canary(self):
        case = smoke.SMOKE_CASES["perseus"]
        self.assertEqual(
            getattr(case, "known_issue_canaries", ()),
            (KNOWN_ISSUE_ID,),
        )

    def test_observed_routing_mismatch_returns_compact_evidence(self):
        runner = getattr(smoke, "run_known_issue_canary", None)
        self.assertTrue(callable(runner), "missing live known-issue canary runner")

        session = FakeSession(
            {
                "find_author_names": text_result(
                    {
                        "authors": [
                            {
                                "urn": "urn:cts:greekLit:tlg0006",
                                "works": [{"urn": TARGET_WORK}],
                            }
                        ]
                    }
                ),
                "get_work_resources": text_result(
                    {"query": TARGET_WORK, "match_count": 0, "matches": []}
                ),
                "get_scaife_library_metadata": text_result(
                    {"urn": TARGET_WORK, "label": "Fragmenta"}
                ),
            }
        )

        evidence = asyncio.run(
            runner(session, "perseus", KNOWN_ISSUE_ID, root=ROOT)
        )
        self.assertEqual(
            evidence,
            {
                "id": KNOWN_ISSUE_ID,
                "status": "observed",
                "target_urn": TARGET_WORK,
                "cts_match_count": 0,
            },
        )
        self.assertEqual(
            [name for name, _arguments in session.calls],
            [
                "find_author_names",
                "get_work_resources",
                "get_scaife_library_metadata",
            ],
        )

    def test_cts_resolution_match_triggers_known_issue_retirement_failure(self):
        runner = getattr(smoke, "run_known_issue_canary", None)
        self.assertTrue(callable(runner), "missing live known-issue canary runner")

        session = FakeSession(
            {
                "find_author_names": text_result(
                    {"authors": [{"works": [{"urn": TARGET_WORK}]}]}
                ),
                "get_work_resources": text_result(
                    {
                        "query": TARGET_WORK,
                        "match_count": 1,
                        "matches": [{"work": {"urn": TARGET_WORK}}],
                    }
                ),
                "get_scaife_library_metadata": text_result(
                    {"urn": TARGET_WORK, "label": "Fragmenta"}
                ),
            }
        )

        with self.assertRaisesRegex(RuntimeError, "may have been fixed"):
            asyncio.run(runner(session, "perseus", KNOWN_ISSUE_ID, root=ROOT))

    def test_canary_rejects_undeclared_known_issue(self):
        runner = getattr(smoke, "run_known_issue_canary", None)
        self.assertTrue(callable(runner), "missing live known-issue canary runner")
        session = FakeSession({})

        with self.assertRaisesRegex(ValueError, "not declared"):
            asyncio.run(
                runner(
                    session,
                    "perseus",
                    "perseus/not-declared",
                    root=ROOT,
                )
            )
        self.assertEqual(session.calls, [])

    def test_json_tool_result_parser_rejects_errors_and_non_json_text(self):
        parser = getattr(smoke, "_json_object_from_tool_result", None)
        self.assertTrue(callable(parser), "missing strict JSON tool-result parser")

        with self.assertRaisesRegex(RuntimeError, "MCP error"):
            parser(
                text_result({"match_count": 0}, is_error=True),
                plugin_id="perseus",
                tool_name="get_work_resources",
            )
        with self.assertRaisesRegex(RuntimeError, "valid JSON object"):
            parser(
                text_result("not json"),
                plugin_id="perseus",
                tool_name="get_work_resources",
            )

    def test_json_tool_result_parser_accepts_fastmcp_wrapped_string_json(self):
        parser = getattr(smoke, "_json_object_from_tool_result", None)
        self.assertTrue(callable(parser), "missing strict JSON tool-result parser")

        result = text_result({"match_count": 0})
        result.structured_content = {"result": json.dumps({"match_count": 0})}

        self.assertEqual(
            parser(
                result,
                plugin_id="perseus",
                tool_name="get_work_resources",
            ),
            {"match_count": 0},
        )


if __name__ == "__main__":
    unittest.main()