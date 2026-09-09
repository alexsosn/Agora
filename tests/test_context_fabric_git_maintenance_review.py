from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_context_fabric_git_metadata_maintenance import GitMetadataFixture


class GitMaintenanceMeasurementIndependenceReviewTests(GitMetadataFixture):
    """Adversarial RED3b/c/d: maintenance, byte and Git observations stay independent."""

    def _plant_garbage(self, store) -> None:
        repo = store.repositories_dir / "fixture-0"
        pack_dir = repo / ".git" / "objects" / "pack"
        pack_dir.mkdir(parents=True, exist_ok=True)
        (pack_dir / "tmp_pack_agora_review").write_bytes(b"garbage" * 4096)

    def test_incomplete_pre_gc_size_measurement_does_not_suppress_git_maintenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            self._plant_garbage(store)
            real_count = store._git_count_objects
            git_calls = 0

            def measured_git(repo: Path, *, timeout: float):
                nonlocal git_calls
                git_calls += 1
                return real_count(repo, timeout=timeout)

            with patch.object(
                store,
                "_directory_size_bounded",
                return_value=(None, False),
            ), patch.object(
                store,
                "_git_count_objects",
                side_effect=measured_git,
            ), patch.object(
                store,
                "_git_maintenance",
                wraps=store._git_maintenance,
            ) as maintain:
                result = store.prune(target_bytes=0)

            maintain.assert_called_once()
            self.assertGreaterEqual(git_calls, 2, "post-GC Git debt must still be observed")
            row = result["repository_maintenance"][0]
            self.assertEqual(row["maintenance_status"], "success")
            self.assertFalse(row["before_measurement_complete"])
            self.assertFalse(row["after_measurement_complete"])
            self.assertIsNone(row["bytes_before"])
            self.assertIsNone(row["bytes_after"])
            self.assertIsNone(row["bytes_reclaimed"])
            self.assertGreater(row["garbage_entries_before"], 0)
            self.assertEqual(row["garbage_entries_after"], 0)
            self.assertGreater(row["garbage_entries_removed"], 0)

            # Byte aggregate is incomplete, but the independently observed Git
            # debt delta remains exact and must not be thrown away with it.
            self.assertFalse(result["repository_reclamation_complete"])
            self.assertIsNone(result["repository_bytes_reclaimed"])
            self.assertTrue(result["repository_git_reclamation_complete"])
            self.assertGreater(result["repository_garbage_entries_removed"], 0)
            self.assertIsInstance(result["repository_packs_before"], int)
            self.assertIsInstance(result["repository_packs_after"], int)

    def test_skipped_healthy_repo_does_not_invent_complete_byte_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            with patch.object(
                store,
                "_directory_size_bounded",
                return_value=(None, False),
            ), patch.object(store, "_git_maintenance") as maintain:
                result = store.prune(target_bytes=0)

            maintain.assert_not_called()
            row = result["repository_maintenance"][0]
            self.assertEqual(row["maintenance_status"], "skipped")
            self.assertFalse(row["before_measurement_complete"])
            self.assertFalse(row["after_measurement_complete"])
            self.assertIsNone(row["bytes_before"])
            self.assertIsNone(row["bytes_after"])
            self.assertIsNone(row["bytes_reclaimed"])
            self.assertIsNone(row["garbage_entries_after"])
            self.assertIsNone(row["garbage_entries_removed"])
            self.assertIsNone(row["packs_after"])

            # No maintenance attempt means the aggregate maintenance effect is
            # exactly zero even though no synthetic post-observation is claimed.
            self.assertTrue(result["repository_reclamation_complete"])
            self.assertEqual(result["repository_bytes_reclaimed"], 0)
            self.assertTrue(result["repository_git_reclamation_complete"])
            self.assertEqual(result["repository_garbage_entries_removed"], 0)

    def test_normal_skipped_repo_does_not_synthesize_post_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self.make_store(Path(tmp))
            result = store.prune(target_bytes=0)

            row = result["repository_maintenance"][0]
            self.assertEqual(row["maintenance_status"], "skipped")
            self.assertTrue(row["before_measurement_complete"])
            self.assertFalse(row["after_measurement_complete"])
            self.assertIsInstance(row["bytes_before"], int)
            self.assertIsNone(row["bytes_after"])
            self.assertIsNone(row["bytes_reclaimed"])
            self.assertIsInstance(row["garbage_entries_before"], int)
            self.assertIsNone(row["garbage_entries_after"])
            self.assertIsNone(row["garbage_entries_removed"])
            self.assertIsInstance(row["packs_before"], int)
            self.assertIsNone(row["packs_after"])

            self.assertTrue(result["repository_reclamation_complete"])
            self.assertEqual(result["repository_bytes_reclaimed"], 0)
            self.assertTrue(result["repository_git_reclamation_complete"])
            self.assertEqual(result["repository_garbage_entries_removed"], 0)


if __name__ == "__main__":
    unittest.main()
