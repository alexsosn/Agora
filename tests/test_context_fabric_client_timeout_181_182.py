"""Regressions for #181 (cancelled acquisition keeps running) and #182
(cold loads cannot finish under a short client tool-call timeout).

The #181 tests use real OS processes. In a blob-less partial clone,
``git archive``/``git show``/``git fetch`` spawn helper processes (lazy
promisor ``git fetch``, ``git-remote-https``, ``index-pack``) that inherit the
parent's stdout. Killing only the direct child leaves those helpers running:
they keep downloading, keep the stdout pipe open, and so keep the request
worker (and the repository lock) busy long after cancellation was reported.
"""

from __future__ import annotations

import json
import os
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

from agora_context_fabric import gitstore as gitstore_module
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.gitstore import _core as core_module
from agora_context_fabric.load_safety import DEFAULT_COMPILE_MAX_MINUTES
from agora_context_fabric.operation import (
    DEFAULT_ACQUISITION_MAX_MINUTES,
    OperationCancelled,
    OperationControl,
    operation_scope,
)

# Stand-in for a Git command whose lazy-fetch helper inherits stdout and keeps
# running after the direct child dies.
_PARENT_WITH_INHERITING_HELPER = r"""
import subprocess, sys, time
subprocess.Popen([
    sys.executable, "-c",
    "import os, sys, time\n"
    "open(sys.argv[1], 'w').write(str(os.getpid()))\n"
    "time.sleep(120)\n",
    sys.argv[1],
])
time.sleep(120)
"""

PROMPT_RETURN_SECONDS = 10.0


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        # Windows reports an invalid/exited PID as a generic OSError.
        return False
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists():
        try:
            state = stat.read_text().rsplit(")", 1)[1].split()[0]
        except (OSError, IndexError):
            return False
        return state not in {"Z", "X"}
    return True


def _wait_for_pid(path: Path, timeout: float = 10.0) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            text = path.read_text().strip()
        except OSError:
            text = ""
        if text:
            return int(text)
        time.sleep(0.02)
    raise AssertionError("helper process did not start")


