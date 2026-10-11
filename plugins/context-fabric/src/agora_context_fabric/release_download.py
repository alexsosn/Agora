"""Restricted, transient acquisition of checksum-pinned GitHub Release ZIPs.

No discovery or persistent cache publication. Caller-supplied identities must
come from reviewed canonical metadata; this downloader only enforces transport,
resource budgets, checksum and temporary-file ownership.
"""
from __future__ import annotations

import hashlib
import math
import re
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .operation import OperationControl, current_operation

_OWNER = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}\Z")
_REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z")
_TAG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z")
_ASSET = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.zip\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_TRUSTED_HOSTS = frozenset({
    "github.com",
    "release-assets.githubusercontent.com",
})
_MAX_TRANSFER = 512 * 1024 * 1024
_SOCKET_TIMEOUT_SECONDS = 30.0
_MAX_TRANSFER_SECONDS = 600.0


def _approved_https(url: str) -> None:
    if not isinstance(url, str) or any(ord(c) < 33 or ord(c) == 127 for c in url):
        raise ValueError("release redirect URL contains unsafe characters")
    parsed = urlsplit(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("release redirect has invalid port") from exc
    if (parsed.scheme != "https" or parsed.hostname not in _TRUSTED_HOSTS
            or port not in (None, 443)
            or parsed.username is not None or parsed.password is not None
            or parsed.fragment or not parsed.path.startswith("/")
            or not parsed.netloc):
        raise ValueError("release redirect must stay within approved HTTPS GitHub asset hosts")


class SafeReleaseRedirect(HTTPRedirectHandler):
    """Reject unapproved intermediates before urllib performs the request."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _approved_https(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _url(*, repository: str, release_tag: str, asset_name: str) -> str:
    if not isinstance(repository, str) or repository.count("/") != 1:
        raise ValueError("release repository must be owner/name")
    owner, name = repository.split("/")
    if (not _OWNER.fullmatch(owner) or not _REPO.fullmatch(name)
            or name in (".", "..") or ".." in name):
        raise ValueError("invalid GitHub release repository")
    if (not isinstance(release_tag, str) or not _TAG.fullmatch(release_tag)
            or release_tag.casefold() == "latest" or ".." in release_tag):
        raise ValueError("release tag must be explicitly pinned")
    if (not isinstance(asset_name, str) or not _ASSET.fullmatch(asset_name)
            or ".." in asset_name):
        raise ValueError("invalid GitHub release ZIP asset")
    return (
        f"https://github.com/{owner}/{name}/releases/download/"
        f"{release_tag}/{asset_name}"
    )


@contextmanager
def download_pinned_release(
    *, repository: str, release_tag: str, asset_name: str,
    asset_sha256: str, asset_bytes: int, temporary_parent: Path,
    opener=None, operation: OperationControl | None = None,
    max_download_bytes: int = _MAX_TRANSFER,
    max_seconds: float = _MAX_TRANSFER_SECONDS,
):
    """Yield one verified downloaded ZIP, then destroy its temporary bytes."""
    url = _url(
        repository=repository, release_tag=release_tag, asset_name=asset_name
    )
    if not isinstance(asset_sha256, str) or not _DIGEST.fullmatch(asset_sha256):
        raise ValueError("asset_sha256 must be 64 lowercase SHA256 hex characters")
    if (not isinstance(asset_bytes, int) or isinstance(asset_bytes, bool)
            or asset_bytes <= 0):
        raise ValueError("asset_bytes must be a positive integer")
    if (not isinstance(max_download_bytes, int)
            or isinstance(max_download_bytes, bool)
            or max_download_bytes <= 0 or max_download_bytes > _MAX_TRANSFER
            or asset_bytes > max_download_bytes):
        raise ValueError("release asset exceeds configured download byte cap")
    if (not isinstance(max_seconds, (int, float)) or isinstance(max_seconds, bool)
            or not math.isfinite(max_seconds) or max_seconds <= 0
            or max_seconds > _MAX_TRANSFER_SECONDS):
        raise ValueError("invalid release download deadline")
    control = operation or current_operation() or OperationControl()
    control.stage("acquiring/materializing")
    control.remaining_acquisition_seconds()
    parent = Path(temporary_parent).expanduser().absolute()
    if parent.is_symlink() or not parent.is_dir():
        raise ValueError("release download requires a private non-symlink temp directory")
    transport = opener if opener is not None else build_opener(SafeReleaseRedirect())
    deadline = time.monotonic() + float(max_seconds)
    with tempfile.TemporaryDirectory(prefix="verified-release-", dir=parent) as work:
        archive_path = Path(work) / "asset.zip"
        request = Request(url, method="GET")
        digest = hashlib.sha256()
        count = 0
        try:
            with transport.open(request, timeout=_SOCKET_TIMEOUT_SECONDS) as response:
                final_url = response.geturl() if hasattr(response, "geturl") else response.url
                _approved_https(final_url)
                with archive_path.open("xb") as output:
                    while True:
                        control.remaining_acquisition_seconds()
                        if time.monotonic() > deadline:
                            raise TimeoutError("pinned release download exceeded cumulative deadline")
                        block = response.read(1 << 20)
                        control.remaining_acquisition_seconds()
                        if time.monotonic() > deadline:
                            raise TimeoutError("pinned release download exceeded cumulative deadline")
                        if not block:
                            break
                        count += len(block)
                        if count > max_download_bytes or count > asset_bytes:
                            raise ValueError("pinned release transfer exceeds approved byte length")
                        if shutil.disk_usage(work).free - len(block) < 0:
                            raise ValueError("pinned release has insufficient free disk space")
                        digest.update(block)
                        output.write(block)
        except TimeoutError:
            # An elapsed cumulative budget is a control-plane error, not a
            # retriable transient network failure.
            raise
        except (OSError, EOFError) as exc:
            raise RuntimeError("verified GitHub release download failed") from exc
        if count != asset_bytes:
            raise ValueError("pinned release compressed byte count mismatch")
        if digest.hexdigest() != asset_sha256:
            raise ValueError("pinned release sha256 mismatch")
        yield archive_path
