from __future__ import annotations

import multiprocessing
import os
import tempfile
import time
import unittest
from pathlib import Path

import portalocker

from scripts.agora_install_materializer import (
    LOCK_PROTOCOL_MARKER,
    MaterializerInstallError,
    _lock,
)


def _hold_pre62_lock(path: str, ready, release) -> None:
    """Emulate the pre-#62 sentinel protocol."""
    lock_path = Path(path)
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        ready.set()
        release.wait(10)
    finally:
        os.close(fd)
        lock_path.unlink(missing_ok=True)


def _hold_pre62_lock_briefly(path: str, ready, hold_seconds: float) -> None:
    lock_path = Path(path)
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        ready.set()
        time.sleep(hold_seconds)
    finally:
        os.close(fd)
        lock_path.unlink(missing_ok=True)


def _post62_lock(path: str, *, timeout: float) -> portalocker.Lock:
    """Construct the advisory-only lock protocol introduced by #62."""
    return portalocker.Lock(
        path,
        mode="a",
        timeout=timeout,
        check_interval=0.05,
        flags=portalocker.LockFlags.EXCLUSIVE | portalocker.LockFlags.NON_BLOCKING,
    )


def _hold_post62_lock(path: str, ready, release) -> None:
    lock = _post62_lock(path, timeout=5)
    lock.acquire()
    try:
        ready.set()
        release.wait(10)
    finally:
        lock.release()


def _attempt_post62_lock(path: str, result) -> None:
    lock = _post62_lock(path, timeout=0.2)
    try:
        lock.acquire()
    except portalocker.exceptions.AlreadyLocked:
        result.put("blocked")
    else:
        result.put("acquired")
        lock.release()


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
            holder = ctx.Process(target=_hold_pre62_lock, args=(str(path), ready, release))
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
            holder = ctx.Process(target=_hold_pre62_lock_briefly, args=(str(path), ready, 0.8))
            holder.start()
            try:
                self.assertTrue(ready.wait(10))
                started = time.monotonic()
                with _lock(path, timeout=5):
                    waited = time.monotonic() - started
            finally:
                holder.join(10)
            self.assertEqual(holder.exitcode, 0)
            self.assertGreater(waited, 0.2, "current installer ignored the pre-#62 sentinel")

    def test_current_holder_excludes_pre62_o_excl_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".environment.lock"
            with _lock(path, timeout=1):
                with self.assertRaises(FileExistsError):
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    os.close(fd)

    def test_live_post62_holder_blocks_current_installer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".source.lock"
            ctx = multiprocessing.get_context("spawn")
            ready, release = ctx.Event(), ctx.Event()
            holder = ctx.Process(target=_hold_post62_lock, args=(str(path), ready, release))
            holder.start()
            try:
                self.assertTrue(ready.wait(10))
                with self.assertRaises(MaterializerInstallError):
                    with _lock(path, timeout=0.15):
                        pass
            finally:
                release.set()
                holder.join(10)
            self.assertEqual(holder.exitcode, 0)

    def test_current_holder_excludes_post62_advisory_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".environment.lock"
            ctx = multiprocessing.get_context("spawn")
            result = ctx.Queue()
            with _lock(path, timeout=1):
                contender = ctx.Process(target=_attempt_post62_lock, args=(str(path), result))
                contender.start()
                contender.join(10)
                self.assertEqual(contender.exitcode, 0)
                self.assertEqual(result.get(timeout=2), "blocked")

    def test_marked_current_residue_is_not_recovered_through_live_post62_holder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".source.lock"
            path.write_text(LOCK_PROTOCOL_MARKER, encoding="ascii")
            ctx = multiprocessing.get_context("spawn")
            ready, release = ctx.Event(), ctx.Event()
            holder = ctx.Process(target=_hold_post62_lock, args=(str(path), ready, release))
            holder.start()
            try:
                self.assertTrue(ready.wait(10))
                with self.assertRaises(MaterializerInstallError):
                    with _lock(path, timeout=0.15):
                        pass
                self.assertTrue(path.exists())
            finally:
                release.set()
                holder.join(10)
            self.assertEqual(holder.exitcode, 0)

            with _lock(path, timeout=1):
                pass
            self.assertFalse(path.exists())

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
            self.assertEqual(path.read_text(encoding="ascii"), LOCK_PROTOCOL_MARKER)
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
