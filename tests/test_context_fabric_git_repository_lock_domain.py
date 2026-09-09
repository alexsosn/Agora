from __future__ import annotations

import contextlib
import inspect
import io
import multiprocessing
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.gitstore import GitStore


def _hold_shared_repository_lock(cache_dir: str, key: str, ready, release) -> None:
    store = GitStore(Path(cache_dir), snapshot_soft_limit_bytes=10_000, min_free_bytes=0)
    with store._repository_lock(key, shared=True, timeout=2):
        ready.set()
        release.wait(5)


class _FakeProcess:
    def __init__(self, stdout: str, *, returncode: int = 0, stderr: str = "") -> None:
        self.stdout = io.StringIO(stdout)
        self.stderr = io.StringIO(stderr)
        self._returncode = returncode

    def wait(self) -> int:
        return self._returncode


class RepositoryUseLockRed2Tests(unittest.TestCase):
    def test_repository_lock_has_explicit_shared_mode(self):
        parameters = inspect.signature(GitStore._repository_lock).parameters
        self.assertIn("shared", parameters)

    def test_shared_reader_blocks_exclusive_mutation_cross_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = GitStore(root / "cache", snapshot_soft_limit_bytes=10_000, min_free_bytes=0)
            ctx = multiprocessing.get_context("spawn")
            ready = ctx.Event()
            release = ctx.Event()
            holder = ctx.Process(
                target=_hold_shared_repository_lock,
                args=(str(store.cache_dir), "fixture", ready, release),
            )
            holder.start()
            try:
                self.assertTrue(ready.wait(3), "shared repository reader never acquired its lock")
                with self.assertRaises(TimeoutError):
                    with store._repository_lock("fixture", shared=False, timeout=0.15):
                        pass
            finally:
                release.set()
                holder.join(5)
                self.assertEqual(holder.exitcode, 0)

    def test_two_shared_repository_readers_can_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = GitStore(root / "cache", snapshot_soft_limit_bytes=10_000, min_free_bytes=0)
            ctx = multiprocessing.get_context("spawn")
            release = ctx.Event()
            ready_a = ctx.Event()
            ready_b = ctx.Event()
            holders = [
                ctx.Process(
                    target=_hold_shared_repository_lock,
                    args=(str(store.cache_dir), "fixture", ready_a, release),
                ),
                ctx.Process(
                    target=_hold_shared_repository_lock,
                    args=(str(store.cache_dir), "fixture", ready_b, release),
                ),
            ]
            for holder in holders:
                holder.start()
            try:
                self.assertTrue(ready_a.wait(3))
                self.assertTrue(ready_b.wait(3), "shared readers serialized unexpectedly")
            finally:
                release.set()
                for holder in holders:
                    holder.join(5)
                    self.assertEqual(holder.exitcode, 0)

    def test_git_show_lines_holds_shared_lock_for_generator_lifetime_and_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GitStore(Path(tmp) / "cache", snapshot_soft_limit_bytes=10_000, min_free_bytes=0)
            repo = store.repositories_dir / "fixture"
            repo.mkdir()
            events: list[tuple[str, str, bool]] = []

            @contextlib.contextmanager
            def observing_lock(key: str, *, shared: bool = False, timeout: float = 30.0):
                events.append(("enter", key, shared))
                try:
                    yield
                finally:
                    events.append(("exit", key, shared))

            with patch.object(store, "_treeish", return_value="HEAD"), patch.object(
                store, "_repository_lock", observing_lock
            ), patch("agora_context_fabric.gitstore._core.subprocess.Popen", return_value=_FakeProcess("one\ntwo\n")):
                lines = store._git_show_lines(repo, "feature.tf")
                self.assertEqual(next(lines), "one")
                self.assertEqual(events, [("enter", "fixture", True)])
                lines.close()

            self.assertEqual(
                events,
                [("enter", "fixture", True), ("exit", "fixture", True)],
            )

    def test_git_show_lines_releases_shared_lock_on_subprocess_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GitStore(Path(tmp) / "cache", snapshot_soft_limit_bytes=10_000, min_free_bytes=0)
            repo = store.repositories_dir / "fixture"
            repo.mkdir()
            events: list[str] = []

            @contextlib.contextmanager
            def observing_lock(key: str, *, shared: bool = False, timeout: float = 30.0):
                self.assertEqual(key, "fixture")
                self.assertTrue(shared)
                events.append("enter")
                try:
                    yield
                finally:
                    events.append("exit")

            with patch.object(store, "_treeish", return_value="HEAD"), patch.object(
                store, "_repository_lock", observing_lock
            ), patch(
                "agora_context_fabric.gitstore._core.subprocess.Popen",
                return_value=_FakeProcess("line\n", returncode=1, stderr="boom"),
            ):
                with self.assertRaises(subprocess.CalledProcessError):
                    list(store._git_show_lines(repo, "feature.tf"))

            self.assertEqual(events, ["enter", "exit"])

    def test_tf_header_metadata_holds_shared_repository_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GitStore(Path(tmp) / "cache", snapshot_soft_limit_bytes=10_000, min_free_bytes=0)
            repo = store.repositories_dir / "fixture"
            repo.mkdir()
            events: list[tuple[str, bool]] = []

            @contextlib.contextmanager
            def observing_lock(key: str, *, shared: bool = False, timeout: float = 30.0):
                self.assertEqual(key, "fixture")
                events.append(("enter", shared))
                try:
                    yield
                finally:
                    events.append(("exit", shared))

            payload = "@node\n@valueType=str\n\n1\tvalue\n"
            with patch.object(store, "_treeish", return_value="HEAD"), patch.object(
                store, "_repository_lock", observing_lock
            ), patch(
                "agora_context_fabric.gitstore._core.subprocess.Popen",
                return_value=_FakeProcess(payload),
            ):
                metadata = store.tf_header_metadata(repo, "feature.tf")

            self.assertEqual(metadata["valueType"], "str")
            self.assertEqual(events, [("enter", True), ("exit", True)])

    def test_repository_status_count_objects_uses_shared_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GitStore(Path(tmp) / "cache", snapshot_soft_limit_bytes=10_000, min_free_bytes=0)
            repo = store.repositories_dir / "fixture"
            repo.mkdir()
            observed: list[bool] = []

            @contextlib.contextmanager
            def observing_lock(key: str, *, shared: bool = False, timeout: float = 30.0):
                self.assertEqual(key, "fixture")
                observed.append(shared)
                yield

            git_metrics = {
                "count": 0,
                "size_bytes": 0,
                "in_pack": 0,
                "packs": 0,
                "size_pack_bytes": 0,
                "prune_packable": 0,
                "garbage": 0,
                "garbage_bytes": 0,
            }
            with patch.object(store, "_repository_lock", observing_lock), patch.object(
                store, "_git_count_objects", return_value=git_metrics
            ), patch.object(store, "_directory_size_bounded", return_value=(0, True)):
                status = store._repository_status()

            self.assertEqual(status["repositories"][0]["inspection_status"], "ok")
            self.assertEqual(observed, [True])


if __name__ == "__main__":
    unittest.main()
