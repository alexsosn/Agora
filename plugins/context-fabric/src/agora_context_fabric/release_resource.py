"""Immutable GitHub Release ZIP -> managed, verifiable Context-Fabric corpus snapshot.

Only native TF feature *data* are published. App files, executable code and
upstream release documentation remain at the upstream immutable source; they
are never executed or extracted into the Agora cache.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

from .local_import import LocalImports
from .operation import OperationControl, current_operation
from .release_archive import staged_verified_tf_zip
from .resolver import PreparedCorpus

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_ALLOWED_HOSTS = frozenset({
    "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com",
})
_RECEIPT = ".agora-release.json"


class _PinnedReleaseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if (parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS
                or parsed.username is not None or parsed.password is not None
                or parsed.port not in (None, 443)):
            raise ValueError("GitHub Release redirect is not trusted HTTPS")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download_release(url: str, destination: Path, *, max_bytes: int) -> None:
    """Download exactly one pinned asset, bounded by bytes and request deadline."""
    if urlsplit(url).scheme != "https" or urlsplit(url).hostname != "github.com":
        raise ValueError("release acquisition requires the canonical HTTPS GitHub URL")
    operation = current_operation() or OperationControl()
    opener = urllib.request.build_opener(_PinnedReleaseRedirect())
    request = urllib.request.Request(url, headers={"User-Agent": "Agora-ContextFabric/1"})
    total = 0
    with opener.open(request, timeout=min(30.0, operation.remaining_acquisition_seconds())) as reader:
        length = reader.headers.get("Content-Length")
        if length is not None and int(length) > max_bytes:
            raise ValueError("GitHub Release asset exceeds pinned byte limit")
        with destination.open("xb") as writer:
            while True:
                operation.remaining_acquisition_seconds()
                part = reader.read(min(1 << 20, max_bytes - total + 1))
                if not part:
                    break
                total += len(part)
                if total > max_bytes:
                    raise ValueError("GitHub Release asset exceeds pinned byte limit")
                writer.write(part)
    if total != max_bytes:
        raise ValueError("GitHub Release asset length differs from pinned release metadata")


class ReleaseArchiveAcquirer:
    def __init__(self, store, *, download=None):
        self.store = store
        self.download = download or _download_release

    @staticmethod
    def _validated_release(resource):
        if resource.kind != "corpus" or resource.acquisition_strategy != "github-release-archive":
            raise ValueError("release acquisition requires a registered archive corpus")
        release = resource.release
        required = {"tag", "asset", "sha256", "bytes", "dataset", "release_id", "tf_version"}
        if not isinstance(release, dict) or set(release) != required:
            raise ValueError("release descriptor must contain exact pinned identity fields")
        for name in ("tag", "asset", "dataset", "release_id", "tf_version"):
            if not isinstance(release[name], str) or not _TOKEN.fullmatch(release[name]):
                raise ValueError(f"release {name} must be a fixed portable token")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", resource.repository):
            raise ValueError("release requires a canonical owner/repository")
        if not release["asset"].endswith(".zip"):
            raise ValueError("release asset must name a pinned ZIP")
        if not isinstance(resource.ref, str) or not _COMMIT.fullmatch(resource.ref):
            raise ValueError("release upstream.ref must be a 40-hex immutable commit")
        if not isinstance(release["sha256"], str) or not _SHA256.fullmatch(release["sha256"]):
            raise ValueError("release sha256 must be a fixed lowercase digest")
        if (not isinstance(release["bytes"], int) or isinstance(release["bytes"], bool)
                or not 0 < release["bytes"] <= 512 * 1024 * 1024):
            raise ValueError("release bytes must be a bounded positive size")
        if resource.tf_path != "tf/" + release["tf_version"]:
            raise ValueError("release TF version/path descriptor mismatch")
        return release

    @staticmethod
    def _manifest(archive: Path, release: dict) -> dict:
        # The existing staged_verified_tf_zip primitive has already hashed the
        # private archive and validated every archive path and TF feature.
        with zipfile.ZipFile(archive) as z:
            if "manifest.json" not in z.namelist() or z.getinfo("manifest.json").file_size > 65536:
                raise ValueError("release manifest is absent or oversized")
            try:
                manifest = json.loads(z.read("manifest.json").decode("utf-8"))
            except (UnicodeError, ValueError, zipfile.BadZipFile) as exc:
                raise ValueError("invalid release manifest") from exc
            if not isinstance(manifest, dict):
                raise ValueError("invalid release manifest object")
            expected = {
                "dataset": release["dataset"],
                "release_id": release["release_id"],
                "tf_version": release["tf_version"],
                "tf_root": "tf/" + release["tf_version"],
            }
            if any(manifest.get(key) != value for key, value in expected.items()):
                raise ValueError("release manifest dataset/version/TF-root identity mismatch")
            if not (manifest["tf_root"] + "/otype.tf" in z.namelist()
                    and manifest["tf_root"] + "/oslots.tf" in z.namelist()):
                raise ValueError("release manifest does not identify the native TF warp root")
            commit = manifest.get("builder_commit")
            source = manifest.get("source_state")
            if (not isinstance(commit, str) or not _COMMIT.fullmatch(commit)
                    or not isinstance(source, str)
                    or not re.fullmatch(r"sha256:[0-9a-f]{64}", source)):
                raise ValueError("release manifest lacks immutable builder/source provenance")
            return {key: manifest[key] for key in (
                "dataset", "release_id", "tf_version", "tf_root",
                "builder_commit", "source_state",
            )}

    def _verify_cached(self, destination: Path, resource, release: dict) -> None:
        if destination.is_symlink() or not destination.is_dir():
            raise ValueError("release cache integrity failure: invalid snapshot directory")
        try:
            receipt = json.loads((destination / _RECEIPT).read_text(encoding="utf-8"))
            expected = {
                "resource_id": resource.id, "repository": resource.repository,
                "commit": resource.ref, "release": release,
            }
            if not isinstance(receipt, dict) or any(receipt.get(k) != v for k, v in expected.items()):
                raise ValueError("invalid receipt identity")
            files = LocalImports._files(destination, "corpus")
            if {f.name for f in files} != set(receipt["files"]):
                raise ValueError("cached feature set changed")
            op = current_operation() or OperationControl()
            for feature in files:
                digest = hashlib.sha256()
                size = 0
                with feature.open("rb") as source:
                    while chunk := source.read(1 << 20):
                        op.remaining_acquisition_seconds()
                        size += len(chunk)
                        digest.update(chunk)
                if {"bytes": size, "sha256": digest.hexdigest()} != receipt["files"][feature.name]:
                    raise ValueError("cached feature bytes changed")
        except (OSError, TypeError, KeyError, ValueError) as exc:
            raise ValueError("release cache integrity failure: do not load altered cached data") from exc
        self.store.touch_cache_object(destination)

    def prepare(self, resource, *, version=None, source_revision=None) -> PreparedCorpus:
        release = self._validated_release(resource)
        revision = release["sha256"]
        if version is not None and version != release["tf_version"]:
            raise ValueError("release corpus version differs from the pinned version")
        if source_revision is not None and source_revision != revision:
            raise ValueError("release source_revision must equal the pinned asset SHA-256 revision")
        destination = (self.store.snapshots_dir / self.store.safe_cache_key(resource.id)
                       / revision / "corpora" / "__root__")
        policy = self.store.current_source_policy()
        mode = policy.mode if policy is not None else "prefer-fresh"
        url = (f"https://github.com/{resource.repository}/releases/download/"
               f"{release['tag']}/{release['asset']}")
        operation = current_operation() or OperationControl()
        with self.store._repository_lock("release-" + resource.id):
            exists = destination.exists() or destination.is_symlink()
            if exists:
                self._verify_cached(destination, resource, release)
            if not exists and mode == "offline":
                raise ValueError("offline: pinned GitHub Release snapshot is not cached")
            if not exists or mode == "require-fresh":
                with tempfile.TemporaryDirectory(prefix="release-download-", dir=self.store.tmp_dir) as d:
                    tmp = Path(d)
                    downloaded = tmp / "input.zip"
                    self.download(url, downloaded, max_bytes=release["bytes"])
                    if downloaded.stat().st_size != release["bytes"]:
                        raise ValueError("release asset size does not match pinned metadata")
                    with staged_verified_tf_zip(
                        downloaded, expected_sha256=revision, staging_parent=tmp,
                        max_archive_bytes=release["bytes"],
                    ) as staged:
                        manifest = self._manifest(downloaded, release)
                        if not exists:
                            staging = Path(tempfile.mkdtemp(prefix="release-snapshot-", dir=self.store.tmp_dir))
                            published = False
                            try:
                                details = {}
                                for source in LocalImports._files(staged, "corpus"):
                                    digest = hashlib.sha256()
                                    size = 0
                                    with source.open("rb") as inp, (staging / source.name).open("xb") as out:
                                        while chunk := inp.read(1 << 20):
                                            operation.remaining_acquisition_seconds()
                                            if shutil.disk_usage(staging).free - len(chunk) < self.store.min_free_bytes:
                                                raise ValueError("release snapshot would violate disk free-space reserve")
                                            digest.update(chunk)
                                            size += len(chunk)
                                            out.write(chunk)
                                    details[source.name] = {"bytes": size, "sha256": digest.hexdigest()}
                                receipt = {
                                    "resource_id": resource.id, "repository": resource.repository,
                                    "commit": resource.ref, "release": release, "manifest": manifest,
                                    "files": details,
                                }
                                (staging / _RECEIPT).write_text(
                                    json.dumps(receipt, sort_keys=True), encoding="utf-8"
                                )
                                destination.parent.mkdir(parents=True, exist_ok=True)
                                if destination.exists() or destination.is_symlink():
                                    raise ValueError("release snapshot destination already exists")
                                staging.rename(destination)
                                published = True
                                try:
                                    self.store.touch_cache_object(destination)
                                except Exception:
                                    shutil.rmtree(destination)
                                    self.store._cleanup_empty_parents(destination)
                                    raise
                            finally:
                                if not published or staging.exists():
                                    shutil.rmtree(staging, ignore_errors=True)
        return PreparedCorpus(
            resource_id=resource.id, member_id=None, logical_name=resource.id,
            relative_path="tf/" + release["tf_version"], path=destination,
            version=release["tf_version"], source_revision=revision,
        )
