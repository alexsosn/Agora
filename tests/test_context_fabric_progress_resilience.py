from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.mcp_tools import register_tools


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name=None):
        def decorator(func):
            self.tools[name or func.__name__] = func
            return func

        return decorator


class _FailingProgressContext:
    async def report_progress(self, progress, total=None, message=None):
        raise RuntimeError("progress transport unavailable")


class _Service:
    def prepare(self, resource_id, *, operation=None, **kwargs):
        operation.stage("resolving")
        operation.stage("acquiring/materializing")
        operation.stage("ready")
        return {"logical_name": resource_id}

    def load(self, resource_id, *, operation=None, **kwargs):
        operation.stage("resolving")
        operation.stage("acquiring/materializing")
        operation.stage("loading/compiling")
        operation.stage("ready")
        return {"logical_name": resource_id}


class ProgressResilienceTests(unittest.TestCase):
    def test_progress_delivery_failure_does_not_convert_success_into_operation_failure(self):
        mcp = _FakeMCP()
        register_tools(mcp, _Service())

        result = asyncio.run(
            mcp.tools["load_corpus"](
                "bhsa",
                ctx=_FailingProgressContext(),
            )
        )

        self.assertEqual(result, {"logical_name": "bhsa"})


if __name__ == "__main__":
    unittest.main()
