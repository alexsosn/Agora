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
    def __init__(self):
        self.tools: dict[str, object] = {}

    def tool(self, name: str | None = None):
        def decorator(func):
            self.tools[name or func.__name__] = func
            return func

        return decorator


class SnapshotService:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def list_members(self, resource_id, **kwargs):
        self.calls.append(("list", {"resource_id": resource_id, **kwargs}))
        return {"resource_id": resource_id, "source_revision": kwargs.get("source_revision")}

    def prepare(self, resource_id, **kwargs):
        self.calls.append(("prepare", {"resource_id": resource_id, **kwargs}))
        return {"resource_id": resource_id, "source_revision": kwargs.get("source_revision")}

    def load(self, resource_id, **kwargs):
        self.calls.append(("load", {"resource_id": resource_id, **kwargs}))
        return {"resource_id": resource_id, "source_revision": kwargs.get("source_revision")}

    def list_resources(self, *_args, **_kwargs):
        return []

    def describe_resource(self, resource_id):
        return {"id": resource_id}

    def unload(self, logical_name):
        return {"logical_name": logical_name}

    def cache_status(self):
        return {}

    def prune_cache(self, **_kwargs):
        return {}

    def remove_cached(self, resource_id, **_kwargs):
        return {"resource_id": resource_id}


class CollectionSnapshotMcpTests(unittest.TestCase):
    def test_revision_token_round_trips_through_collection_tools(self):
        mcp = FakeMCP()
        service = SnapshotService()
        register_tools(mcp, service)
        revision = "a" * 40

        mcp.tools["list_collection_members"](
            "greek_literature",
            query="Homer",
            source_revision=revision,
            offset=5,
            limit=10,
        )
        mcp.tools["prepare_corpus"](
            "greek_literature",
            member_id="iliad-member",
            source_revision=revision,
        )
        mcp.tools["load_corpus"](
            "greek_literature",
            member_id="iliad-member",
            source_revision=revision,
            features=["word"],
        )

        self.assertEqual(
            service.calls,
            [
                (
                    "list",
                    {
                        "resource_id": "greek_literature",
                        "query": "Homer",
                        "source_revision": revision,
                        "offset": 5,
                        "limit": 10,
                    },
                ),
                (
                    "prepare",
                    {
                        "resource_id": "greek_literature",
                        "member_id": "iliad-member",
                        "modules": None,
                        "source_revision": revision,
                    },
                ),
                (
                    "load",
                    {
                        "resource_id": "greek_literature",
                        "member_id": "iliad-member",
                        "features": ["word"],
                        "modules": None,
                        "source_revision": revision,
                    },
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
