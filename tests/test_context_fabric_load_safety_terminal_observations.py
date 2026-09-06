from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.cold_compile import ColdCompileLimitError, ColdCompileSupervisor


class _DiskUsage:
    def __init__(self, free: int):
        self.free = free


class _ImmediateProcess:
    def __init__(self, returncode: int = 0):
        self.returncode = returncode
        self.waited = False
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.waited = True
        return self.returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


class _Clock:
    def __init__(self, values):
        self._values = iter(values)
        self._last = 0.0

    def __call__(self):
        try:
            self._last = float(next(self._values))
        except StopIteration:
            pass
        return self._last


class TerminalObservationSafetyTests(unittest.TestCase):
    @staticmethod
    def _supervisor(*, popen, disk_usage, monotonic=None):
        return ColdCompileSupervisor(
            cfm_version="1",
            poll_interval=0,
            terminate_grace_seconds=0,
            popen=popen,
            disk_usage=disk_usage,
            monotonic=monotonic,
            sleep=lambda _seconds: None,
        )

    def test_success_exit_is_rejected_when_final_output_observation_exceeds_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            process = _ImmediateProcess(0)

            def spawn(*_args, **_kwargs):
                cfm = root / ".cfm" / "1"
                cfm.mkdir(parents=True, exist_ok=True)
                (cfm / "payload.bin").write_bytes(b"x" * 101)
                return process

            supervisor = self._supervisor(
                popen=spawn,
                disk_usage=lambda _path: _DiskUsage(free=10_000),
            )
            with self.assertRaises(ColdCompileLimitError) as raised:
                supervisor.run(
                    path=root,
                    logical_name="fixture",
                    features=None,
                    compile_budget_bytes=100,
                    timeout_seconds=60,
                    min_free_bytes=10,
                    cancel_event=threading.Event(),
                )

        self.assertEqual(raised.exception.reason, "compiled-output-budget")
        self.assertGreaterEqual(raised.exception.observed_compiled_bytes, 101)
        self.assertTrue(process.waited)
        self.assertFalse(process.terminated)
        self.assertFalse(process.killed)

    def test_success_exit_is_rejected_when_final_free_space_observation_breaks_reserve(self):
        frees = iter((10_000, 100))
        process = _ImmediateProcess(0)
        supervisor = self._supervisor(
            popen=lambda *_args, **_kwargs: process,
            disk_usage=lambda _path: _DiskUsage(free=next(frees, 100)),
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ColdCompileLimitError) as raised:
                supervisor.run(
                    path=Path(tmp),
                    logical_name="fixture",
                    features=None,
                    compile_budget_bytes=1_000,
                    timeout_seconds=60,
                    min_free_bytes=500,
                    cancel_event=threading.Event(),
                )

        self.assertEqual(raised.exception.reason, "observed-free-space")
        self.assertTrue(process.waited)
        self.assertFalse(process.terminated)
        self.assertFalse(process.killed)

    def test_success_exit_is_rejected_when_final_elapsed_observation_reaches_timeout(self):
        process = _ImmediateProcess(0)
        supervisor = self._supervisor(
            popen=lambda *_args, **_kwargs: process,
            disk_usage=lambda _path: _DiskUsage(free=10_000),
            monotonic=_Clock((0.0, 2.0)),
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ColdCompileLimitError) as raised:
                supervisor.run(
                    path=Path(tmp),
                    logical_name="fixture",
                    features=None,
                    compile_budget_bytes=1_000,
                    timeout_seconds=2.0,
                    min_free_bytes=10,
                    cancel_event=threading.Event(),
                )

        self.assertEqual(raised.exception.reason, "timeout")
        self.assertTrue(process.waited)
        self.assertFalse(process.terminated)
        self.assertFalse(process.killed)


if __name__ == "__main__":
    unittest.main()
