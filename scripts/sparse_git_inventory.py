"""Verify a pinned sparse Git worktree without downloading excluded blobs.

The legacy `git ls-tree --long` queries sizes of every tracked blob.
On a promisor/partial clone this may lazily hydrate *unselected* objects.
Use tree object IDs only and verify selected working-tree bytes locally.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
from pathlib import Path

_TT = re.compile(r"[^/]+/[^/]+_TT(?:/.*|\.zip)\Z")


def _tracked_tt_blobs(root: Path) -> dict[str, tuple[str, str]]:
    env = {**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"}
    raw = subprocess.check_output(
        ["git", "-C", str(root), "ls-tree", "-r", "-z", "HEAD"],
        env=env, timeout=120,
    )
    selected: dict[str, tuple[str, str]] = {}
    for record in raw.split(b"\x00"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        name = raw_path.decode("utf-8")
        if _TT.fullmatch(name):
            if kind != "blob" or mode not in {"100644", "100755"}:
                raise ValueError(f"selected TT entry is not a regular Git blob: {name}")
            if len(oid) not in (40, 64):
                raise ValueError(f"invalid selected Git blob ID for {name}")
            selected[name] = (oid, mode)
    return selected


def _hash_git_blob(file: Path, *, size: int, digest_len: int) -> str:
    h = hashlib.sha256() if digest_len == 64 else hashlib.sha1()
    h.update(f"blob {size}\0".encode("ascii"))
    with file.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def verify_selected_sparse_inventory(
    repository: Path, *, expected_count: int, expected_bytes: int,
) -> tuple[int, int]:
    """Verify included TT filenames/content at pinned HEAD; never lazy-fetch."""
    root = repository.resolve()
    selected = _tracked_tt_blobs(root)
    if len(selected) != expected_count:
        raise ValueError(
            f"pinned TT Git tree count mismatch: expected {expected_count}, got {len(selected)}"
        )
    total = 0
    for relative, (oid, _) in selected.items():
        source = root / relative
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"pinned TT file absent or symlinked: {relative}")
        if not source.resolve().is_relative_to(root):
            raise ValueError(f"pinned TT file escaped checkout: {relative}")
        st = source.stat()
        if not stat.S_ISREG(st.st_mode):
            raise ValueError(f"pinned TT entry is not a regular file: {relative}")
        total += st.st_size
        if _hash_git_blob(source, size=st.st_size, digest_len=len(oid)) != oid:
            raise ValueError(f"pinned TT Git blob mismatch: {relative}")
    if total != expected_bytes:
        raise ValueError(
            f"pinned TT content size mismatch: expected {expected_bytes}, got {total}"
        )
    actual = {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if ".git" not in p.relative_to(root).parts and (p.is_file() or p.is_symlink())
    }
    if actual != selected.keys():
        extra = actual - selected.keys()
        missing = selected.keys() - actual
        raise ValueError(
            f"sparse checkout contains unwanted or missing paths: "
            f"extra={sorted(extra)[:10]!r}, missing={sorted(missing)[:10]!r}"
        )
    return len(selected), total
