from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.mcp_tools import register_tools


class FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, name: str | None = None):
        def decorator(func):
            tool_name = name or func.__name__
            if tool_name in self.tools:
                raise AssertionError(f"duplicate tool {tool_name}")
            self.tools[tool_name] = func
            return func

        return decorator


class CapturingService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def list_resources(self, query="", **kwargs):
        self.calls.append(("list_resources", (query,), kwargs))
        return []

    def describe_resource(self, resource_id):
        self.calls.append(("describe_resource", (resource_id,), {}))
        return {"id": resource_id}

    def list_members(self, resource_id, **kwargs):
        self.calls.append(("list_members", (resource_id,), kwargs))
        return {"items": []}

    def prepare(self, resource_id, **kwargs):
        self.calls.append(("prepare", (resource_id,), kwargs))
        return {"logical_name": resource_id}

    def load(self, resource_id, **kwargs):
        self.calls.append(("load", (resource_id,), kwargs))
        return {"logical_name": resource_id}

    def cancel_load(self, load_id):
        self.calls.append(("cancel_load", (load_id,), {}))
        return {"found": False, "load_id": load_id}

    def unload(self, logical_name):
        self.calls.append(("unload", (logical_name,), {}))
        return {"logical_name": logical_name}

    def cache_status(self):
        self.calls.append(("cache_status", (), {}))
        return {}

    def prune_cache(self, **kwargs):
        self.calls.append(("prune_cache", (), kwargs))
        return {}

    def remove_cached(self, resource_id, **kwargs):
        self.calls.append(("remove_cached", (resource_id,), kwargs))
        return {}


class OfflineSourceModeMCPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mcp = FakeMCP()
        self.service = CapturingService()
        register_tools(self.mcp, self.service)

    def test_collection_members_forwards_explicit_offline_mode(self):
        self.mcp.tools["list_collection_members"](
            "greek_literature",
            source_mode="offline",
        )
        self.assertEqual(self.service.calls[-1][0], "list_members")
        self.assertEqual(self.service.calls[-1][2]["source_mode"], "offline")

    def test_prepare_forwards_explicit_offline_mode(self):
        self.mcp.tools["prepare_corpus"]("bhsa", source_mode="offline")
        self.assertEqual(self.service.calls[-1][0], "prepare")
        self.assertEqual(self.service.calls[-1][2]["source_mode"], "offline")

    def test_load_forwards_explicit_require_fresh_mode(self):
        self.mcp.tools["load_corpus"]("bhsa", source_mode="require-fresh")
        self.assertEqual(self.service.calls[-1][0], "load")
        self.assertEqual(self.service.calls[-1][2]["source_mode"], "require-fresh")

    def test_omitted_source_mode_preserves_historical_delegation_shape(self):
        self.mcp.tools["prepare_corpus"]("bhsa")
        self.assertNotIn("source_mode", self.service.calls[-1][2])

        self.mcp.tools["load_corpus"]("bhsa")
        self.assertNotIn("source_mode", self.service.calls[-1][2])

        self.mcp.tools["list_collection_members"]("greek_literature")
        self.assertNotIn("source_mode", self.service.calls[-1][2])


if __name__ == "__main__":
    unittest.main()