def _wait_until_dead(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _process_alive(pid):
            return True
        time.sleep(0.05)
    return not _process_alive(pid)


class _HelperTreeCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.pid_file = self.root / "helper.pid"
        self.helper_pid: int | None = None

    def tearDown(self) -> None:
        if self.helper_pid is not None and _process_alive(self.helper_pid):
            try:
                os.kill(self.helper_pid, 9)
            except OSError:
                pass
        self._tmp.cleanup()

    def _substitute(self, real_popen, marker: str):
        pid_file = str(self.pid_file)

        def fake_popen(command, *args, **kwargs):
            if marker in command:
                command = [sys.executable, "-c", _PARENT_WITH_INHERITING_HELPER, pid_file]
            return real_popen(command, *args, **kwargs)

        return fake_popen

    def _cancel_when_helper_starts(self, control: OperationControl) -> threading.Thread:
        def cancel() -> None:
            self.helper_pid = _wait_for_pid(self.pid_file)
            control.cancel()

        thread = threading.Thread(target=cancel, daemon=True)
        thread.start()
        return thread

    def _run_and_join(self, target) -> dict[str, object]:
        outcome: dict[str, object] = {}

        def run() -> None:
            try:
                outcome["result"] = target()
            except BaseException as exc:  # the expected cancellation
                outcome["error"] = exc

        worker = threading.Thread(target=run, daemon=True)
        started = time.monotonic()
        worker.start()
        worker.join(PROMPT_RETURN_SECONDS + 5.0)
        outcome["elapsed"] = time.monotonic() - started
        outcome["alive"] = worker.is_alive()
        return outcome

    def _assert_prompt_cancellation(self, outcome: dict[str, object]) -> None:
        self.assertFalse(
            outcome["alive"],
            "cancelled Git work kept the request worker blocked (#181)",
        )
        self.assertLess(outcome["elapsed"], PROMPT_RETURN_SECONDS)
        self.assertIsInstance(outcome.get("error"), OperationCancelled)
        self.assertIsNotNone(self.helper_pid)
        self.assertTrue(
            _wait_until_dead(self.helper_pid),
            "a Git helper process survived cancellation and keeps downloading (#181)",
        )


class CancelledAcquisitionStopsGitProcessTreeTests(_HelperTreeCase):
    def test_cancelled_snapshot_export_kills_lazy_fetch_helper_and_returns(self):
        store = GitStore(self.root / "cache", min_free_bytes=0)
        repo = self.root / "repo"
        repo.mkdir()
        control = OperationControl(acquisition_timeout_seconds=600.0)
        responses = iter(["https://example.invalid/repo.git", "", "", "", "deadbeef"])
        real_popen = core_module.subprocess.Popen

        def export() -> None:
            with operation_scope(control):
                store._export_snapshot(
                    repo,
                    "deadbeef",
                    "tf/2021",
                    self.root / "destination",
                    lambda _path: None,
                )

        with (
            patch.object(store, "_run", side_effect=lambda *_a, **_k: next(responses)),
            patch.object(store, "_ensure_free_reserve"),
            patch(
                "agora_context_fabric.gitstore._core.subprocess.Popen",
                side_effect=self._substitute(real_popen, "archive"),
            ),
        ):
            self._cancel_when_helper_starts(control)
            outcome = self._run_and_join(export)

        self._assert_prompt_cancellation(outcome)
        self.assertEqual(list((self.root / "cache" / "tmp").glob("snapshot-*")), [])

    def test_cancelled_git_fetch_kills_transport_helpers(self):
        store = GitStore(self.root / "cache", min_free_bytes=0)
        control = OperationControl(acquisition_timeout_seconds=600.0)
        real_popen = gitstore_module.subprocess.Popen

        def fetch() -> None:
            with operation_scope(control):
                store._run_refresh("fetch", "--quiet", "origin")

        with patch(
            "agora_context_fabric.gitstore.subprocess.Popen",
            side_effect=self._substitute(real_popen, "fetch"),
        ):
            self._cancel_when_helper_starts(control)
            outcome = self._run_and_join(fetch)

        self._assert_prompt_cancellation(outcome)

    def test_cancelled_git_show_stream_kills_lazy_fetch_helper(self):
        store = GitStore(self.root / "cache", min_free_bytes=0)
        repo = self.root / "repo"
        repo.mkdir()
        control = OperationControl(acquisition_timeout_seconds=600.0)
        real_popen = core_module.subprocess.Popen

        def show() -> None:
            with operation_scope(control):
                with patch.object(store, "_treeish", return_value="deadbeef"):
                    list(store._git_show_lines(repo, "otype.tf", "deadbeef"))

        with patch(
            "agora_context_fabric.gitstore._core.subprocess.Popen",
            side_effect=self._substitute(real_popen, "show"),
        ):
            self._cancel_when_helper_starts(control)
            outcome = self._run_and_join(show)

        self._assert_prompt_cancellation(outcome)


class RepositoryLockWaitMessageTests(unittest.TestCase):
    def test_lock_wait_timeout_explains_busy_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GitStore(Path(tmp) / "cache", min_free_bytes=0)
            holding = threading.Event()
            release = threading.Event()

            def hold() -> None:
                with store._repository_lock("bhsa"):
                    holding.set()
                    release.wait(10)

            holder = threading.Thread(target=hold, daemon=True)
            holder.start()
            self.assertTrue(holding.wait(5))
            try:
                with self.assertRaises(TimeoutError) as caught:
                    with store._repository_lock("bhsa", timeout=0.1):
                        pass
            finally:
                release.set()
                holder.join(5)

        message = str(caught.exception)
        self.assertIn("timed out waiting for Git cache lock", message)
        self.assertIn("bhsa", message)
        self.assertIn("corpus_cache_status", message)
        self.assertRegex(message, "(?i)another .*(request|process)")


class ClientToolTimeoutBudgetTests(unittest.TestCase):
    """Generated clients must allow one cold prepare/load call to finish (#182)."""

    @staticmethod
    def _load(path: str) -> dict:
        return json.loads((ROOT / path).read_text(encoding="utf-8"))

    def _server_budget_seconds(self) -> float:
        return (DEFAULT_ACQUISITION_MAX_MINUTES + DEFAULT_COMPILE_MAX_MINUTES) * 60.0

    def test_claude_config_declares_per_server_timeout_covering_guardrails(self):
        server = self._load("plugins/context-fabric/.claude-plugin/mcp.json")["context-fabric"]
        timeout_ms = server.get("timeout")
        self.assertIsInstance(timeout_ms, int, "Claude per-server `timeout` (ms) is missing")
        self.assertGreater(timeout_ms / 1000.0, self._server_budget_seconds())

    def test_codex_config_declares_tool_timeout_covering_guardrails(self):
        server = self._load("plugins/context-fabric/.codex-plugin/mcp.json")["mcpServers"][
            "context-fabric"
        ]
        timeout_sec = server.get("tool_timeout_sec")
        self.assertIsInstance(timeout_sec, (int, float), "Codex `tool_timeout_sec` is missing")
        self.assertGreater(float(timeout_sec), self._server_budget_seconds())

    def test_both_clients_project_the_same_canonical_budget(self):
        claude = self._load("plugins/context-fabric/.claude-plugin/mcp.json")["context-fabric"]
        codex = self._load("plugins/context-fabric/.codex-plugin/mcp.json")["mcpServers"][
            "context-fabric"
        ]
        self.assertEqual(claude.get("timeout"), int(codex.get("tool_timeout_sec", 0) * 1000))


class CorpusSkillsPrepareFirstTests(unittest.TestCase):
    def test_large_corpus_skills_direct_first_load_through_prepare(self):
        for skill in ("bhsa-research", "tlhdig-hittite-research", "cuc-ugaritic-research"):
            text = (
                ROOT / "plugins/context-fabric/skills" / skill / "SKILL.md"
            ).read_text(encoding="utf-8")
            with self.subTest(skill=skill):
                self.assertIn("prepare_corpus", text)
                self.assertLess(
                    text.index("prepare_corpus"),
                    text.index("load_corpus"),
                    "first-load guidance must reach prepare_corpus before load_corpus",
                )


if __name__ == "__main__":
    unittest.main()
