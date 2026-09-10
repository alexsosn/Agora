from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.gitstore import GitStore


@contextmanager
def _uncontended_lock(*_args, **_kwargs):
    yield


class RepositoryStatusReviewRedTests(unittest.TestCase):
    def _store_with_repository(self, root: Path) -> GitStore:
        store = GitStore(
            root / "cache",
            snapshot_soft_limit_bytes=10_000,
            min_free_bytes=0,
        )
        (store.repositories_dir / "fixture").mkdir(parents=True)
        return store

    def _status_for_git_metrics(
        self,
        store: GitStore,
        *,
        packs: int,
        garbage: int,
        garbage_bytes: int,
    ) -> dict:
        metrics = {
            "count": 0,
            "size_bytes": 0,
            "in_pack": 0,
            "packs": packs,
            "size_pack_bytes": 0,
            "prune_packable": 0,
            "garbage": garbage,
            "garbage_bytes": garbage_bytes,
        }
        with (
            patch.object(store, "_repository_lock", side_effect=_uncontended_lock),
            patch.object(store, "_git_count_objects", return_value=metrics),
            patch.object(store, "_directory_size_bounded", return_value=(123, True)),
        ):
            return store.cache_status()

    def test_repository_row_exposes_maintenance_needed_from_documented_trigger(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store_with_repository(Path(tmp))

            healthy = self._status_for_git_metrics(
                store,
                packs=16,
                garbage=0,
                garbage_bytes=0,
            )["repositories"][0]
            garbage = self._status_for_git_metrics(
                store,
                packs=1,
                garbage=1,
                garbage_bytes=1024,
            )["repositories"][0]
            fragmented = self._status_for_git_metrics(
                store,
                packs=17,
                garbage=0,
                garbage_bytes=0,
            )["repositories"][0]

            self.assertIs(healthy["maintenance_needed"], False)
            self.assertIs(garbage["maintenance_needed"], True)
            self.assertIs(fragmented["maintenance_needed"], True)

    def test_repository_size_oserror_is_contained_as_incomplete_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store_with_repository(Path(tmp))
            metrics = {
                "count": 0,
                "size_bytes": 0,
                "in_pack": 0,
                "packs": 3,
                "size_pack_bytes": 4096,
                "prune_packable": 0,
                "garbage": 0,
                "garbage_bytes": 0,
            }
            with (
                patch.object(store, "_repository_lock", side_effect=_uncontended_lock),
                patch.object(store, "_git_count_objects", return_value=metrics),
                patch.object(
                    store,
                    "_directory_size_bounded",
                    side_effect=PermissionError("simulated unreadable repository entry"),
                ),
            ):
                status = store.cache_status()

            row = status["repositories"][0]
            self.assertEqual(row["inspection_status"], "error")
            self.assertIsNone(row["size_bytes"])
            self.assertFalse(row["size_complete"])
            self.assertFalse(status["repository_cache_bytes_complete"])
            self.assertIsNone(status["repository_cache_bytes"])
            self.assertTrue(
                status["repository_git_metrics_complete"],
                "successful Git metrics remain independently complete when only size inspection fails",
            )
            self.assertEqual(status["repository_pack_count"], 3)


if __name__ == "__main__":
    unittest.main()
