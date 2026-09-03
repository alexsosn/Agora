from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.mcp_tools import register_tools
from agora_context_fabric.server import build_parser, select_transport


class FakeMCP:
    def __init__(self):
        self.tools: dict[str, object] = {}

    def tool(self, name: str | None = None):
        def decorator(func):
            tool_name = name or func.__name__
            if tool_name in self.tools:
                raise AssertionError(f"duplicate tool {tool_name}")
            self.tools[tool_name] = func
            return func

        return decorator


class FakeService:
    def __init__(self):
        self.calls: list[tuple[str, tuple, dict]] = []

    def list_resources(self, query="", *, language=None, discipline=None, kind=None):
        self.calls.append(
            (
                "list_resources",
                (query,),
                {"language": language, "discipline": discipline, "kind": kind},
            )
        )
        return [{"id": "bhsa"}]

    def describe_resource(self, resource_id):
        self.calls.append(("describe_resource", (resource_id,), {}))
        return {"id": resource_id}

    def list_members(self, resource_id, *, query="", offset=0, limit=100):
        self.calls.append(
            (
                "list_members",
                (resource_id,),
                {"query": query, "offset": offset, "limit": limit},
            )
        )
        return {"members": [{"id": "member"}]}

    def prepare(self, resource_id, *, member_id=None, modules=None):
        self.calls.append(
            ("prepare", (resource_id,), {"member_id": member_id, "modules": modules})
        )
        return {"logical_name": resource_id}

    def load(self, resource_id, *, member_id=None, features=None, modules=None):
        self.calls.append(
            (
                "load",
                (resource_id,),
                {"member_id": member_id, "features": features, "modules": modules},
            )
        )
        return {"logical_name": resource_id}


class ToolRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        self.service = FakeService()
        register_tools(self.mcp, self.service)

    def test_registers_exact_agora_tool_set(self):
        self.assertEqual(
            set(self.mcp.tools),
            {
                "list_available_corpora",
                "describe_available_corpus",
                "list_collection_members",
                "prepare_corpus",
                "load_corpus",
            },
        )

    def test_discovery_tool_delegates_filters(self):
        result = self.mcp.tools["list_available_corpora"](
            query="dead",
            language="hebrew",
            discipline="judaica",
            kind="corpus",
        )
        self.assertEqual(result, [{"id": "bhsa"}])
        self.assertEqual(
            self.service.calls[-1],
            (
                "list_resources",
                ("dead",),
                {"language": "hebrew", "discipline": "judaica", "kind": "corpus"},
            ),
        )

    def test_collection_tool_delegates_pagination(self):
        result = self.mcp.tools["list_collection_members"](
            "greek_literature", query="homer", offset=10, limit=5
        )
        self.assertEqual(result, {"members": [{"id": "member"}]})
        self.assertEqual(
            self.service.calls[-1],
            (
                "list_members",
                ("greek_literature",),
                {"query": "homer", "offset": 10, "limit": 5},
            ),
        )

    def test_prepare_tool_delegates_selected_modules(self):
        self.mcp.tools["prepare_corpus"]("bhsa", modules=["bhsa-trees"])
        self.assertEqual(
            self.service.calls[-1],
            (
                "prepare",
                ("bhsa",),
                {"member_id": None, "modules": ["bhsa-trees"]},
            ),
        )

    def test_load_tool_delegates_member_features_and_modules(self):
        result = self.mcp.tools["load_corpus"](
            "greek_literature",
            member_id="homer-iliad-a1b2c3d4",
            features=["otype", "word"],
            modules=["example-module"],
        )
        self.assertEqual(result, {"logical_name": "greek_literature"})
        self.assertEqual(
            self.service.calls[-1],
            (
                "load",
                ("greek_literature",),
                {
                    "member_id": "homer-iliad-a1b2c3d4",
                    "features": ["otype", "word"],
                    "modules": ["example-module"],
                },
            ),
        )


class ServerParserTests(unittest.TestCase):
    def test_server_can_start_without_preloaded_corpora(self):
        args = build_parser().parse_args([])
        self.assertIsNone(args.sse)
        self.assertIsNone(args.http)
        self.assertFalse(args.verbose)
        self.assertIsNotNone(args.cache_dir)
        self.assertFalse(hasattr(args, "corpus"))

    def test_transport_selection_is_deterministic(self):
        parser = build_parser()
        self.assertEqual(select_transport(parser.parse_args([])), ("stdio", None))
        self.assertEqual(select_transport(parser.parse_args(["--sse", "8123"])), ("sse", 8123))
        self.assertEqual(select_transport(parser.parse_args(["--http", "9123"])), ("http", 9123))

    def test_sse_and_http_are_mutually_exclusive(self):
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["--sse", "8000", "--http", "9000"])


if __name__ == "__main__":
    unittest.main()
