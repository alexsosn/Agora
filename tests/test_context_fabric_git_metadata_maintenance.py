from __future__ import annotations

import multiprocessing
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.gitstore import _core as gitstore_core


def _hold_repository_lock(cache_dir: str, key: str, ready, release) -> None:
    store = GitStore(Path(cache_dir), snapshot_soft_limit_bytes=10_000, min_free_bytes=0)
    with store._repository_lock(key, timeout=2):
        ready.set()
        release.wait(5)


class GitMetadataFixture(unittest.TestCase):
    @staticmethod
    def _init_repo(path: Path, payload: str = "payload") -> None:
        path.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.name", "Agora Tests"], cwd=path, check=True)
        (path / "data.txt").write_text(payload, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=path, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=path, check=True)

    def make_store(self, root: Path, *, repositories: int = 1) -> GitStore:
        store = GitStore(root / "cache", snapshot_soft_limit_bytes=10_000, min_free_bytes=0)
        for index in range(repositories):
            source = root / f"source-{index}"
            self._init_repo(source, payload=f"payload-{index}")
            store.ensure_metadata(str(source), cache_key=f"fixture-{index}")
        return store


class CountObjectsParserRedTests(unittest.TestCase):
    VALID = """count: 2
size: 3
in-pack: 4
packs: 5
size-pack: 6
prune-packable: 7
garbage: 8
size-garbage: 9
alternate: ignored
"""

    def test_parse_count_objects_converts_kib_fields_to_bytes(self):
        parsed = GitStore._parse_count_objects(self.VALID)
        self.assertEqual(
            parsed,
            {
                "count": 2,
                "size_bytes": 3 * 1024,
                "in_pack": 4,
                "packs": 5,
                "size_pack_bytes": 6 * 1024,
                "prune_packable": 7,
                "garbage": 8,
                "garbage_bytes": 9 * 1024,
            },
        )

    def test_parse_count_objects_rejects_missing_duplicate_malformed_and_negative_fields(self):
        cases = [
            self.VALID.replace("garbage: 8\n", ""),
            self.VALID + "packs: 5\n",
            self.VALID.replace("packs: 5", "packs: nope"),
            self.VALID.replace("garbage: 8", "garbage: -1"),
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    GitStore._parse_count_objects(payload)


class RepositoryStatusRedTests(GitMetadataFixture):
    def test_status_reports_repository_storage_separately_from_logical_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            status = store.cache_status()

            self.assertEqual(status["cache_bytes"], 0)
            self.assertGreater(status["repository_cache_bytes"], 0)
            self.assertTrue(status["repository_cache_bytes_complete"])
            self.assertTrue(status["repository_git_metrics_complete"])
            self.assertEqual(len(status["repositories"]), 1)
            row = status["repositories"][0]
            self.assertEqual(row["cache_key"], "fixture-0")
            self.assertEqual(row["inspection_status"], "ok")
            self.assertTrue(row["size_complete"])
            self.assertIsInstance(row["packs"], int)
            self.assertIsInstance(row["garbage_entries"], int)
            self.assertIsInstance(row["garbage_bytes"], int)

    def test_git_recognized_garbage_is_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            repo = store.repositories_dir / "fixture-0"
            pack_dir = repo / ".git" / "objects" / "pack"
            pack_dir.mkdir(parents=True, exist_ok=True)
            garbage = pack_dir / "tmp_pack_agora_fixture"
            garbage.write_bytes(b"garbage" * 32)

            status = store.cache_status()
            row = status["repositories"][0]
            self.assertEqual(row["inspection_status"], "ok")
            self.assertGreaterEqual(row["garbage_entries"], 1)
            self.assertGreater(row["garbage_bytes"], 0)
            self.assertGreaterEqual(status["repository_garbage_entries"], 1)
            self.assertGreater(status["repository_garbage_bytes"], 0)

    def test_busy_repository_is_bounded_and_makes_git_aggregate_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            ctx = multiprocessing.get_context("spawn")
            ready = ctx.Event()
            release = ctx.Event()
            holder = ctx.Process(
                target=_hold_repository_lock,
                args=(str(store.cache_dir), "fixture-0", ready, release),
            )
            holder.start()
            self.assertTrue(ready.wait(3))
            try:
                with patch.object(gitstore_core, "DEFAULT_GIT_STATUS_BUDGET_SECONDS", 0.15):
                    started = time.monotonic()
                    status = store.cache_status()
                    elapsed = time.monotonic() - started
                self.assertLess(elapsed, 0.6)
                row = status["repositories"][0]
                self.assertEqual(row["inspection_status"], "busy")
                self.assertTrue(row["busy"])
                self.assertFalse(status["repository_git_metrics_complete"])
                self.assertIsNone(status["repository_pack_count"])
                self.assertIsNone(status["repository_garbage_entries"])
                self.assertIsNone(status["repository_garbage_bytes"])
            finally:
                release.set()
                holder.join(5)
                self.assertEqual(holder.exitcode, 0)

    def test_many_busy_repositories_share_one_status_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp), repositories=3)
            ctx = multiprocessing.get_context("spawn")
            release = ctx.Event()
            holders = []
            ready_events = []
            for index in range(3):
                ready = ctx.Event()
                process = ctx.Process(
                    target=_hold_repository_lock,
                    args=(str(store.cache_dir), f"fixture-{index}", ready, release),
                )
                process.start()
                holders.append(process)
                ready_events.append(ready)
            for ready in ready_events:
                self.assertTrue(ready.wait(3))
            try:
                with patch.object(gitstore_core, "DEFAULT_GIT_STATUS_BUDGET_SECONDS", 0.15):
                    started = time.monotonic()
                    status = store.cache_status()
                    elapsed = time.monotonic() - started
                self.assertLess(elapsed, 0.6)
                self.assertTrue(status["repository_inspection_budget_exhausted"])
                self.assertTrue(
                    any(
                        row["inspection_status"] == "budget-exhausted"
                        for row in status["repositories"]
                    )
                )
            finally:
                release.set()
                for process in holders:
                    process.join(5)
                    self.assertEqual(process.exitcode, 0)

    def test_slow_count_objects_consumes_remaining_global_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            seen_timeouts: list[float] = []

            def timeout_count_objects(_repo: Path, *, timeout: float):
                seen_timeouts.append(timeout)
                raise subprocess.TimeoutExpired(["git", "count-objects", "-v"], timeout)

            with patch.object(gitstore_core, "DEFAULT_GIT_STATUS_BUDGET_SECONDS", 0.12), patch.object(
                store, "_git_count_objects", side_effect=timeout_count_objects
            ):
                started = time.monotonic()
                status = store.cache_status()
                elapsed = time.monotonic() - started

            self.assertLess(elapsed, 0.5)
            self.assertEqual(len(seen_timeouts), 1)
            self.assertGreater(seen_timeouts[0], 0)
            self.assertLessEqual(seen_timeouts[0], 0.12)
            self.assertEqual(status["repositories"][0]["inspection_status"], "budget-exhausted")
            self.assertFalse(status["repository_git_metrics_complete"])

    def test_interrupted_repository_size_is_null_not_partial_and_bytes_aggregate_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))

            real_bounded_size = store._directory_size_bounded

            def incomplete_size(path: Path, *, deadline: float):
                if Path(path).is_relative_to(store.repositories_dir):
                    return None, False
                return real_bounded_size(path, deadline=deadline)

            with patch.object(store, "_directory_size_bounded", side_effect=incomplete_size):
                status = store.cache_status()

            row = status["repositories"][0]
            self.assertIsNone(row["size_bytes"])
            self.assertFalse(row["size_complete"])
            self.assertIsNone(status["repository_cache_bytes"])
            self.assertFalse(status["repository_cache_bytes_complete"])
            self.assertTrue(status["repository_git_metrics_complete"])

    def test_partial_git_rows_remain_visible_but_aggregate_is_null(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp), repositories=2)
            real_count = store._git_count_objects

            def mixed_count(repo: Path, *, timeout: float):
                if repo.name == "fixture-1":
                    raise RuntimeError("simulated inspection failure")
                return real_count(repo, timeout=timeout)

            with patch.object(store, "_git_count_objects", side_effect=mixed_count):
                status = store.cache_status()

            first = next(row for row in status["repositories"] if row["cache_key"] == "fixture-0")
            second = next(row for row in status["repositories"] if row["cache_key"] == "fixture-1")
            self.assertEqual(first["inspection_status"], "ok")
            self.assertIsInstance(first["packs"], int)
            self.assertEqual(second["inspection_status"], "error")
            self.assertFalse(status["repository_git_metrics_complete"])
            self.assertIsNone(status["repository_pack_count"])
            self.assertIsNone(status["repository_garbage_entries"])
            self.assertIsNone(status["repository_garbage_bytes"])

    def test_successful_rows_produce_exact_git_aggregates(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp), repositories=2)
            status = store.cache_status()
            rows = status["repositories"]
            self.assertTrue(status["repository_git_metrics_complete"])
            self.assertEqual(status["repository_pack_count"], sum(row["packs"] for row in rows))
            self.assertEqual(
                status["repository_garbage_entries"],
                sum(row["garbage_entries"] for row in rows),
            )
            self.assertEqual(
                status["repository_garbage_bytes"],
                sum(row["garbage_bytes"] for row in rows),
            )


class DeadlineAwareDirectorySizeRedTests(unittest.TestCase):
    def test_recursive_size_walk_stops_when_deadline_expires(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index in range(20):
                (root / f"file-{index}.bin").write_bytes(b"x" * 128)
            store = GitStore(root / "cache", snapshot_soft_limit_bytes=10_000, min_free_bytes=0)

            real_walk = os.walk

            def slow_walk(path):
                for item in real_walk(path):
                    time.sleep(0.01)
                    yield item

            with patch.object(gitstore_core.os, "walk", side_effect=slow_walk):
                size, complete = store._directory_size_bounded(
                    root,
                    deadline=time.monotonic() + 0.005,
                )
            self.assertIsNone(size)
            self.assertFalse(complete)


if __name__ == "__main__":
    unittest.main()
