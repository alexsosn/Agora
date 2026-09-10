from __future__ import annotations

import multiprocessing
import queue
import tempfile
import time
import unittest
from pathlib import Path

from scripts import agora_managed_artifacts as managed


ARTIFACT_A = "art-" + "d" * 32
ARTIFACT_B = "art-" + "e" * 32


def _method(store, name: str):
    value = getattr(store, name, None)
    if not callable(value):
        raise AssertionError(f"RED3c: ManagedArtifactStore.{name} is missing")
    return value


def _hold(root: str, method_name: str, artifact_id: str, ready, release) -> None:
    store = managed.ManagedArtifactStore(Path(root))
    with _method(store, method_name)(artifact_id, timeout=2.0):
        ready.put(True)
        try:
            release.get(timeout=10.0)
        except queue.Empty:
            pass


class ManagedArtifactUseLeaseRed3cTests(unittest.TestCase):
    def _holder(self, root: Path, method_name: str, artifact_id: str):
        ctx = multiprocessing.get_context("spawn")
        ready = ctx.Queue()
        release = ctx.Queue()
        process = ctx.Process(
            target=_hold,
            args=(str(root), method_name, artifact_id, ready, release),
        )
        process.start()
        self.assertTrue(ready.get(timeout=5.0))
        return process, release

    def _stop(self, process, release) -> None:
        if process.is_alive():
            release.put(True)
            process.join(timeout=5.0)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5.0)
        self.assertEqual(process.exitcode, 0)

    def test_two_shared_use_leases_for_same_artifact_can_coexist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "managed"
            first, first_release = self._holder(root, "use_lease", ARTIFACT_A)
            second = second_release = None
            try:
                second, second_release = self._holder(root, "use_lease", ARTIFACT_A)
            finally:
                if second is not None:
                    self._stop(second, second_release)
                self._stop(first, first_release)

    def test_exclusive_removal_lock_is_bounded_while_use_lease_is_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "managed"
            holder, release = self._holder(root, "use_lease", ARTIFACT_A)
            try:
                store = managed.ManagedArtifactStore(root)
                started = time.monotonic()
                with self.assertRaisesRegex(Exception, r"(?i)lock|timeout|timed|busy|use"):
                    with _method(store, "removal_lock")(ARTIFACT_A, timeout=0.15):
                        self.fail("exclusive removal must not overlap an active use lease")
                self.assertLess(time.monotonic() - started, 1.5)
            finally:
                self._stop(holder, release)

    def test_process_death_releases_use_lease_for_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "managed"
            holder, _release = self._holder(root, "use_lease", ARTIFACT_A)
            holder.terminate()
            holder.join(timeout=5.0)
            self.assertFalse(holder.is_alive())
            store = managed.ManagedArtifactStore(root)
            with _method(store, "removal_lock")(ARTIFACT_A, timeout=1.0):
                pass

    def test_different_artifacts_do_not_share_use_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "managed"
            holder, release = self._holder(root, "removal_lock", ARTIFACT_A)
            try:
                store = managed.ManagedArtifactStore(root)
                with _method(store, "use_lease")(ARTIFACT_B, timeout=0.5):
                    pass
            finally:
                self._stop(holder, release)

    def test_compile_lock_can_be_taken_while_shared_use_lease_is_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "managed"
            store = managed.ManagedArtifactStore(root)
            with _method(store, "use_lease")(ARTIFACT_A, timeout=0.5):
                with store.compile_lock(ARTIFACT_A, timeout=0.5):
                    pass

    def test_use_and_removal_share_one_artifact_id_lock_identity(self):
        names = []
        for suffix in ("one", "two"):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / suffix / "managed"
                store = managed.ManagedArtifactStore(root)
                with _method(store, "use_lease")(ARTIFACT_A, timeout=0.5):
                    pass
                with _method(store, "removal_lock")(ARTIFACT_A, timeout=0.5):
                    pass
                lock_names = sorted(path.name for path in (root / "locks").glob("*.lock"))
                use_names = [name for name in lock_names if name.startswith("use-")]
                self.assertEqual(len(use_names), 1, lock_names)
                names.append(use_names[0])
        self.assertEqual(names[0], names[1])

    def test_invalid_artifact_id_fails_before_use_lock_path_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "managed"
            store = managed.ManagedArtifactStore(root)
            with self.assertRaises((TypeError, ValueError)):
                with _method(store, "use_lease")(str(root / "objects" / ARTIFACT_A), timeout=0.1):
                    pass
            self.assertFalse((root / "locks").exists())


if __name__ == "__main__":
    unittest.main()
