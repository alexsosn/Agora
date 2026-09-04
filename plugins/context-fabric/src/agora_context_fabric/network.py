from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .gitstore import GitStore


NETWORK_MODES = frozenset({"auto", "offline", "require-fresh"})
_IMMUTABLE_REVISION_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
_NETWORK_MODE: ContextVar[str | None] = ContextVar("agora_context_fabric_network_mode", default=None)
_SELECTION_RECORD = "agora-selection.json"
_CONNECTIVITY_MARKERS = (
    "could not resolve host",
    "could not resolve hostname",
    "failed to connect",
    "connection timed out",
    "connection timeout",
    "connection refused",
    "network is unreachable",
    "no route to host",
    "temporary failure in name resolution",
    "couldn't connect to server",
    "proxy connect aborted",
    "proxyconnect tcp",
    "tls connect error",
    "ssl connect error",
)


class NetworkUnavailableError(RuntimeError):
    """A remote operation failed because network connectivity is unavailable."""


class OfflineCacheMissError(RuntimeError):
    """Offline mode cannot satisfy a request from the existing local cache."""


class RemoteResolutionError(RuntimeError):
    """A remote Git failure must not be mistaken for an offline condition."""


@dataclass(frozen=True)
class RepositoryResolution:
    path: Path
    revision: str
    source_revision_verified: bool
    resolution: str
    allow_network: bool = True


def validate_network_mode(mode: str) -> str:
    normalized = mode.strip().casefold()
    if normalized not in NETWORK_MODES:
        allowed = ", ".join(sorted(NETWORK_MODES))
        raise ValueError(f"network_mode must be one of: {allowed}")
    return normalized


def current_network_mode() -> str:
    explicit = _NETWORK_MODE.get()
    if explicit is not None:
        return explicit
    return validate_network_mode(os.environ.get("AGORA_CORPUS_NETWORK_MODE", "auto"))


@contextmanager
def use_network_mode(mode: str) -> Iterator[None]:
    token = _NETWORK_MODE.set(validate_network_mode(mode))
    try:
        yield
    finally:
        _NETWORK_MODE.reset(token)


def _stderr_text(exc: subprocess.CalledProcessError) -> str:
    stderr = exc.stderr
    if isinstance(stderr, bytes):
        return stderr.decode("utf-8", errors="replace").strip()
    return str(stderr or "").strip()


def is_connectivity_failure(exc: subprocess.CalledProcessError) -> bool:
    rendered = _stderr_text(exc).casefold()
    return any(marker in rendered for marker in _CONNECTIVITY_MARKERS)


def _remote_error(resource_id: str, exc: subprocess.CalledProcessError) -> RemoteResolutionError:
    detail = _stderr_text(exc) or f"git exited with status {exc.returncode}"
    return RemoteResolutionError(
        f"cannot resolve Context-Fabric resource {resource_id!r} from its upstream repository: {detail}"
    )


def _network_error(resource_id: str) -> NetworkUnavailableError:
    return NetworkUnavailableError(
        f"cannot resolve Context-Fabric resource {resource_id!r}: network access is unavailable"
    )


def _record_path(repo: Path) -> Path:
    return repo / ".git" / _SELECTION_RECORD


