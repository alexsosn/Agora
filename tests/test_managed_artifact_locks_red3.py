from __future__ import annotations

import multiprocessing
import queue
import tempfile
import time
import unittest
from pathlib import Path

from scripts import agora_managed_artifacts as managed


REQUEST_KEY = "a" * 64
ARTIFACT_A = "art-" + "b" * 32
ARTIFACT_B = "art-" + "c" * 32


def _lock_method(store, name: str):
    method = getattr(store, name, None)
    if not callable(method):
        raise AssertionError(f"RED3: ManagedArtifactStore.{name} is missing")
    return method


def _hold_lock(root: str, method_name: str, identity: str, ready, release) -> None:
    store = managed.ManagedArtifactStore(Path(root))
    method = _lock_method(store, method_name)
    with method(identity, timeout=2.0):
        ready.put(True)
        try:
            release.get(timeout=10.0)
        except queue.Empty:
            pass


class ManagedArtifactLockRed3Tests(unittest.TestCase):
    def _start_holder(self, root: Path, method_name: str, identity: str):
        ctx = multiprocessing.get_context("spawn")
        ready = ctx.Queue()
        release = ctx.Queue()
        process = ctx.Process(
            target=_hold_lock,
            args=(str(root), method_name, identity, ready, release),
        )
        process.start()
        self.assertTrue(ready.get(timeout=5.0))
        return process, release

    def test_publication_lock_is_cross_process_and_timeout_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "managed"
            process, release = self._start_holder(root, "publication_lock", REQUEST_KEY)
            try:
                store = managed.ManagedArtifactStore(root)
                started = time.monotonic()
                with self.assertRaisesRegex(Exception, r"(?i)lock|timeout|timed|busy"):
                    with _lock_method(store, "publication_lock")(REQUEST_KEY, timeout=0.15):
                        self.fail("same request-key publication lock must not be acquired twice")
                self.assertLess(time.monotonic() - started, 1.5)
            finally:
                release.put(True)
                process.join(timeout=5.0)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5.0)
                self.assertEqual(process.exitcode, 0)

    def test_compile_lock_is_keyed_by_artifact_id_and_different_ids_do_not_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "managed"
            process, release = self._start_holder(root, "compile_lock", ARTIFACT_A)
            try:
                store = managed.ManagedArtifactStore(root)
                started = time.monotonic()
                with _lock_method(store, "compile_lock")(ARTIFACT_B, timeout=0.5):
                    pass
                self.assertLess(time.monotonic() - started, 1.5)
                with self.assertRaisesRegex(Exception, r"(?i)lock|timeout|timed|busy"):
                    with _lock_method(store, "compile_lock")(ARTIFACT_A, timeout=0.15):
                        self.fail("same artifact compile lock must be exclusive")
            finally:
                release.put(True)
                process.join(timeout=5.0)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5.0)
                self.assertEqual(process.exitcode, 0)

    def test_process_death_releases_compile_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "managed"
            process, _release = self._start_holder(root, "compile_lock", ARTIFACT_A)
            process.terminate()
            process.join(timeout=5.0)
            self.assertFalse(process.is_alive())

            store = managed.ManagedArtifactStore(root)
            with _lock_method(store, "compile_lock")(ARTIFACT_A, timeout=1.0):
                pass

    def test_lock_namespaces_are_stable_across_store_root_relocation(self):
        names = []
        for suffix in ("one", "two"):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / suffix / "managed"
                store = managed.ManagedArtifactStore(root)
                with _lock_method(store, "publication_lock")(REQUEST_KEY, timeout=0.5):
                    pass
                with _lock_method(store, "compile_lock")(ARTIFACT_A, timeout=0.5):
                    pass
                lock_names = sorted(path.name for path in (root / "locks").glob("*.lock"))
                self.assertEqual(len(lock_names), 2, lock_names)
                names.append(lock_names)
        self.assertEqual(names[0], names[1])
        self.assertNotEqual(names[0][0], names[0][1])

    def test_compile_lock_rejects_caller_path_spellings_before_lock_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "managed"
            store = managed.ManagedArtifactStore(root)
            with self.assertRaises((TypeError, ValueError)):
                with _lock_method(store, "compile_lock")(str(root / "objects" / ARTIFACT_A), timeout=0.1):
                    pass
            self.assertFalse((root / "locks").exists())

    def test_publication_lock_requires_canonical_request_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "managed"
            store = managed.ManagedArtifactStore(root)
            with self.assertRaises((TypeError, ValueError)):
                with _lock_method(store, "publication_lock")("../not-a-request-key", timeout=0.1):
                    pass
            self.assertFalse((root / "locks").exists())


if __name__ == "__main__":
    unittest.main()
