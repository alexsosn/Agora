from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# Keep the mature cache lifecycle implementation byte-for-byte isolated while
# extending its public GitStore surface with the cold-compile lock. Re-export
# public core names so existing imports (GIB, CacheLease, etc.) stay compatible.
from ._gitstore_core import *  # noqa: F401,F403
from ._gitstore_core import GitStore as _CoreGitStore


class GitStore(_CoreGitStore):
    """Context-Fabric cache store with an exact-object cold-compile lock."""

    @contextmanager
    def compile_lock(self, path: Path, timeout: float = 0.25) -> Iterator[None]:
        """Serialize cold compilation for one exact managed cache object.

        This lock is deliberately separate from the cache object's shared lease:
        the lease prevents eviction while a load is active, whereas this
        exclusive OS-backed lock prevents two Agora processes from compiling the
        same prepared object concurrently. Lock files live outside the managed
        object so cleanup/pruning cannot remove the synchronization primitive.
        """

        candidate = self._managed_path(path)
        lock_path = self.locks_dir / "compile" / f"{self._object_id(candidate)}.lock"
        lock = self._acquire_file_lock(
            lock_path,
            shared=False,
            timeout=timeout,
            description="Context-Fabric cold-compile lock",
        )
        try:
            yield
        finally:
            lock.release()
