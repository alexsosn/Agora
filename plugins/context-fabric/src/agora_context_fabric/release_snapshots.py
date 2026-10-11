"""Immutable local snapshots for *verified* TF release ZIP payloads.

This module does not download remote data or register corpus identities.
A future trusted catalog resolver must pin the expected release SHA-256, tag,
repository and version before calling install()/prepare().
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path

from .local_import import LocalImports
from .operation import OperationControl, current_operation
from .release_archive import staged_verified_tf_zip

_RECEIPT = ".agora-release.json"
_RESOURCE = re.compile(r"[a-z][a-z0-9._-]{0,63}\Z")
_VERSION = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]{0,99}\Z")
_REPOSITORY = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*/[A-Za-z0-9_-][A-Za-z0-9._-]*\Z")
_TAG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MAX_RECEIPT_BYTES = 1024 * 1024
_MAX_FEATURE_BYTES = 2 * 1024 * 1024 * 1024


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _identity(
    *, resource_id: str, repository: str, release_tag: str,
    version: str, asset_sha256: str,
) -> dict[str, str]:
    if (not isinstance(resource_id, str) or not _RESOURCE.fullmatch(resource_id)
            or resource_id.startswith("local-")
            or resource_id in (".", "..") or ".." in resource_id):
        raise ValueError("invalid stable release resource id")
    if (not isinstance(repository, str) or not _REPOSITORY.fullmatch(repository)
            or repository.split("/")[0] in (".", "..")
            or repository.split("/")[1] in (".", "..")):
        raise ValueError("invalid release source repository")
    if not isinstance(release_tag, str) or not _TAG.fullmatch(release_tag):
        raise ValueError("invalid release tag")
    if not isinstance(version, str) or not _VERSION.fullmatch(version) or ".." in version:
        raise ValueError("invalid corpus version")
    if not isinstance(asset_sha256, str) or not _SHA256.fullmatch(asset_sha256):
        raise ValueError("asset_sha256 must be a pinned lowercase sha256")
    return {
        "resource_id": resource_id,
        "repository": repository,
        "release_tag": release_tag,
        "version": version,
        "asset_sha256": asset_sha256,
    }


class ReleaseSnapshots:
    """Build/reopen canonical-ID corpus snapshots without mutating the catalog."""

    def __init__(self, store):
        self.store = store

    def _destination(self, identity: dict[str, str]) -> Path:
        return (
            self.store.snapshots_dir / identity["resource_id"] /
            identity["asset_sha256"] / "corpora" / "__root__"
        )

    def _assert_managed_destination(self, destination: Path) -> None:
        """Reject symlinked cache ancestors before any mkdir or publication."""
        root = self.store.snapshots_dir
        if root.is_symlink() or root.resolve() != root.absolute():
            raise ValueError("release cache root is a symlink or outside managed cache")
        relative = destination.relative_to(root)
        candidate = root
        for component in relative.parts:
            candidate = candidate / component
            if candidate.is_symlink():
                raise ValueError("release cache path contains a symlink")
        if not destination.resolve().is_relative_to(root):
            raise ValueError("release snapshot path is outside managed cache")

    def _verify_locked(
        self, identity: dict[str, str], *, operation: OperationControl,
    ) -> Path:
        destination = self._destination(identity)
        self._assert_managed_destination(destination)
        if not destination.is_dir() or destination.is_symlink():
            raise FileNotFoundError(
                "pinned release snapshot is not cached; acquire the reviewed asset first"
            )
        receipt_path = destination / _RECEIPT
        if (receipt_path.is_symlink() or not receipt_path.is_file()
                or receipt_path.stat().st_size > _MAX_RECEIPT_BYTES):
            raise ValueError("release receipt integrity mismatch")
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("release receipt integrity mismatch") from exc
        if not isinstance(receipt, dict) or set(receipt) != {
            "schema_version", *identity, "files", "receipt_sha256"
        }:
            raise ValueError("release receipt integrity mismatch")
        seal = receipt.get("receipt_sha256")
        if (receipt.get("schema_version") != 1 or not isinstance(seal, str)
                or _digest({k: v for k, v in receipt.items() if k != "receipt_sha256"}) != seal):
            raise ValueError("release receipt integrity mismatch")
        if any(receipt.get(k) != v for k, v in identity.items()):
            raise ValueError("release snapshot identity mismatch")
        manifest = receipt.get("files")
        if not isinstance(manifest, dict) or not manifest:
            raise ValueError("release receipt integrity mismatch")
        files = LocalImports._files(destination, "corpus")
        expected = set(manifest) | {_RECEIPT}
        actual = {p.name for p in destination.iterdir()}
        # Native Text-Fabric compiles under .tf/; Context-Fabric also
        # materializes its own derived indexes under .cfm/ during a real load.
        # ORACC's published large corpus confirmed .cfm/ is created on first
        # load even though a minimal Pseudepigrapha fixture only made .tf/.
        # Neither directory is a source feature or part of the signed receipt.
        # Permit only these *directories*, never root symlinks, arbitrary
        # new files/directories, or modified/additional original .tf features.
        for name in (".tf", ".cfm"):
            if name in actual:
                compiled = destination / name
                if compiled.is_symlink() or not compiled.is_dir():
                    raise ValueError("release payload integrity mismatch: unsafe compiled cache")
                actual.remove(name)
        if actual != expected:
            raise ValueError("release payload integrity mismatch: unexpected cache files")
        if set(manifest) != {path.name for path in files}:
            raise ValueError("release payload integrity mismatch")
        for path in files:
            entry = manifest[path.name]
            if (not isinstance(entry, dict) or set(entry) != {"bytes", "sha256"}
                    or not isinstance(entry["bytes"], int)
                    or isinstance(entry["bytes"], bool)
                    or entry["bytes"] <= 0
                    or not isinstance(entry["sha256"], str)
                    or not _SHA256.fullmatch(entry["sha256"])):
                raise ValueError("release receipt integrity mismatch")
            h = hashlib.sha256()
            size = 0
            before = path.lstat()
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("release payload integrity mismatch: feature changed type")
            try:
                fd = os.open(
                    path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_NONBLOCK", 0)
                )
                with os.fdopen(fd, "rb") as reader:
                    opened = os.fstat(reader.fileno())
                    if (not stat.S_ISREG(opened.st_mode)
                            or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
                        raise ValueError("release payload integrity mismatch: feature changed")
                    while chunk := reader.read(1 << 20):
                        operation.remaining_acquisition_seconds()
                        h.update(chunk)
                        size += len(chunk)
                    after = os.fstat(reader.fileno())
                    named = path.lstat()
                    if ((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                            != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                            or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)):
                        raise ValueError("release payload integrity mismatch: feature changed")
            except OSError as exc:
                raise ValueError("release payload integrity mismatch: unsafe/changed feature") from exc
            if (size != entry["bytes"] or h.hexdigest() != entry["sha256"]):
                raise ValueError("release payload integrity mismatch")
        self.store.touch_cache_object(destination)
        return destination

    def _verify_and_complete_locked(
        self, identity: dict[str, str], *, operation: OperationControl,
    ) -> Path:
        """Verify immutable release source before touching optional CFM products.

        Caller holds the shared cache transition lock. Both offline prepare()
        and require-fresh reinstall() must obey this same trust boundary.
        """
        path = self._verify_locked(identity, operation=operation)
        from .cfm_compat import complete_empty_compiled_features

        with self.store._repository_lock("cfm-empty-" + identity["resource_id"]):
            complete_empty_compiled_features(
                path, min_free_bytes=self.store.min_free_bytes,
            )
        return path

    @staticmethod
    def _prepared(identity: dict[str, str], path: Path):
        from .resolver import PreparedCorpus

        return PreparedCorpus(
            resource_id=identity["resource_id"],
            member_id=None,
            logical_name=identity["resource_id"],
            relative_path="tf/" + identity["version"],
            path=path,
            version=identity["version"],
            source_revision=identity["asset_sha256"],
        )

    def prepare(
        self, *, resource_id: str, repository: str, release_tag: str,
        version: str, asset_sha256: str, operation: OperationControl | None = None,
    ):
        identity = _identity(
            resource_id=resource_id, repository=repository, release_tag=release_tag,
            version=version, asset_sha256=asset_sha256,
        )
        control = operation or current_operation() or OperationControl()
        control.remaining_acquisition_seconds()
        with self.store.cache_transition():
            path = self._verify_and_complete_locked(identity, operation=control)
        return self._prepared(identity, path)

    def install(
        self, archive_path: Path, *, resource_id: str, repository: str,
        release_tag: str, version: str, asset_sha256: str,
        operation: OperationControl | None = None,
    ):
        identity = _identity(
            resource_id=resource_id, repository=repository, release_tag=release_tag,
            version=version, asset_sha256=asset_sha256,
        )
        control = operation or current_operation() or OperationControl()
        control.stage("acquiring/materializing")
        control.remaining_acquisition_seconds()
        destination = self._destination(identity)
        self._assert_managed_destination(destination)
        # The private-copy + SHA256 check precedes any ZIP member extraction.
        # Both stage and publication occur within managed temporary storage.
        with staged_verified_tf_zip(
            archive_path, expected_sha256=identity["asset_sha256"],
            staging_parent=self.store.tmp_dir,
            max_uncompressed_bytes=_MAX_FEATURE_BYTES,
        ) as staged:
            files = LocalImports._files(staged, "corpus")
            with self.store.cache_transition():
                if destination.exists() or destination.is_symlink():
                    return self._prepared(
                        identity, self._verify_and_complete_locked(identity, operation=control)
                    )
                temporary = Path(tempfile.mkdtemp(prefix="release-import-", dir=self.store.tmp_dir))
                published = False
                try:
                    manifest = {}
                    total = 0
                    for path in files:
                        control.remaining_acquisition_seconds()
                        before = path.lstat()
                        if not stat.S_ISREG(before.st_mode):
                            raise ValueError("release staging file is not regular")
                        digest = hashlib.sha256()
                        size = 0
                        fd = os.open(
                            path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                            | getattr(os, "O_NONBLOCK", 0)
                        )
                        with os.fdopen(fd, "rb") as reader, (temporary / path.name).open("xb") as writer:
                            opened = os.fstat(reader.fileno())
                            if (not stat.S_ISREG(opened.st_mode)
                                    or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
                                raise ValueError("release staging source changed during copy")
                            while chunk := reader.read(1 << 20):
                                control.remaining_acquisition_seconds()
                                size += len(chunk)
                                total += len(chunk)
                                if total > _MAX_FEATURE_BYTES:
                                    raise ValueError("release snapshot exceeds byte limit")
                                if (shutil.disk_usage(temporary).free - len(chunk)
                                        < self.store.min_free_bytes):
                                    raise ValueError("release snapshot violates free-space reserve")
                                digest.update(chunk)
                                writer.write(chunk)
                            after = os.fstat(reader.fileno())
                            if (size != after.st_size or before.st_size != after.st_size
                                    or opened.st_mtime_ns != after.st_mtime_ns):
                                raise ValueError("release staging source changed during copy")
                        manifest[path.name] = {"bytes": size, "sha256": digest.hexdigest()}
                    receipt = {
                        "schema_version": 1, **identity, "files": manifest,
                    }
                    receipt["receipt_sha256"] = _digest(receipt)
                    (temporary / _RECEIPT).write_text(
                        json.dumps(receipt, sort_keys=True), encoding="utf-8"
                    )
                    # Check again while holding the cache transition lock:
                    # no cache ancestor may be redirected to an external path.
                    self._assert_managed_destination(destination)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    self._assert_managed_destination(destination)
                    control.remaining_acquisition_seconds()
                    temporary.rename(destination)
                    published = True
                    try:
                        self.store.touch_cache_object(destination)
                    except Exception:
                        for sidecar in (
                            self.store._access_path(destination),
                            self.store._meta_path(destination),
                        ):
                            sidecar.unlink(missing_ok=True)
                        shutil.rmtree(destination, ignore_errors=True)
                        self.store._cleanup_empty_parents(destination)
                        raise
                    return self._prepared(identity, destination)
                finally:
                    if not published:
                        shutil.rmtree(temporary, ignore_errors=True)
