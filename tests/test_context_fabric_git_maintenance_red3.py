from __future__ import annotations

import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from test_context_fabric_git_metadata_maintenance import GitMetadataFixture
from agora_context_fabric.gitstore import _core as gitstore_core


class ExplicitGitMaintenanceRedTests(GitMetadataFixture):
    """RED3 for #45: explicit prune owns bounded Git maintenance."""

    def _plant_garbage(self, store, key: str = "fixture-0") -> Path:
        repo = store.repositories_dir / key
        pack_dir = repo / ".git" / "objects" / "pack"
        pack_dir.mkdir(parents=True, exist_ok=True)
        garbage = pack_dir / "tmp_pack_agora_red3"
        garbage.write_bytes(b"garbage" * 4096)
        return garbage

    def _plant_fragmented_packs(self, store, key: str = "fixture-0", count: int = 18) -> int:
        repo = store.repositories_dir / key
        pack_dir = repo / ".git" / "objects" / "pack"
        pack_dir.mkdir(parents=True, exist_ok=True)
        for index in range(count):
            payload = f"fragment-{index}-{time.time_ns()}\n".encode()
            blob = subprocess.run(
                ["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
                input=payload,
                check=True,
                stdout=subprocess.PIPE,
            ).stdout.decode().strip()
            subprocess.run(
                ["git", "-C", str(repo), "pack-objects", str(pack_dir / f"red3-{index}")],
                input=(blob + "\n").encode(),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        return store._git_count_objects(repo, timeout=5)["packs"]

    def _row(self, result: dict, key: str = "fixture-0") -> dict:
        rows = result["repository_maintenance"]
        return next(row for row in rows if row["cache_key"] == key)

    def test_prune_reports_git_maintenance_and_reclaims_real_garbage(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            garbage = self._plant_garbage(store)
            before = store.cache_status()["repositories"][0]
            self.assertTrue(before["maintenance_needed"])
            self.assertGreater(before["garbage_entries"], 0)

            result = store.prune(target_bytes=0)

            row = self._row(result)
            self.assertTrue(row["maintenance_attempted"])
            self.assertEqual(row["maintenance_status"], "success")
            self.assertTrue(row["before_measurement_complete"])
            self.assertTrue(row["after_measurement_complete"])
            self.assertGreater(row["garbage_entries_before"], 0)
            self.assertEqual(row["garbage_entries_after"], 0)
            self.assertGreater(row["garbage_entries_removed"], 0)
            self.assertFalse(garbage.exists())

    def test_healthy_repository_is_skipped_without_running_gc(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            with patch.object(store, "_git_maintenance") as maintain:
                result = store.prune(target_bytes=0)
            maintain.assert_not_called()
            row = self._row(result)
            self.assertFalse(row["maintenance_attempted"])
            self.assertEqual(row["maintenance_status"], "skipped")

    def test_real_pack_fragmentation_above_threshold_is_materially_reduced(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            before_packs = self._plant_fragmented_packs(store)
            self.assertGreater(before_packs, gitstore_core.DEFAULT_GIT_MAINTENANCE_PACK_LIMIT)

            result = store.prune(target_bytes=0)

            row = self._row(result)
            self.assertEqual(row["maintenance_status"], "success")
            self.assertEqual(row["packs_before"], before_packs)
            self.assertIsInstance(row["packs_after"], int)
            self.assertLess(row["packs_after"], before_packs)

    def test_gc_failure_is_reported_and_logical_prune_still_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            self._plant_garbage(store)
            with patch.object(
                store,
                "_git_maintenance",
                side_effect=subprocess.CalledProcessError(1, ["git", "gc"]),
            ), patch.object(store, "cache_entries", wraps=store.cache_entries) as entries:
                result = store.prune(target_bytes=0)
            self.assertGreaterEqual(entries.call_count, 1)
            row = self._row(result)
            self.assertEqual(row["maintenance_status"], "failed")
            self.assertFalse(row["after_measurement_complete"])
            self.assertIsNone(row["bytes_reclaimed"])
            self.assertIsNone(row["garbage_entries_removed"])
            self.assertEqual(result["repository_maintenance_failed"], 1)

    def test_gc_timeout_is_reported_and_logical_prune_still_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            self._plant_garbage(store)
            with patch.object(
                store,
                "_git_maintenance",
                side_effect=subprocess.TimeoutExpired(["git", "gc"], 0.01),
            ), patch.object(store, "cache_entries", wraps=store.cache_entries) as entries:
                result = store.prune(target_bytes=0)
            self.assertGreaterEqual(entries.call_count, 1)
            row = self._row(result)
            self.assertEqual(row["maintenance_status"], "timed-out")
            self.assertFalse(row["after_measurement_complete"])
            self.assertEqual(result["repository_maintenance_timed_out"], 1)

    def test_many_slow_repositories_share_one_global_maintenance_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp), repositories=3)
            for index in range(3):
                self._plant_garbage(store, f"fixture-{index}")
            seen: list[float] = []

            def timeout(_repo: Path, *, timeout: float):
                seen.append(timeout)
                time.sleep(min(timeout, 0.03))
                raise subprocess.TimeoutExpired(["git", "gc"], timeout)

            with patch.object(gitstore_core, "DEFAULT_GIT_MAINTENANCE_BUDGET_SECONDS", 0.08, create=True), patch.object(
                store, "_git_maintenance", side_effect=timeout
            ):
                started = time.monotonic()
                result = store.prune(target_bytes=0)
                elapsed = time.monotonic() - started

            self.assertLess(elapsed, 0.5)
            self.assertTrue(seen)
            self.assertTrue(all(0 < value <= 0.08 for value in seen))
            self.assertTrue(result["repository_maintenance_budget_exhausted"])
            self.assertGreaterEqual(result["repository_maintenance_skipped_budget"], 1)

    def test_slow_pre_count_objects_consumes_global_maintenance_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp), repositories=2)
            calls: list[float] = []

            def timeout_count(_repo: Path, *, timeout: float):
                calls.append(timeout)
                raise subprocess.TimeoutExpired(["git", "count-objects", "-v"], timeout)

            with patch.object(gitstore_core, "DEFAULT_GIT_MAINTENANCE_BUDGET_SECONDS", 0.05, create=True), patch.object(
                store, "_git_count_objects", side_effect=timeout_count
            ):
                result = store.prune(target_bytes=0)

            self.assertTrue(calls)
            self.assertTrue(all(0 < value <= 0.05 for value in calls))
            self.assertTrue(result["repository_maintenance_budget_exhausted"])
            self.assertTrue(
                all(
                    row["maintenance_status"] in {"budget-exhausted", "timed-out"}
                    for row in result["repository_maintenance"]
                )
            )

    def test_successful_gc_with_post_git_measurement_exhausted_reports_null_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            self._plant_garbage(store)
            real_count = store._git_count_objects
            calls = 0

            def count_then_timeout(repo: Path, *, timeout: float):
                nonlocal calls
                calls += 1
                if calls == 1:
                    return real_count(repo, timeout=timeout)
                raise subprocess.TimeoutExpired(["git", "count-objects", "-v"], timeout)

            with patch.object(store, "_git_count_objects", side_effect=count_then_timeout), patch.object(
                store, "_git_maintenance", return_value=None
            ):
                result = store.prune(target_bytes=0)

            row = self._row(result)
            self.assertEqual(row["maintenance_status"], "success")
            self.assertFalse(row["after_measurement_complete"])
            self.assertIsNone(row["garbage_entries_after"])
            self.assertIsNone(row["garbage_entries_removed"])
            self.assertIsNone(row["packs_after"])
            self.assertFalse(result["repository_reclamation_complete"])

    def test_successful_gc_with_incomplete_post_size_keeps_git_delta_but_not_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            self._plant_garbage(store)
            real_size = store._directory_size_bounded
            size_calls = 0

            def size_then_incomplete(path: Path, *, deadline: float):
                nonlocal size_calls
                if Path(path).is_relative_to(store.repositories_dir):
                    size_calls += 1
                    if size_calls >= 2:
                        return None, False
                return real_size(path, deadline=deadline)

            with patch.object(store, "_directory_size_bounded", side_effect=size_then_incomplete):
                result = store.prune(target_bytes=0)

            row = self._row(result)
            self.assertEqual(row["maintenance_status"], "success")
            self.assertFalse(row["after_measurement_complete"])
            self.assertIsNone(row["bytes_after"])
            self.assertIsNone(row["bytes_reclaimed"])
            self.assertIsInstance(row["garbage_entries_removed"], int)
            self.assertIsInstance(row["packs_after"], int)
            self.assertFalse(result["repository_reclamation_complete"])

    def test_maintenance_uses_exclusive_repository_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            self._plant_garbage(store)
            seen: list[bool] = []
            real_lock = store._repository_lock

            def observed_lock(key: str, timeout: float = 30.0, *, shared: bool = False):
                seen.append(shared)
                return real_lock(key, timeout=timeout, shared=shared)

            with patch.object(store, "_repository_lock", side_effect=observed_lock):
                store.prune(target_bytes=0)

            self.assertIn(False, seen)

    def test_measured_repository_growth_is_not_clamped_to_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            self._plant_garbage(store)
            sizes = iter([(100, True), (125, True)])

            def measured(_path: Path, *, deadline: float):
                return next(sizes)

            with patch.object(store, "_directory_size_bounded", side_effect=measured), patch.object(
                store, "_git_maintenance", return_value=None
            ):
                result = store.prune(target_bytes=0)

            row = self._row(result)
            self.assertEqual(row["bytes_before"], 100)
            self.assertEqual(row["bytes_after"], 125)
            self.assertEqual(row["bytes_reclaimed"], -25)

    def test_second_prune_is_idempotent_after_successful_maintenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            self._plant_garbage(store)
            first = store.prune(target_bytes=0)
            second = store.prune(target_bytes=0)
            self.assertEqual(self._row(first)["maintenance_status"], "success")
            self.assertEqual(self._row(second)["maintenance_status"], "skipped")


if __name__ == "__main__":
    unittest.main()
