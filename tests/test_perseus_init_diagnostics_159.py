from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone

from scripts import smoke_mcp_plugin as smoke


class _InitializeFailureSession:
    async def initialize(self):
        raise RuntimeError("synthetic handshake leaf")

    async def list_tools(self):  # pragma: no cover - initialize must fail first
        raise AssertionError("list_tools must not be reached")


class PerseusInitDiagnostics159Tests(unittest.TestCase):
    def test_error_report_preserves_nested_exception_group_leaf(self):
        error = ExceptionGroup(
            "stdio task group failed",
            [RuntimeError("server stream closed during initialize")],
        )

        report = smoke.build_error_report(
            "sedra",
            error,
            launch=smoke.load_plugin_launch("sedra"),
            env={},
            checked_at=datetime(2026, 9, 11, 17, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(report["error"], "ExceptionGroup: stdio task group failed (1 sub-exception)")
        self.assertEqual(report["error_detail"]["type"], "ExceptionGroup")
        self.assertEqual(report["error_detail"]["message"], "stdio task group failed (1 sub-exception)")
        self.assertEqual(
            report["error_detail"]["exceptions"],
            [
                {
                    "type": "RuntimeError",
                    "message": "server stream closed during initialize",
                }
            ],
        )

    def test_session_failure_identifies_initialize_phase_and_preserves_cause(self):
        async def exercise():
            return await smoke._exercise_session(
                _InitializeFailureSession(),
                "sedra",
                smoke.SMOKE_CASES["sedra"],
                startup_only=True,
                root=smoke.ROOT,
            )

        with self.assertRaises(Exception) as captured:
            asyncio.run(exercise())

        error = captured.exception
        self.assertEqual(type(error).__name__, "SmokePhaseError")
        self.assertEqual(getattr(error, "phase", None), "initialize")
        self.assertIsInstance(error.__cause__, RuntimeError)
        self.assertEqual(str(error.__cause__), "synthetic handshake leaf")


if __name__ == "__main__":
    unittest.main()
