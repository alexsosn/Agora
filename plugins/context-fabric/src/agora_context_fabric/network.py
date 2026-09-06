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
from typing import Any, Iterator

from .gitstore import GitStore


NETWORK_MODES = frozenset({"auto", "offline", "require-fresh"})
_IMMUTABLE_REVISION_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
_NETWORK_MODE: ContextVar[str | None] = ContextVar(
    "agora_context_fabric_network_mode",
    default=None,
)
_SELECTION_RECORD = "agora-selection.json"
_INVALID_RECORD = object()

# Git delegates HTTP(S) transport to libcurl while SSH and local Git emit their
# own diagnostics. Keep this intentionally narrow: an unknown remote failure is
# a remote/configuration error, never an excuse to serve stale state.
_CONNECTIVITY_MARKERS = (
    "could not resolve host",
    "could not resolve hostname",
    "temporary failure in name resolution",
    "name or service not known",
    "failed to connect",
    "connection timed out",
    "connection timeout",
    "connection refused",
    "connection reset by peer",
    "network is unreachable",
    "no route to host",
    "operation timed out",
    "couldn't connect to server",
    "proxy connect aborted",
    "proxyconnect tcp",
    "recv failure",
    "send failure",
    "tls connect error",
    "ssl connect error",
)


class NetworkUnavailableError(RuntimeError):
    """A required remote operation failed because connectivity is unavailable."""


class OfflineCacheMissError(RuntimeError):
    """Offline/degraded resolution cannot be satisfied by compatible local state."""


class RemoteResolutionError(RuntimeError):
    """A non-connectivity Git failure that must not trigger stale fallback."""


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
    destination = _record_path(repo)
    if not destination.parent.is_dir():
        return
    record = {
        "repository": repository,
        "configured_ref": configured_ref,
        "revision": revision,
    }
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
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def _read_selection_record(repo: Path) -> dict[str, Any] | object | None:
    path = _record_path(repo)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return _INVALID_RECORD
    try:
        record = json.loads(raw)
    except (ValueError, TypeError, json.JSONDecodeError):
        return _INVALID_RECORD
    if not isinstance(record, dict):
        return _INVALID_RECORD
    if not isinstance(record.get("repository"), str):
        return _INVALID_RECORD
    configured_ref = record.get("configured_ref")
    if configured_ref is not None and not isinstance(configured_ref, str):
        return _INVALID_RECORD
    revision = record.get("revision")
    if not isinstance(revision, str) or not _IMMUTABLE_REVISION_RE.fullmatch(revision):
        return _INVALID_RECORD
    return record


def _repository_identity(value: str) -> str:
    """Normalize local Git origins without broadening remote URL equivalence."""
    if "://" in value or value.startswith("git@"):
        return value.rstrip("/\\")
    candidate = Path(value).expanduser()
    if candidate.is_absolute() or candidate.exists():
        resolved = candidate.resolve(strict=False)
        return os.path.normcase(os.path.normpath(str(resolved))).rstrip("/\\")
    return value.rstrip("/\\")


def _repository_matches(store: GitStore, repo: Path, repository: str) -> bool:
    try:
        actual = store._run("remote", "get-url", "origin", cwd=repo)
    except subprocess.CalledProcessError:
        return False
    expected = store.repository_url(repository)
    return _repository_identity(actual) == _repository_identity(expected)


def _legacy_ref_names(configured_ref: str) -> tuple[tuple[str, str], ...]:
    if configured_ref.startswith("refs/heads/"):
        return (("branch", configured_ref.removeprefix("refs/heads/")),)
    if configured_ref.startswith("refs/tags/"):
        return (("tag", configured_ref.removeprefix("refs/tags/")),)
    return (("branch", configured_ref), ("tag", configured_ref))


