from __future__ import annotations

import contextlib
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from test_context_fabric_git_metadata_maintenance import GitMetadataFixture
from agora_context_fabric.gitstore import _core as gitstore_core


class GitMaintenanceFollowup142RedTests(GitMetadataFixture):
    @staticmethod
    def _healthy_git_metrics() -> dict[str, int]:
        return {
            "count": 0,
            "size_bytes": 0,
            "in_pack": 0,
            "packs": 1,
            "size_pack_bytes": 0,
            "prune_packable": 0,
            "garbage": 0,
            "garbage_bytes": 0,
        }

    def test_repository_lock_wait_respects_prune_caller_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            observed_timeouts: list[float] = []

            @contextlib.contextmanager
            def observed_lock(key: str, timeout: float = 30.0, *, shared: bool = False):
                self.assertEqual(key, "fixture-0")
                self.assertFalse(shared)
                observed_timeouts.append(timeout)
                yield

            with patch.object(store, "_repository_lock", side_effect=observed_lock), patch.object(
                store, "_git_count_objects", return_value=self._healthy_git_metrics()
            ), patch.object(store, "_directory_size_bounded", return_value=(123, True)):
                store.prune(target_bytes=0, timeout=0.05)

            self.assertTrue(observed_timeouts)
            self.assertTrue(
                all(0 < value <= 0.05 for value in observed_timeouts),
                f"repository maintenance lock waits escaped caller policy: {observed_timeouts}",
            )

    def test_healthy_repo_size_walk_exhausting_budget_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))

            def exhaust_budget(_path: Path, *, deadline: float):
                time.sleep(0.05)
                return None, False

            with patch.object(
                gitstore_core,
                "DEFAULT_GIT_MAINTENANCE_BUDGET_SECONDS",
                0.02,
                create=True,
            ), patch.object(
                store, "_git_count_objects", return_value=self._healthy_git_metrics()
            ), patch.object(
                store, "_directory_size_bounded", side_effect=exhaust_budget
            ), patch.object(store, "_git_maintenance") as maintain:
                result = store.prune(target_bytes=0)

            maintain.assert_not_called()
            row = result["repository_maintenance"][0]
            self.assertEqual(row["maintenance_status"], "skipped")
            self.assertFalse(row["before_measurement_complete"])
            self.assertTrue(
                result["repository_maintenance_budget_exhausted"],
                "deadline exhaustion during the required pre-maintenance size observation must be visible",
            )


if __name__ == "__main__":
    unittest.main()
