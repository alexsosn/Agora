from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from scripts import smoke_mcp_plugin as smoke


class _InitializeFailureSession:
    async def initialize(self):
        raise RuntimeError("synthetic handshake leaf")

    async def list_tools(self):  # pragma: no cover - initialize must fail first
        raise AssertionError("list_tools must not be reached")


class _InitializeCancellationSession:
    async def initialize(self):
        raise asyncio.CancelledError()

    async def list_tools(self):  # pragma: no cover - initialize must cancel first
        raise AssertionError("list_tools must not be reached")


class _ListToolsFailureSession:
    async def initialize(self):
        return SimpleNamespace()

    async def list_tools(self):
        raise RuntimeError("synthetic list-tools leaf")


class _CallToolFailureSession:
    async def initialize(self):
        return SimpleNamespace()

    async def list_tools(self):
        return SimpleNamespace(
            tools=[SimpleNamespace(name=name) for name in smoke.SMOKE_CASES["sedra"].expected_tools]
        )

    async def call_tool(self, *_args, **_kwargs):
        raise RuntimeError("synthetic call-tool leaf")


class _PerseusCanarySession:
    async def initialize(self):
        return SimpleNamespace()

    async def list_tools(self):
        return SimpleNamespace(
            tools=[SimpleNamespace(name=name) for name in smoke.SMOKE_CASES["perseus"].expected_tools]
        )

    async def call_tool(self, *_args, **_kwargs):
        return SimpleNamespace(content=[SimpleNamespace(text="payload")], is_error=False)


class PerseusInitDiagnostics159Tests(unittest.TestCase):
    def _exercise(self, session, plugin_id: str, *, startup_only: bool = False):
        return asyncio.run(
            smoke._exercise_session(
                session,
                plugin_id,
                smoke.SMOKE_CASES[plugin_id],
                startup_only=startup_only,
                root=smoke.ROOT,
            )
        )

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

    def test_error_report_serializes_phase_and_original_cause(self):
        cause = RuntimeError("synthetic nested cause")
        try:
            raise smoke.SmokePhaseError("initialize", cause) from cause
        except smoke.SmokePhaseError as error:
            report = smoke.build_error_report(
                "sedra",
                error,
                launch=smoke.load_plugin_launch("sedra"),
                env={},
                checked_at=datetime(2026, 9, 11, 17, 0, tzinfo=timezone.utc),
            )

        detail = report["error_detail"]
        self.assertEqual(detail["type"], "SmokePhaseError")
        self.assertEqual(detail["phase"], "initialize")
        self.assertEqual(
            detail["cause"],
            {"type": "RuntimeError", "message": "synthetic nested cause"},
        )

    def test_session_failure_identifies_initialize_phase_and_preserves_cause(self):
        with self.assertRaises(smoke.SmokePhaseError) as captured:
            self._exercise(_InitializeFailureSession(), "sedra", startup_only=True)

        error = captured.exception
        self.assertEqual(error.phase, "initialize")
        self.assertIsInstance(error.__cause__, RuntimeError)
        self.assertEqual(str(error.__cause__), "synthetic handshake leaf")

    def test_session_failure_identifies_list_tools_phase(self):
        with self.assertRaises(smoke.SmokePhaseError) as captured:
            self._exercise(_ListToolsFailureSession(), "sedra", startup_only=True)

        self.assertEqual(captured.exception.phase, "list_tools")
        self.assertEqual(str(captured.exception.__cause__), "synthetic list-tools leaf")

    def test_session_failure_identifies_representative_call_tool_phase(self):
        with self.assertRaises(smoke.SmokePhaseError) as captured:
            self._exercise(_CallToolFailureSession(), "sedra")

        self.assertEqual(captured.exception.phase, "call_tool")
        self.assertEqual(str(captured.exception.__cause__), "synthetic call-tool leaf")

    def test_session_failure_identifies_known_issue_canary_phase(self):
        with patch.object(
            smoke,
            "run_known_issue_canary",
            side_effect=RuntimeError("synthetic canary leaf"),
        ):
            with self.assertRaises(smoke.SmokePhaseError) as captured:
                self._exercise(_PerseusCanarySession(), "perseus")

        self.assertEqual(captured.exception.phase, "known_issue_canary")
        self.assertEqual(str(captured.exception.__cause__), "synthetic canary leaf")

    def test_cancellation_is_not_reclassified_as_a_smoke_phase_error(self):
        with self.assertRaises(asyncio.CancelledError):
            self._exercise(_InitializeCancellationSession(), "sedra", startup_only=True)


if __name__ == "__main__":
    unittest.main()
