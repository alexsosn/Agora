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

    def test_prune_reports_git_maintenance_and_reclaims_real_garbage(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            garbage = self._plant_garbage(store)
            before = store.cache_status()["repositories"][0]
            self.assertTrue(before["maintenance_needed"])
            self.assertGreater(before["garbage_entries"], 0)

            result = store.prune(target_bytes=0)

            self.assertIn("repository_maintenance", result)
            rows = result["repository_maintenance"]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["cache_key"], "fixture-0")
            self.assertEqual(row["status"], "maintained")
            self.assertGreater(row["before"]["garbage_entries"], 0)
            self.assertEqual(row["after"]["garbage_entries"], 0)
            self.assertFalse(garbage.exists())

    def test_healthy_repository_is_skipped_without_running_gc(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            with patch.object(store, "_git_maintenance") as maintain:
                result = store.prune(target_bytes=0)
            maintain.assert_not_called()
            row = result["repository_maintenance"][0]
            self.assertEqual(row["status"], "not-needed")

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
            row = result["repository_maintenance"][0]
            self.assertEqual(row["status"], "error")
            self.assertFalse(row["after_complete"])

    def test_gc_timeout_is_bounded_by_one_global_maintenance_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp), repositories=3)
            for index in range(3):
                self._plant_garbage(store, f"fixture-{index}")
            seen: list[float] = []

            def timeout(_repo: Path, *, timeout: float):
                seen.append(timeout)
                time.sleep(min(timeout, 0.03))
                raise subprocess.TimeoutExpired(["git", "gc"], timeout)

            with patch.object(gitstore_core, "DEFAULT_GIT_MAINTENANCE_BUDGET_SECONDS", 0.08), patch.object(
                store, "_git_maintenance", side_effect=timeout
            ):
                started = time.monotonic()
                result = store.prune(target_bytes=0)
                elapsed = time.monotonic() - started

            self.assertLess(elapsed, 0.5)
            self.assertTrue(seen)
            self.assertTrue(all(0 < value <= 0.08 for value in seen))
            self.assertTrue(result["repository_maintenance_budget_exhausted"])

    def test_maintenance_uses_exclusive_repository_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            self._plant_garbage(store)
            seen: list[bool] = []
            real_lock = store._repository_lock

            def observed_lock(key: str, *, shared: bool = False, timeout: float = 30.0):
                seen.append(shared)
                return real_lock(key, shared=shared, timeout=timeout)

            with patch.object(store, "_repository_lock", side_effect=observed_lock):
                store.prune(target_bytes=0)

            self.assertIn(False, seen)

    def test_second_prune_is_idempotent_after_successful_maintenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            self._plant_garbage(store)
            first = store.prune(target_bytes=0)
            second = store.prune(target_bytes=0)
            self.assertEqual(first["repository_maintenance"][0]["status"], "maintained")
            self.assertEqual(second["repository_maintenance"][0]["status"], "not-needed")


if __name__ == "__main__":
    unittest.main()
