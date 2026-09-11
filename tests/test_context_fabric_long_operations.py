from __future__ import annotations

import asyncio
import importlib
import inspect
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.mcp_tools import register_tools


class _FakeMCP:
    def __init__(self):
        self.tools: dict[str, object] = {}

    def tool(self, name: str | None = None):
        def decorator(func):
            tool_name = name or func.__name__
            self.tools[tool_name] = func
            return func

        return decorator


class _FakeContext:
    def __init__(self):
        self.messages: list[str] = []

    async def report_progress(
        self,
        progress: float,
        total: float | None = None,
        message: str | None = None,
    ) -> None:
        if message is not None:
            self.messages.append(message)


class _ProgressService:
    def prepare(self, resource_id: str, *, operation=None, **_kwargs):
        if operation is None:
            raise AssertionError("prepare_corpus must pass an operation control")
        operation.stage("resolving")
        operation.stage("acquiring/materializing")
        operation.stage("ready")
        return {"logical_name": resource_id}

    def load(self, resource_id: str, *, operation=None, **_kwargs):
        if operation is None:
            raise AssertionError("load_corpus must pass an operation control")
        operation.stage("resolving")
        operation.stage("acquiring/materializing")
        operation.stage("loading/compiling")
        operation.stage("ready")
        return {"logical_name": resource_id}


class _CancellationService(_ProgressService):
    def __init__(self):
        self.started = threading.Event()
        self.finished = threading.Event()

    def prepare(self, resource_id: str, *, operation=None, **_kwargs):
        if operation is None:
            raise AssertionError("prepare_corpus must pass an operation control")
        operation.stage("resolving")
        operation.stage("acquiring/materializing")
        self.started.set()
        try:
            while not operation.cancelled:
                time.sleep(0.005)
            operation.raise_if_cancelled()
        finally:
            self.finished.set()
        raise AssertionError("cancelled operation must not return success")


class LongOperationMCPContractTests(unittest.TestCase):
    def test_prepare_and_load_tools_are_async_and_report_ordered_stages(self):
        mcp = _FakeMCP()
        register_tools(mcp, _ProgressService())
        prepare = mcp.tools["prepare_corpus"]
        load = mcp.tools["load_corpus"]

        self.assertTrue(
            inspect.iscoroutinefunction(prepare),
            "prepare_corpus must yield the MCP event loop during long acquisition",
        )
        self.assertTrue(
            inspect.iscoroutinefunction(load),
            "load_corpus must yield the MCP event loop during long acquisition/load",
        )

        async def exercise():
            prepare_ctx = _FakeContext()
            load_ctx = _FakeContext()
            prepared = await prepare("bhsa", ctx=prepare_ctx)
            loaded = await load("bhsa", ctx=load_ctx)
            return prepared, loaded, prepare_ctx.messages, load_ctx.messages

        prepared, loaded, prepare_messages, load_messages = asyncio.run(exercise())
        self.assertEqual(prepared["logical_name"], "bhsa")
        self.assertEqual(loaded["logical_name"], "bhsa")
        self.assertEqual(
            prepare_messages,
            ["resolving", "acquiring/materializing", "ready"],
        )
        self.assertEqual(
            load_messages,
            ["resolving", "acquiring/materializing", "loading/compiling", "ready"],
        )

    def test_mcp_cancellation_signals_operation_and_waits_for_worker_exit(self):
        mcp = _FakeMCP()
        service = _CancellationService()
        register_tools(mcp, service)
        prepare = mcp.tools["prepare_corpus"]
        self.assertTrue(inspect.iscoroutinefunction(prepare))

        async def exercise():
            ctx = _FakeContext()
            task = asyncio.create_task(prepare("bhsa", ctx=ctx))
            started = await asyncio.to_thread(service.started.wait, 1.0)
            self.assertTrue(started, "worker never reached acquisition stage")
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(
                service.finished.is_set(),
                "cancelled MCP handler returned before the worker stopped",
            )
            self.assertNotIn("ready", ctx.messages)

        asyncio.run(exercise())


class _HangingProcess:
    def __init__(self):
        self.killed = False
        self.returncode: int | None = None
        self.stdout = None
        self.stderr = None

    def communicate(self, timeout: float | None = None):
        if self.killed:
            self.returncode = -9
            return ("", "")
        raise subprocess.TimeoutExpired(["git", "fixture"], timeout or 0)

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self, timeout: float | None = None):
        if not self.killed:
            raise subprocess.TimeoutExpired(["git", "fixture"], timeout or 0)
        return self.returncode


class _BlockingStream:
    def __init__(self, process: _HangingProcess, *, stderr: bool = False):
        self.process = process
        self.closed = False
        self.stderr_mode = stderr

    def __iter__(self):
        return self

    def __next__(self):
        while not self.process.killed:
            time.sleep(0.005)
        raise StopIteration

    def read(self):
        return "" if self.stderr_mode else ""

    def close(self):
        self.closed = True


class AcquisitionDeadlineContractTests(unittest.TestCase):
    @staticmethod
    def _operation_module():
        return importlib.import_module("agora_context_fabric.operation")

    def test_regular_git_subprocess_observes_acquisition_deadline(self):
        operation_module = self._operation_module()
        control = operation_module.OperationControl(acquisition_timeout_seconds=0.05)
        process = _HangingProcess()

        with tempfile.TemporaryDirectory() as tmp:
            store = GitStore(Path(tmp) / "cache", min_free_bytes=0)
            with operation_module.operation_scope(control):
                with (
                    patch(
                        "agora_context_fabric.gitstore.subprocess.run",
                        side_effect=AssertionError(
                            "operation-scoped Git must not use an uninterruptible subprocess.run"
                        ),
                    ),
                    patch(
                        "agora_context_fabric.gitstore.subprocess.Popen",
                        return_value=process,
                    ),
                ):
                    with self.assertRaisesRegex(TimeoutError, "acquisition|materialization"):
                        store._run_refresh("fetch", "--quiet")

        self.assertTrue(process.killed)

    def test_streaming_git_subprocess_observes_same_acquisition_deadline(self):
        operation_module = self._operation_module()
        control = operation_module.OperationControl(acquisition_timeout_seconds=0.05)
        process = _HangingProcess()
        process.stdout = _BlockingStream(process)
        process.stderr = _BlockingStream(process, stderr=True)
        outcome: dict[str, BaseException] = {}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = GitStore(root / "cache", min_free_bytes=0)
            repo = root / "repo"
            repo.mkdir()

            def consume() -> None:
                try:
                    with operation_module.operation_scope(control):
                        list(store._git_show_lines(repo, "fixture.tf", "deadbeef"))
                except BaseException as exc:  # capture expected operation timeout
                    outcome["error"] = exc

            with patch(
                "agora_context_fabric.gitstore._core.subprocess.Popen",
                return_value=process,
            ):
                thread = threading.Thread(target=consume, daemon=True)
                thread.start()
                thread.join(0.5)
                if thread.is_alive():
                    process.kill()
                    thread.join(0.5)
                    self.fail("streaming Git read ignored the acquisition deadline")

        self.assertTrue(process.killed)
        self.assertIsInstance(outcome.get("error"), TimeoutError)
        self.assertRegex(str(outcome["error"]), "acquisition|materialization")


if __name__ == "__main__":
    unittest.main()