def _legacy_fetch_head_matches(repo: Path, configured_ref: str, revision: str) -> bool:
    """Recognize only unambiguous old `_select()` FETCH_HEAD evidence.

    Pre-selection-record Agora fetched exactly one configured ref and then copied
    FETCH_HEAD into refs/agora/selected. Git preserves the fetched ref kind/name
    in the mergeable FETCH_HEAD record. That is enough to migrate a legacy
    branch/tag cache only when exactly one recognized record binds the selected
    commit to the currently configured ref.
    """
    try:
        lines = (repo / ".git" / "FETCH_HEAD").read_text(encoding="utf-8").splitlines()
    except OSError:
        return False

    accepted_prefixes = tuple(
        f"{kind} '{name}' of " for kind, name in _legacy_ref_names(configured_ref)
    )
    matches = 0
    for line in lines:
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        commit, not_for_merge, description = parts
        if commit.casefold() != revision.casefold():
            continue
        if not_for_merge:
            continue
        if description.startswith(accepted_prefixes):
            matches += 1
    return matches == 1


def _selection_matches(
    store: GitStore,
    repo: Path,
    *,
    repository: str,
    configured_ref: str | None,
    revision: str,
) -> bool:
    if not _repository_matches(store, repo, repository):
        return False

    record = _read_selection_record(repo)
    if record is _INVALID_RECORD:
        return False
    if isinstance(record, dict):
        return (
            record.get("repository") == repository
            and record.get("configured_ref") == configured_ref
            and str(record.get("revision", "")).casefold() == revision.casefold()
        )

    # Legacy cache: refs/agora/selected existed before selection records.
    if configured_ref is None:
        return True
    if _IMMUTABLE_REVISION_RE.fullmatch(configured_ref):
        return configured_ref.casefold() == revision.casefold()
    return _legacy_fetch_head_matches(repo, configured_ref, revision)


@contextmanager
def _repository_selection_transaction(
    store: GitStore,
    *,
    resource_id: str,
    repository: str,
    configured_ref: str | None,
) -> Iterator[tuple[Path, str]]:
    """Select one upstream revision while holding the repository mutation lock.

    GitStore.ensure_metadata() historically releases this lock before callers can
    read refs/agora/selected. Freshness provenance must bind to the exact revision
    chosen by this request, so clone/fetch/select, revision capture, and selection
    record persistence are kept inside one cross-process critical section here.
    """
    key = store.safe_cache_key(resource_id)
    repo = store.repositories_dir / key
    with store._repository_lock(key):
        if (repo / ".git").is_dir() and not _repository_matches(store, repo, repository):
            # Invalidate identity evidence before repointing origin. If the new
            # source cannot be reached, auto mode must fail instead of treating
            # the old repository's selected ref as a cache hit for the new one.
            store._run("update-ref", "-d", store.SELECTED_REF, cwd=repo)
            try:
                _record_path(repo).unlink()
            except FileNotFoundError:
                pass
            store._run(
                "remote",
                "set-url",
                "origin",
                store.repository_url(repository),
                cwd=repo,
            )
        if not (repo / ".git").is_dir():
            source = store.repository_url(repository)
            store._run(
                "clone",
                "--quiet",
                "--filter=blob:none",
                "--no-checkout",
                "--depth",
                "1",
                source,
                str(repo),
            )
        revision = store._select(repo, configured_ref)
        yield repo, revision


def _cached_resolution(
    store: GitStore,
    *,
    resource_id: str,
    repository: str,
    configured_ref: str | None,
) -> RepositoryResolution:
    key = store.safe_cache_key(resource_id)
    repo = store.repositories_dir / key
    with store._repository_lock(key):
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
            store,
            repo,
            repository=repository,
            configured_ref=configured_ref,
            revision=revision,
        ):
            raise OfflineCacheMissError(
                f"cached metadata for Context-Fabric resource {resource_id!r} does not match its configured "
                "repository/ref; network access is required"
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
        with _repository_selection_transaction(
            store,
            resource_id=resource_id,
            repository=repository,
            configured_ref=configured_ref,
        ) as (repo, revision):
            _write_selection_record(
                repo,
                repository=repository,
                configured_ref=configured_ref,
                revision=revision,
            )
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
