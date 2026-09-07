from __future__ import annotations

import inspect
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog, ResourceSpec
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.mcp_tools import register_tools
from agora_context_fabric.service import ContextFabricService


class ColdLoadPolicyContractTests(unittest.TestCase):
    def _safety(self):
        from agora_context_fabric import load_safety

        return load_safety

    def test_source_budget_counts_only_direct_tf_files(self):
        safety = self._safety()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.tf").write_bytes(b"a" * 10)
            (root / "b.tf").write_bytes(b"b" * 20)
            (root / "notes.txt").write_bytes(b"x" * 1000)
            nested = root / "nested"
            nested.mkdir()
            (nested / "ignored.tf").write_bytes(b"z" * 500)
            self.assertEqual(safety.source_tf_bytes(root), 30)

    def test_default_budget_is_sixteen_x_with_256_mib_floor(self):
        safety = self._safety()
        mib = 1024**2
        self.assertEqual(safety.compile_budget_bytes(1), 256 * mib)
        self.assertEqual(safety.compile_budget_bytes(100 * mib), 1600 * mib)

    def test_explicit_limits_are_positive_and_do_not_change_reserve(self):
        safety = self._safety()
        gib = 1024**3
        self.assertEqual(safety.compile_budget_bytes(100, max_compile_gb=1.5), int(1.5 * gib))
        self.assertEqual(safety.compile_timeout_seconds(max_compile_minutes=2.5), 150.0)
        for value in (0, -1):
            with self.assertRaises(ValueError):
                safety.compile_budget_bytes(100, max_compile_gb=value)
            with self.assertRaises(ValueError):
                safety.compile_timeout_seconds(max_compile_minutes=value)

    def test_current_cfm_marker_is_version_scoped(self):
        safety = self._safety()
        path = Path("/tmp/corpus")
        self.assertEqual(
            safety.cfm_marker(path, "1"),
            path / ".cfm" / "1" / "meta.json",
        )


class StoreCompileLockContractTests(unittest.TestCase):
    def test_store_exposes_separate_compile_lock(self):
        self.assertTrue(hasattr(GitStore, "compile_lock"))
        signature = inspect.signature(GitStore.compile_lock)
        self.assertIn("path", signature.parameters)
        self.assertIn("timeout", signature.parameters)


class ServiceColdLoadContractTests(unittest.TestCase):
    @staticmethod
    def _resource() -> ResourceSpec:
        return ResourceSpec(
            id="fixture",
            name="Fixture",
            plugin="context-fabric",
            provider="context-fabric",
            kind="corpus",
            repository="unused/repository",
            languages=("test",),
            disciplines=("testing",),
        )

    def test_load_accepts_explicit_compile_limits(self):
        signature = inspect.signature(ContextFabricService.load)
        self.assertIn("max_compile_gb", signature.parameters)
        self.assertIn("max_compile_minutes", signature.parameters)

    def test_cache_status_exposes_active_loads(self):
        class Store:
            def cache_status(self):
                return {"cache_bytes": 0}

        class Resolver:
            store = Store()

        service = ContextFabricService(Catalog([self._resource()]), Resolver(), object())
        status = service.cache_status()
        self.assertIn("active_loads", status)
        self.assertEqual(status["active_loads"], [])

    def test_service_exposes_idempotent_cancel_api(self):
        self.assertTrue(hasattr(ContextFabricService, "cancel_load"))
        class Store:
            def cache_status(self):
                return {}
        class Resolver:
            store = Store()
        service = ContextFabricService(Catalog([self._resource()]), Resolver(), object())
        result = service.cancel_load("missing")
        self.assertEqual(
            result,
            {
                "found": False,
                "load_id": "missing",
                "cancellation_requested": False,
                "phase": None,
            },
        )


class McpColdLoadSafetyContractTests(unittest.TestCase):
    class FakeMCP:
        def __init__(self):
            self.tools: dict[str, object] = {}

        def tool(self, name: str | None = None):
            def decorator(func):
                self.tools[name or func.__name__] = func
                return func
            return decorator

    class FakeService:
        def __init__(self):
            self.calls = []

        def list_resources(self, *args, **kwargs): return []
        def describe_resource(self, *args, **kwargs): return {}
        def list_members(self, *args, **kwargs): return {"members": []}
        def prepare(self, *args, **kwargs): return {}
        def unload(self, *args, **kwargs): return {}
        def cache_status(self, *args, **kwargs): return {}
        def prune_cache(self, *args, **kwargs): return {}
        def remove_cached(self, *args, **kwargs): return {}

        def load(self, resource_id, **kwargs):
            self.calls.append(("load", resource_id, kwargs))
            return {"logical_name": resource_id}

        def cancel_load(self, load_id):
            self.calls.append(("cancel", load_id, {}))
            return {"found": True, "load_id": load_id, "cancellation_requested": True, "phase": "compiling"}

    def setUp(self):
        self.mcp = self.FakeMCP()
        self.service = self.FakeService()
        register_tools(self.mcp, self.service)

    def test_cancel_tool_is_registered(self):
        self.assertIn("cancel_corpus_load", self.mcp.tools)

    def test_load_tool_forwards_compile_limits(self):
        self.mcp.tools["load_corpus"](
            "fixture",
            max_compile_gb=2.0,
            max_compile_minutes=5.0,
        )
        self.assertEqual(
            self.service.calls[-1],
            (
                "load",
                "fixture",
                {
                    "member_id": None,
                    "features": None,
                    "modules": None,
                    "max_compile_gb": 2.0,
                    "max_compile_minutes": 5.0,
                },
            ),
        )

    def test_cancel_tool_delegates_by_load_id(self):
        result = self.mcp.tools["cancel_corpus_load"]("load-123")
        self.assertTrue(result["cancellation_requested"])
        self.assertEqual(self.service.calls[-1], ("cancel", "load-123", {}))


if __name__ == "__main__":
    unittest.main()