def _write_selection_record(
    repo: Path,
    *,
    repository: str,
    configured_ref: str | None,
    revision: str,
) -> None:
    record = {
        "repository": repository,
        "configured_ref": configured_ref,
        "revision": revision,
    }
    destination = _record_path(repo)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(record, handle, sort_keys=True)
            temporary = Path(handle.name)
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def _selection_matches(
    repo: Path,
    *,
    repository: str,
    configured_ref: str | None,
    revision: str,
) -> bool:
    if configured_ref is None:
        return True
    if _IMMUTABLE_REVISION_RE.fullmatch(configured_ref):
        return configured_ref.casefold() == revision.casefold()
    try:
        record = json.loads(_record_path(repo).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False
    return (
        record.get("repository") == repository
        and record.get("configured_ref") == configured_ref
        and record.get("revision") == revision
    )


def _cached_resolution(
    store: GitStore,
    *,
    resource_id: str,
    repository: str,
    configured_ref: str | None,
) -> RepositoryResolution:
    repo = store.repositories_dir / store.safe_cache_key(resource_id)
    if not (repo / ".git").is_dir():
        raise OfflineCacheMissError(
            f"Context-Fabric resource {resource_id!r} is not cached; network access is required for acquisition"
        )
    try:
        revision = store.selected_revision(repo)
    except subprocess.CalledProcessError as exc:
        raise OfflineCacheMissError(
            f"Context-Fabric resource {resource_id!r} has no cached selected revision; network access is required"
        ) from exc
    if not _selection_matches(
        repo,
        repository=repository,
        configured_ref=configured_ref,
        revision=revision,
    ):
        raise OfflineCacheMissError(
            f"cached metadata for Context-Fabric resource {resource_id!r} does not match its configured ref; network access is required"
        )
    immutable = bool(
        configured_ref
        and _IMMUTABLE_REVISION_RE.fullmatch(configured_ref)
        and configured_ref.casefold() == revision.casefold()
    )
    return RepositoryResolution(
        path=repo,
        revision=revision,
        source_revision_verified=immutable,
        resolution="cached",
        allow_network=False,
    )


def resolve_repository(
    store: GitStore,
    *,
    resource_id: str,
    repository: str,
    configured_ref: str | None,
) -> RepositoryResolution:
    mode = current_network_mode()
    if mode == "offline":
        return _cached_resolution(
            store,
            resource_id=resource_id,
            repository=repository,
            configured_ref=configured_ref,
        )

    try:
        kwargs = {"cache_key": resource_id}
        if configured_ref is not None:
            kwargs["ref"] = configured_ref
        repo = store.ensure_metadata(repository, **kwargs)
        revision = store.selected_revision(repo)
    except subprocess.CalledProcessError as exc:
        if not is_connectivity_failure(exc):
            raise _remote_error(resource_id, exc) from exc
        if mode == "auto":
            try:
                return _cached_resolution(
                    store,
                    resource_id=resource_id,
                    repository=repository,
                    configured_ref=configured_ref,
                )
            except OfflineCacheMissError:
                pass
        raise _network_error(resource_id) from exc

    _write_selection_record(
        repo,
        repository=repository,
        configured_ref=configured_ref,
        revision=revision,
    )
    return RepositoryResolution(
        path=repo,
        revision=revision,
        source_revision_verified=True,
        resolution="fresh",
        allow_network=True,
    )


def _cached_object(
    store: GitStore,
    *,
    resource_id: str,
    revision: str,
    relative_path: str,
    kind: str,
) -> Path:
    for entry in store.cache_entries(resource_id):
        if (
            entry.get("kind") == kind
            and entry.get("revision") == revision
            and entry.get("relative_path") == relative_path
        ):
            path = Path(str(entry["path"]))
            store.touch_cache_object(path)
            return path
    raise OfflineCacheMissError(
        f"materialized cache for Context-Fabric resource {resource_id!r} at revision {revision} "
        "is not available; network access is required to acquire the missing corpus bytes"
    )


def materialize_corpus(
    store: GitStore,
    resolution: RepositoryResolution,
    *,
    resource_id: str,
    relative_path: str,
) -> Path:
    if current_network_mode() == "offline" or not resolution.allow_network:
        return _cached_object(
            store,
            resource_id=resource_id,
            revision=resolution.revision,
            relative_path=relative_path,
            kind="corpus-snapshot",
        )
    try:
        return store.materialize(resolution.path, relative_path, resolution.revision)
    except subprocess.CalledProcessError as exc:
        if is_connectivity_failure(exc):
            raise _network_error(resource_id) from exc
        raise _remote_error(resource_id, exc) from exc


def materialize_feature_module(
    store: GitStore,
    resolution: RepositoryResolution,
    *,
    resource_id: str,
    relative_path: str,
) -> Path:
    if current_network_mode() == "offline" or not resolution.allow_network:
        return _cached_object(
            store,
            resource_id=resource_id,
            revision=resolution.revision,
            relative_path=relative_path,
            kind="feature-module-snapshot",
        )
    try:
        return store.materialize_feature_module(
            resolution.path,
            relative_path,
            resolution.revision,
        )
    except subprocess.CalledProcessError as exc:
        if is_connectivity_failure(exc):
            raise _network_error(resource_id) from exc
        raise _remote_error(resource_id, exc) from exc
