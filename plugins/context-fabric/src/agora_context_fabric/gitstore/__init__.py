from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import _core as _core_module

# Preserve the historical gitstore module surface after converting it into a
# package. This keeps existing imports and patch targets compatible while the
# exact-object compile lock remains a small extension around the mature cache
# lifecycle implementation in _core.py.
for _name, _value in vars(_core_module).items():
    if _name == "GitStore" or _name.startswith("__"):
        continue
    globals().setdefault(_name, _value)

_CoreGitStore = _core_module.GitStore


class GitStore(_CoreGitStore):
    """Context-Fabric cache store with an exact-object cold-compile lock."""

    @contextmanager
    def compile_lock(self, path: Path, timeout: float = 0.25) -> Iterator[None]:
        """Serialize cold compilation for one exact managed cache object.

        The shared cache lease prevents eviction while a load is active. This
        separate exclusive OS-backed lock prevents two Agora processes from
        compiling the same prepared object concurrently.
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


del _name, _value
