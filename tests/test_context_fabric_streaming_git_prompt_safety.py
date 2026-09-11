from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.operation import OperationControl, operation_scope


class _CompletedProcess:
    def __init__(self, *, binary_stdout: bool = False):
        self.returncode = 0
        self.killed = False
        self.stdout = io.BytesIO() if binary_stdout else io.StringIO("@node\n")
        self.stderr = io.StringIO("")

    def poll(self):
        return self.returncode

    def wait(self, timeout: float | None = None):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


class StreamingGitPromptSafetyTests(unittest.TestCase):
    def _assert_noninteractive_git_popen(self, kwargs: dict) -> None:
        self.assertEqual(
            kwargs.get("stdin"),
            subprocess.DEVNULL,
            "streaming Git must never inherit MCP/server stdin",
        )
        env = kwargs.get("env")
        self.assertIsInstance(env, dict)
        self.assertEqual(env.get("GIT_TERMINAL_PROMPT"), "0")
        self.assertEqual(env.get("LC_ALL"), "C")

    def test_git_show_stream_disables_prompts_and_stdin(self):
        control = OperationControl(acquisition_timeout_seconds=1.0)
        process = _CompletedProcess()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = GitStore(root / "cache", min_free_bytes=0)
            repo = root / "repo"
            repo.mkdir()
            with (
                operation_scope(control),
                patch(
                    "agora_context_fabric.gitstore._core.subprocess.Popen",
                    return_value=process,
                ) as popen,
            ):
                list(store._git_show_lines(repo, "fixture.tf", "deadbeef"))

        self._assert_noninteractive_git_popen(popen.call_args.kwargs)

    def test_git_archive_stream_disables_prompts_and_stdin(self):
        control = OperationControl(acquisition_timeout_seconds=1.0)
        process = _CompletedProcess(binary_stdout=True)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = GitStore(root / "cache", min_free_bytes=0)
            repo = root / "repo"
            repo.mkdir()
            responses = iter(
                [
                    "https://example.invalid/repo.git",
                    "",
                    "",
                    "",
                    "deadbeef",
                ]
            )
            with (
                operation_scope(control),
                patch.object(store, "_run", side_effect=lambda *_args, **_kwargs: next(responses)),
                patch.object(store, "_ensure_free_reserve"),
                patch(
                    "agora_context_fabric.gitstore_long_ops.tarfile.open",
                    return_value=nullcontext([]),
                ),
                patch("agora_context_fabric.gitstore_long_ops.os.replace"),
                patch(
                    "agora_context_fabric.gitstore._core.subprocess.Popen",
                    return_value=process,
                ) as popen,
            ):
                store._export_snapshot(
                    repo,
                    "deadbeef",
                    ".",
                    root / "destination",
                    lambda _path: None,
                )

        self._assert_noninteractive_git_popen(popen.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
