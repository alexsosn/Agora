"""Pure-data, no-publication staging of checksum-verified native Text-Fabric ZIPs.

This is a local validation primitive, not an HTTP downloader or a registered
archive-backed corpus resolver. Every caller must supply an expected SHA-256
from an independently reviewed immutable source descriptor.
"""
from __future__ import annotations

import codecs
import hashlib
import os
import re
import stat
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

_FEATURE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.@-]*\.tf\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_REQUIRED = frozenset({"otype.tf", "oslots.tf", "otext.tf"})
_HEADERS = (b"@node\n", b"@edge\n", b"@config\n",
            b"@node\r\n", b"@edge\r\n", b"@config\r\n")
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
             *(f"LPT{i}" for i in range(1, 10))}
_MAX_FEATURE_FILES = 2048


def _safe_members(
    archive: zipfile.ZipFile, *, max_members: int, max_uncompressed_bytes: int
) -> tuple[str, list[zipfile.ZipInfo]]:
    infos = archive.infolist()
    if len(infos) > max_members:
        raise ValueError("TF release archive exceeds member count cap")
    names: set[str] = set()
    roots: dict[str, set[str]] = {}
    declared = 0
    for info in infos:
        name = info.filename
        # Fail rather than normalize POSIX/Windows traversal or filesystem
        # aliases; all members must be safe, even those outside the TF root.
        if (not name or "\\" in name or name.startswith("/")
                or name.startswith("./") or "//" in name
                or len(name) > 512
                or any(c in name for c in ("\0", "\n", "\r"))
                or any(part in (".", "..", "") for part in name.rstrip("/").split("/"))
                or ":" in name.split("/")[0]):
            raise ValueError(f"TF release archive contains unsafe path: {name!r}")
        normalized = name.rstrip("/")
        key = normalized.casefold()
        if key in names:
            raise ValueError(f"TF release archive has duplicate or case-colliding path: {name!r}")
        names.add(key)
        mode = stat.S_IFMT(info.external_attr >> 16)
        if mode == stat.S_IFLNK:
            raise ValueError(f"TF release archive contains a symlink: {name!r}")
        if info.is_dir():
            if mode not in (0, stat.S_IFDIR):
                raise ValueError(f"TF release archive contains invalid directory type: {name!r}")
            continue
        if mode not in (0, stat.S_IFREG):
            raise ValueError(f"TF release archive contains a special file: {name!r}")
        declared += info.file_size
        if declared > max_uncompressed_bytes:
            raise ValueError("TF release archive exceeds declared expanded byte limit")
        root, _, feature = normalized.rpartition("/")
        if feature in ("otype.tf", "oslots.tf"):
            roots.setdefault(root, set()).add(feature)
    complete = [root for root, features in roots.items() if features == {"otype.tf", "oslots.tf"}]
    if len(complete) != 1:
        raise ValueError("TF release archive must contain exactly one paired warp root")
    root = complete[0]
    selected: list[zipfile.ZipInfo] = []
    for info in infos:
        if info.is_dir():
            continue
        name = info.filename
        if root:
            if not name.startswith(root + "/"):
                continue
            leaf = name[len(root) + 1:]
        else:
            leaf = name
        if "/" in leaf or not leaf.endswith(".tf"):
            continue
        if not _FEATURE.fullmatch(leaf) or leaf.split(".")[0].upper() in _RESERVED:
            raise ValueError(f"TF release has a non-portable feature name: {leaf!r}")
        selected.append(info)
        if len(selected) > _MAX_FEATURE_FILES:
            raise ValueError("TF release has too many feature files")
    if not _REQUIRED.issubset({info.filename.rsplit("/", 1)[-1] for info in selected}):
        raise ValueError("TF release archive is missing required warp/config feature files")
    return root, selected


@contextmanager
def staged_verified_tf_zip(
    archive_path: Path,
    *,
    expected_sha256: str,
    staging_parent: Path | None = None,
    max_archive_bytes: int = 512 * 1024 * 1024,
    max_uncompressed_bytes: int = 2 * 1024 * 1024 * 1024,
    max_members: int = 50_000,
) -> Iterator[Path]:
    """Yield temporary validated TF features, then remove *all* staging data.

    No output/cache publication occurs. The input archive is privately copied
    before verification so the ZIP parsed below is exactly the hashed bytes,
    even if the caller's original file is concurrently modified.
    """
    if not isinstance(expected_sha256, str) or not _DIGEST.fullmatch(expected_sha256):
        raise ValueError("expected_sha256 must be a lowercase 64-digit SHA-256")
    if any(not isinstance(n, int) or isinstance(n, bool) or n <= 0 for n in
           (max_archive_bytes, max_uncompressed_bytes, max_members)):
        raise ValueError("release staging limits must be positive integers")
    archive_path = Path(archive_path)
    before = archive_path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("archive input must be a regular non-symlink file")
    if before.st_size > max_archive_bytes:
        raise ValueError("TF release archive exceeds compressed byte limit")
    with tempfile.TemporaryDirectory(prefix="verified-tf-", dir=staging_parent) as work:
        private_archive = Path(work) / "input.zip"
        digest = hashlib.sha256()
        total_archive = 0
        fd = os.open(archive_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as source, private_archive.open("xb") as target:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise ValueError("archive input changed type")
            while part := source.read(1 << 20):
                total_archive += len(part)
                if total_archive > max_archive_bytes:
                    raise ValueError("TF release archive exceeds compressed byte limit")
                digest.update(part)
                target.write(part)
        if digest.hexdigest() != expected_sha256:
            raise ValueError("TF release archive sha256 does not match pinned digest")
        staged = Path(work) / "tf"
        staged.mkdir()
        with zipfile.ZipFile(private_archive) as archive:
            _, selected = _safe_members(
                archive, max_members=max_members,
                max_uncompressed_bytes=max_uncompressed_bytes,
            )
            actual_total = 0
            for info in selected:
                feature_name = info.filename.rsplit("/", 1)[-1]
                decoder = codecs.getincrementaldecoder("utf-8")()
                copied = 0
                first = True
                try:
                    with archive.open(info, "r") as reader, (staged / feature_name).open("xb") as writer:
                        while chunk := reader.read(1 << 20):
                            if first and not chunk.startswith(_HEADERS):
                                raise ValueError(f"TF release feature has invalid TF header: {feature_name}")
                            first = False
                            copied += len(chunk)
                            actual_total += len(chunk)
                            if copied > info.file_size or actual_total > max_uncompressed_bytes:
                                raise ValueError("TF release exceeds actual expanded byte limit")
                            try:
                                decoder.decode(chunk)
                            except UnicodeDecodeError as exc:
                                raise ValueError(f"TF release feature is not UTF-8: {feature_name}") from exc
                            writer.write(chunk)
                        try:
                            decoder.decode(b"", final=True)
                        except UnicodeDecodeError as exc:
                            raise ValueError(f"TF release feature is not UTF-8: {feature_name}") from exc
                except (zipfile.BadZipFile, EOFError) as exc:
                    raise ValueError(f"TF release has corrupt archive member: {feature_name}") from exc
                if first or copied != info.file_size:
                    raise ValueError(f"TF release feature length mismatch: {feature_name}")
        # Reuse the plugin's production portability/required-feature checks.
        from .local_import import LocalImports
        LocalImports._files(staged, "corpus")
        yield staged
