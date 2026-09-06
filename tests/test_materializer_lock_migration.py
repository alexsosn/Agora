from __future__ import annotations

import multiprocessing
import os
import tempfile
import time
import unittest
from pathlib import Path

from scripts.agora_install_materializer import MaterializerInstallError, _lock


def _hold_legacy_lock(path: str, ready, release) -> None:
    """Emulate the pre-#62 sentinel protocol exactly enough for interoperability tests."""
    lock_path = Path(path)
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        ready.set()
        release.wait(10)
    finally:
        os.close(fd)
        lock_path.unlink(missing_ok=True)


def _hold_legacy_lock_briefly(path: str, ready, hold_seconds: float) -> None:
    lock_path = Path(path)
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        ready.set()
        time.sleep(hold_seconds)
    finally:
        os.close(fd)
        lock_path.unlink(missing_ok=True)


def _crash_holding_current_lock(path: str, ready) -> None:
    with _lock(Path(path), timeout=5):
        ready.set()
        os._exit(0)


class MaterializerLockMigrationTests(unittest.TestCase):
    def test_live_pre62_holder_blocks_current_installer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".source.lock"
            ctx = multiprocessing.get_context("spawn")
            ready, release = ctx.Event(), ctx.Event()
            holder = ctx.Process(target=_hold_legacy_lock, args=(str(path), ready, release))
            holder.start()
            try:
                self.assertTrue(ready.wait(10))
                with self.assertRaisesRegex(MaterializerInstallError, "legacy|pre-migration"):
                    with _lock(path, timeout=0.15):
                        pass
            finally:
                release.set()
                holder.join(10)
            self.assertEqual(holder.exitcode, 0)

    def test_current_waits_for_brief_pre62_holder_then_enters(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".source.lock"
            ctx = multiprocessing.get_context("spawn")
            ready = ctx.Event()
            holder = ctx.Process(target=_hold_legacy_lock_briefly, args=(str(path), ready, 0.8))
            holder.start()
            try:
                self.assertTrue(ready.wait(10))
                started = time.monotonic()
                with _lock(path, timeout=5):
                    waited = time.monotonic() - started
            finally:
                holder.join(10)
            self.assertEqual(holder.exitcode, 0)
            self.assertGreater(waited, 0.2, "current installer ignored the legacy sentinel")

    def test_current_holder_excludes_pre62_o_excl_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".environment.lock"
            with _lock(path, timeout=1):
                with self.assertRaises(FileExistsError):
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    os.close(fd)

    def test_clean_current_release_removes_legacy_visible_sentinel(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".source.lock"
            with _lock(path, timeout=1):
                self.assertTrue(path.exists())
            self.assertFalse(path.exists(), "clean current runs must not wedge older installers")

    def test_current_crash_residue_is_self_identifying_and_recoverable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".source.lock"
            ctx = multiprocessing.get_context("spawn")
            ready = ctx.Event()
            crashed = ctx.Process(target=_crash_holding_current_lock, args=(str(path), ready))
            crashed.start()
            self.assertTrue(ready.wait(10))
            crashed.join(10)
            self.assertEqual(crashed.exitcode, 0)

            self.assertTrue(path.exists())
            self.assertTrue(
                path.read_text(encoding="utf-8").startswith("agora-materializer-lock-"),
                "current crash residue must be distinguishable from an empty legacy sentinel",
            )
            with _lock(path, timeout=1):
                pass
            self.assertFalse(path.exists())

    def test_ambiguous_empty_legacy_sentinel_fails_closed_and_is_not_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".source.lock"
            path.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(MaterializerInstallError, "legacy|pre-migration"):
                with _lock(path, timeout=0.15):
                    pass
            self.assertTrue(path.exists(), "ambiguous legacy state must never be auto-deleted")


if __name__ == "__main__":
    unittest.main()
