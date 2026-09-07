from __future__ import annotations

import os
import subprocess
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Literal

from . import _core as _core_module

# Preserve the historical gitstore module surface after converting it into a
# package. This keeps existing imports and patch targets compatible while the
# exact-object compile lock and source-resolution policy remain small
# extensions around the mature cache lifecycle implementation in _core.py.
for _name, _value in vars(_core_module).items():
    if _name == "GitStore" or _name.startswith("__"):
        continue
    globals().setdefault(_name, _value)

_CoreGitStore = _core_module.GitStore

SourceMode = Literal["prefer-fresh", "offline", "require-fresh"]


@dataclass(frozen=True)
class MetadataSelection:
    repo: Path
    revision: str
    source_resolution: Literal["remote", "cached", "explicit-revision"]
    source_revision_verified: bool


@dataclass
class SourcePolicyState:
    mode: SourceMode
    allow_network: bool
    selections: dict[str, MetadataSelection] = field(default_factory=dict)


_SOURCE_POLICY: ContextVar[SourcePolicyState | None] = ContextVar(
    "agora_context_fabric_source_policy",
    default=None,
)


class GitStore(_CoreGitStore):
    """Context-Fabric cache store with compile and source-resolution policy."""

    SOURCE_MODES = frozenset({"prefer-fresh", "offline", "require-fresh"})
    _NON_CONNECTIVITY_MARKERS = (
        "authentication failed",
        "repository not found",
        "permission denied",
        "access denied",
        "couldn't find remote ref",
        "could not find remote ref",
        "remote ref does not exist",
        "not our ref",
    )
    _CONNECTIVITY_MARKERS = (
        "could not resolve host",
        "could not resolve proxy",
        "network is unreachable",
        "connection refused",
        "connection timed out",
        "operation timed out",
        "failed to connect",
        "couldn't connect to server",
    )

    @classmethod
    def validate_source_mode(cls, source_mode: str | None) -> SourceMode:
        mode = "prefer-fresh" if source_mode is None else source_mode
        if mode not in cls.SOURCE_MODES:
            allowed = ", ".join(sorted(cls.SOURCE_MODES))
            raise ValueError(f"source_mode must be one of: {allowed}")
        return mode  # type: ignore[return-value]

    @staticmethod
    def _stderr_text(exc: subprocess.CalledProcessError) -> str:
        value = exc.stderr
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value or "")

    @classmethod
    def _is_connectivity_failure(cls, exc: subprocess.CalledProcessError) -> bool:
        text = cls._stderr_text(exc).casefold()
        if any(marker in text for marker in cls._NON_CONNECTIVITY_MARKERS):
            return False
        return any(marker in text for marker in cls._CONNECTIVITY_MARKERS)

    def _run_refresh(self, *args: str, cwd: Path | None = None) -> str:
        command = ["git"]
        if cwd is not None:
            command += ["-C", str(cwd)]
        command += list(args)
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        env["GIT_TERMINAL_PROMPT"] = "0"
        result = subprocess.run(
            command,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        return result.stdout.strip()

    def _run(self, *args: str, cwd: Path | None = None) -> str:
        # Any fetch may surface diagnostics consumed by source-failure
        # classification. Keep those diagnostics stable and credential prompting
        # disabled, including the disposable snapshot-export repository fetch.
        if args and args[0] == "fetch":
            return self._run_refresh(*args, cwd=cwd)
        return super()._run(*args, cwd=cwd)

    def _select(self, repo: Path, ref: str | None) -> str:
        target = ref or "HEAD"
        self._run_refresh(
            "fetch",
            "--quiet",
            "--filter=blob:none",
            "--depth",
            "1",
            "origin",
            target,
            cwd=repo,
        )
        selected = self._run("rev-parse", "FETCH_HEAD", cwd=repo)
        self._run("update-ref", self.SELECTED_REF, selected, cwd=repo)
        return selected

    @contextmanager
    def source_policy(self, source_mode: str | None = None) -> Iterator[SourcePolicyState]:
        mode = self.validate_source_mode(source_mode)
        state = SourcePolicyState(mode=mode, allow_network=mode != "offline")
        token = _SOURCE_POLICY.set(state)
        try:
            yield state
        finally:
            _SOURCE_POLICY.reset(token)

    def current_source_policy(self) -> SourcePolicyState | None:
        return _SOURCE_POLICY.get()

    def _record_selection(self, key: str, selection: MetadataSelection) -> None:
        state = self.current_source_policy()
        if state is not None:
            state.selections[key] = selection

    def select_metadata(
        self,
        repository: str,
        *,
        cache_key: str | None = None,
        ref: str | None = None,
        source_mode: str | None = None,
    ) -> MetadataSelection:
        requested_mode = self.validate_source_mode(source_mode)
        state = self.current_source_policy()
        mode: SourceMode = requested_mode
        # Once an operation has fallen back because connectivity is unavailable,
        # subsequent parent/module resolutions must not open a second network
        # path. They become cached-only for the remainder of that operation.
        if state is not None and not state.allow_network and requested_mode == "prefer-fresh":
            mode = "offline"

        key = self.safe_cache_key(cache_key or repository)
        destination = self.repositories_dir / key
        with self._repository_lock(key):
            if mode == "offline":
                if not (destination / ".git").is_dir():
                    raise RuntimeError(
                        f"resource {key!r} is not cached for offline use; network-enabled "
                        "preparation is required before it can be used offline"
                    )
                try:
                    revision = self.selected_revision(destination)
                except subprocess.CalledProcessError as exc:
                    raise RuntimeError(
                        f"resource {key!r} has no cached selected revision for offline use; "
                        "network-enabled preparation is required"
                    ) from exc
                selection = MetadataSelection(
                    repo=destination,
                    revision=revision,
                    source_resolution="cached",
                    source_revision_verified=False,
                )
                self._record_selection(key, selection)
                return selection

            existed = (destination / ".git").is_dir()
            if not existed:
                source = self.repository_url(repository)
                try:
                    self._run_refresh(
                        "clone",
                        "--quiet",
                        "--filter=blob:none",
                        "--no-checkout",
                        "--depth",
                        "1",
                        source,
                        str(destination),
                    )
                except subprocess.CalledProcessError as exc:
                    if self._is_connectivity_failure(exc):
                        raise RuntimeError(
                            f"resource {key!r} is not cached and upstream acquisition failed; "
                            "network access is required to prepare it"
                        ) from exc
                    raise RuntimeError(
                        f"upstream acquisition failed for resource {key!r}; "
                        "cached state was not substituted"
                    ) from exc

            try:
                revision = self._select(destination, ref)
            except subprocess.CalledProcessError as exc:
                if mode == "require-fresh" or not self._is_connectivity_failure(exc):
                    qualifier = "fresh upstream resolution" if mode == "require-fresh" else "upstream refresh"
                    raise RuntimeError(
                        f"{qualifier} failed for resource {key!r}; cached state was not substituted"
                    ) from exc
                try:
                    revision = self.selected_revision(destination)
                except subprocess.CalledProcessError:
                    raise RuntimeError(
                        f"upstream refresh failed for resource {key!r} and no cached selected "
                        "revision is available; network access is required"
                    ) from exc
                selection = MetadataSelection(
                    repo=destination,
                    revision=revision,
                    source_resolution="cached",
                    source_revision_verified=False,
                )
                if state is not None:
                    state.allow_network = False
                self._record_selection(key, selection)
                return selection

            selection = MetadataSelection(
                repo=destination,
                revision=revision,
                source_resolution="remote",
                source_revision_verified=True,
            )
            self._record_selection(key, selection)
            return selection

    def ensure_metadata(
        self,
        repository: str,
        *,
        cache_key: str | None = None,
        ref: str | None = None,
    ) -> Path:
        state = self.current_source_policy()
        mode: str | None = None
        if state is not None:
            mode = "offline" if not state.allow_network else state.mode
        return self.select_metadata(
            repository,
            cache_key=cache_key,
            ref=ref,
            source_mode=mode,
        ).repo

    def _cached_snapshot(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None,
        *,
        kind: str,
        validate,
    ) -> Path:
        relative = self._safe_relative_path(relative_path)
        try:
            resolved_revision = self._resolved_revision(repo, revision)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"revision {revision or self.SELECTED_REF!r} is not cached for offline use"
            ) from exc
        destination = self._snapshot_destination(repo, resolved_revision, relative, kind=kind)
        with self.cache_transition():
            try:
                validate(destination)
            except FileNotFoundError as exc:
                raise RuntimeError(
                    f"offline cache miss for {repo.name!r} at {relative!r} revision "
                    f"{resolved_revision}; network-enabled preparation is required to publish "
                    "the source snapshot"
                ) from exc
            self.touch_cache_object(destination)
            return destination

    def _materialize_snapshot(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None,
        *,
        kind: str,
        validate,
    ) -> Path:
        try:
            return super()._materialize_snapshot(
                repo,
                relative_path,
                revision,
                kind=kind,
                validate=validate,
            )
        except subprocess.CalledProcessError as exc:
            relative = self._safe_relative_path(relative_path)
            if self._is_connectivity_failure(exc):
                raise RuntimeError(
                    f"source snapshot acquisition failed for {repo.name!r} at {relative!r}; "
                    "network access is required to publish the snapshot"
                ) from exc
            raise RuntimeError(
                f"source snapshot acquisition failed for {repo.name!r} at {relative!r}; "
                "cached state was not substituted"
            ) from exc

    def materialize(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None = None,
        *,
        allow_network: bool | None = None,
    ) -> Path:
        state = self.current_source_policy()
        network_allowed = (
            state.allow_network if allow_network is None and state is not None else allow_network
        )
        if network_allowed is False:
            return self._cached_snapshot(
                repo,
                relative_path,
                revision,
                kind="corpora",
                validate=self._validate_corpus_snapshot,
            )
        return super().materialize(repo, relative_path, revision)

    def materialize_feature_module(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None = None,
        *,
        allow_network: bool | None = None,
    ) -> Path:
        state = self.current_source_policy()
        network_allowed = (
            state.allow_network if allow_network is None and state is not None else allow_network
        )
        files = tuple(self.feature_files(repo, relative_path, revision))
        if not files:
            raise FileNotFoundError(
                f"materialized path is not a Text-Fabric feature module: {relative_path}"
            )
        if network_allowed is False:
            return self._cached_snapshot(
                repo,
                relative_path,
                revision,
                kind="feature-modules",
                validate=lambda path: self._validate_module_snapshot(path, files),
            )
        return self._materialize_snapshot(
            repo,
            relative_path,
            revision,
            kind="feature-modules",
            validate=lambda path: self._validate_module_snapshot(path, files),
        )

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
