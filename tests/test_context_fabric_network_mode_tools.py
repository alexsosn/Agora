from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.mcp_tools import register_tools
from agora_context_fabric.network import current_network_mode


class FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self):
        def decorator(function):
            self.tools[function.__name__] = function
            return function

        return decorator


class ModeRecordingService:
    def __init__(self) -> None:
        self.observed: list[tuple[str, str]] = []

    def _record(self, operation: str) -> dict[str, str]:
        mode = current_network_mode()
        self.observed.append((operation, mode))
        return {"operation": operation, "network_mode": mode}

    def list_members(self, _resource_id: str, **_kwargs):
        return self._record("list_members")

    def prepare(self, _resource_id: str, **_kwargs):
        return self._record("prepare")

    def load(self, _resource_id: str, **_kwargs):
        return self._record("load")

    # Remaining registrations are not invoked by these tests.
    def list_resources(self, *_args, **_kwargs):
        return []

    def describe_resource(self, _resource_id: str):
        return {}

    def unload(self, _logical_name: str):
        return {}

    def cache_status(self):
        return {}

    def prune_cache(self, **_kwargs):
        return {}

    def remove_cached(self, *_args, **_kwargs):
        return {}


class NetworkModeToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mcp = FakeMCP()
        self.service = ModeRecordingService()
        register_tools(self.mcp, self.service)

    def test_prepare_override_is_scoped_to_one_call(self):
        prepare = self.mcp.tools["prepare_corpus"]
        result = prepare("fixture", network_mode="offline")
        self.assertEqual(result["network_mode"], "offline")
        self.assertEqual(current_network_mode(), "auto")

        defaulted = prepare("fixture")
        self.assertEqual(defaulted["network_mode"], "auto")
        self.assertEqual(self.service.observed[-2:], [("prepare", "offline"), ("prepare", "auto")])

    def test_load_and_collection_listing_have_independent_overrides(self):
        load = self.mcp.tools["load_corpus"]
        list_members = self.mcp.tools["list_collection_members"]

        self.assertEqual(
            load("fixture", network_mode="require-fresh")["network_mode"],
            "require-fresh",
        )
        self.assertEqual(
            list_members("collection", network_mode="offline")["network_mode"],
            "offline",
        )
        self.assertEqual(current_network_mode(), "auto")

    def test_invalid_mode_fails_before_service_call(self):
        prepare = self.mcp.tools["prepare_corpus"]
        with self.assertRaisesRegex(ValueError, "network_mode"):
            prepare("fixture", network_mode="sometimes")
        self.assertEqual(self.service.observed, [])


if __name__ == "__main__":
    unittest.main()
