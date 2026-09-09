from __future__ import annotations

import os
import subprocess
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Literal

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

# Repository metadata inspection is an additive package-level extension around
# the mature core cache. Publish the constants on _core as well so historical
# patch/import targets continue to work while the implementation remains here.
DEFAULT_GIT_STATUS_BUDGET_SECONDS = 2.0
DEFAULT_GIT_MAINTENANCE_PACK_LIMIT = 16
DEFAULT_GIT_MAINTENANCE_BUDGET_SECONDS = 30.0
DEFAULT_GIT_MAINTENANCE_TIMEOUT_SECONDS = 15.0
_core_module.DEFAULT_GIT_STATUS_BUDGET_SECONDS = DEFAULT_GIT_STATUS_BUDGET_SECONDS
_core_module.DEFAULT_GIT_MAINTENANCE_PACK_LIMIT = DEFAULT_GIT_MAINTENANCE_PACK_LIMIT
_core_module.DEFAULT_GIT_MAINTENANCE_BUDGET_SECONDS = DEFAULT_GIT_MAINTENANCE_BUDGET_SECONDS
_core_module.DEFAULT_GIT_MAINTENANCE_TIMEOUT_SECONDS = DEFAULT_GIT_MAINTENANCE_TIMEOUT_SECONDS

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
    """Context-Fabric cache store with source, compile and metadata policy."""

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

    @staticmethod
    def _parse_count_objects(output: str) -> dict[str, int]:
        required = {
            "count",
            "size",
            "in-pack",
            "packs",
            "size-pack",
            "prune-packable",
            "garbage",
            "size-garbage",
        }
        values: dict[str, int] = {}
        for raw_line in output.splitlines():
            key, separator, raw_value = raw_line.partition(":")
            key = key.strip()
            if not separator or key not in required:
                continue
            if key in values:
                raise ValueError(f"duplicate git count-objects field: {key}")
            try:
                value = int(raw_value.strip())
            except ValueError as exc:
                raise ValueError(f"malformed git count-objects field: {key}") from exc
            if value < 0:
                raise ValueError(f"negative git count-objects field: {key}")
            values[key] = value

        missing = sorted(required - values.keys())
        if missing:
            raise ValueError(
                "missing git count-objects field(s): " + ", ".join(missing)
            )
        return {
            "count": values["count"],
            "size_bytes": values["size"] * 1024,
            "in_pack": values["in-pack"],
            "packs": values["packs"],
            "size_pack_bytes": values["size-pack"] * 1024,
            "prune_packable": values["prune-packable"],
            "garbage": values["garbage"],
            "garbage_bytes": values["size-garbage"] * 1024,
        }

    @staticmethod
    def _directory_size_bounded(
        path: Path,
        *,
        deadline: float,
    ) -> tuple[int | None, bool]:
        total = 0
        for root, _dirs, files in os.walk(path):
            if time.monotonic() >= deadline:
                return None, False
            for filename in files:
                if time.monotonic() >= deadline:
                    return None, False
                candidate = Path(root) / filename
                try:
                    if not candidate.is_symlink():
                        total += candidate.stat().st_size
                except FileNotFoundError:
                    continue
        if time.monotonic() >= deadline:
            return None, False
        return total, True

    def _git_count_objects(self, repo: Path, *, timeout: float) -> dict[str, int]:
        if timeout <= 0:
            raise subprocess.TimeoutExpired(["git", "count-objects", "-v"], timeout)
        result = subprocess.run(
            ["git", "-C", str(repo), "count-objects", "-v"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return self._parse_count_objects(result.stdout)

    @staticmethod
    def _repository_status_row(cache_key: str, repo: Path) -> dict[str, Any]:
        return {
            "cache_key": cache_key,
            "path": str(repo),
            "size_bytes": None,
            "size_complete": False,
            "packs": None,
            "garbage_entries": None,
            "garbage_bytes": None,
            "maintenance_needed": None,
            "busy": False,
            "inspection_status": "budget-exhausted",
        }

    def _repository_status(self) -> dict[str, Any]:
        budget = float(_core_module.DEFAULT_GIT_STATUS_BUDGET_SECONDS)
        deadline = time.monotonic() + max(0.0, budget)
        rows: list[dict[str, Any]] = []

        repositories = sorted(
            (path for path in self.repositories_dir.iterdir() if path.is_dir()),
            key=lambda path: path.name,
        )
        for repo in repositories:
            row = self._repository_status_row(repo.name, repo)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                rows.append(row)
                continue

            try:
                with self._repository_lock(repo.name, timeout=remaining, shared=True):
                    git_ok = False
                    remaining = deadline - time.monotonic()
                    if remaining > 0:
                        try:
                            git = self._git_count_objects(repo, timeout=remaining)
                        except subprocess.TimeoutExpired:
                            row["inspection_status"] = "budget-exhausted"
                        except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError):
                            row["inspection_status"] = "error"
                        else:
                            row["packs"] = git["packs"]
                            row["garbage_entries"] = git["garbage"]
                            row["garbage_bytes"] = git["garbage_bytes"]
                            row["maintenance_needed"] = bool(
                                git["garbage"] > 0
                                or git["packs"] > _core_module.DEFAULT_GIT_MAINTENANCE_PACK_LIMIT
                            )
                            git_ok = True
                            row["inspection_status"] = "ok"

                    remaining = deadline - time.monotonic()
                    if remaining > 0:
                        try:
                            size, complete = self._directory_size_bounded(
                                repo,
                                deadline=deadline,
                            )
                        except OSError:
                            row["inspection_status"] = "error"
                        else:
                            row["size_bytes"] = size
                            row["size_complete"] = complete
                            if not complete and row["inspection_status"] == "ok":
                                row["inspection_status"] = "budget-exhausted"
                    elif row["inspection_status"] == "ok" or git_ok:
                        row["inspection_status"] = "budget-exhausted"
            except TimeoutError:
                row["busy"] = True
                row["inspection_status"] = "busy"

            rows.append(row)

        bytes_complete = all(bool(row["size_complete"]) for row in rows)
        repository_bytes = (
            sum(int(row["size_bytes"]) for row in rows)
            if bytes_complete
            else None
        )
        git_complete = all(
            row["packs"] is not None
            and row["garbage_entries"] is not None
            and row["garbage_bytes"] is not None
            for row in rows
        )
        pack_count = (
            sum(int(row["packs"]) for row in rows) if git_complete else None
        )
        garbage_entries = (
            sum(int(row["garbage_entries"]) for row in rows)
            if git_complete
            else None
        )
        garbage_bytes = (
            sum(int(row["garbage_bytes"]) for row in rows)
            if git_complete
            else None
        )
        budget_exhausted = (
            time.monotonic() >= deadline
            or any(row["inspection_status"] == "budget-exhausted" for row in rows)
        )
        return {
            "repository_cache_bytes": repository_bytes,
            "repository_cache_bytes_complete": bytes_complete,
            "repository_cache_gb": (
                self._gib(repository_bytes) if repository_bytes is not None else None
            ),
            "repository_git_metrics_complete": git_complete,
            "repository_pack_count": pack_count,
            "repository_garbage_entries": garbage_entries,
            "repository_garbage_bytes": garbage_bytes,
            "repository_garbage_gb": (
                self._gib(garbage_bytes) if garbage_bytes is not None else None
            ),
            "repository_inspection_budget_seconds": budget,
            "repository_inspection_budget_exhausted": budget_exhausted,
            "repositories": rows,
        }

    def cache_status(self) -> dict[str, Any]:
        status = super().cache_status()
        status.update(self._repository_status())
        return status

    def _git_maintenance(self, repo: Path, *, timeout: float) -> None:
        if timeout <= 0:
            raise subprocess.TimeoutExpired(["git", "gc", "--prune=now"], timeout)
        subprocess.run(
            ["git", "-C", str(repo), "gc", "--prune=now"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )

    @staticmethod
    def _repository_maintenance_row(cache_key: str, repo: Path) -> dict[str, Any]:
        return {
            "cache_key": cache_key,
            "path": str(repo),
            "maintenance_attempted": False,
            "maintenance_status": "budget-exhausted",
            "before_measurement_complete": False,
            "after_measurement_complete": False,
            "bytes_before": None,
            "bytes_after": None,
            "bytes_reclaimed": None,
            "garbage_entries_before": None,
            "garbage_entries_after": None,
            "garbage_entries_removed": None,
            "packs_before": None,
            "packs_after": None,
        }

    def _repository_maintenance(self) -> dict[str, Any]:
        budget = float(_core_module.DEFAULT_GIT_MAINTENANCE_BUDGET_SECONDS)
        deadline = time.monotonic() + max(0.0, budget)
        rows: list[dict[str, Any]] = []
        budget_exhausted = budget <= 0

        repositories = sorted(
            (path for path in self.repositories_dir.iterdir() if path.is_dir()),
            key=lambda path: path.name,
        )
        for repo in repositories:
            row = self._repository_maintenance_row(repo.name, repo)
            if budget_exhausted or time.monotonic() >= deadline:
                budget_exhausted = True
                rows.append(row)
                continue

            remaining = deadline - time.monotonic()
            try:
                with self._repository_lock(repo.name, timeout=remaining, shared=False):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        budget_exhausted = True
                        rows.append(row)
                        continue
                    try:
                        before_git = self._git_count_objects(repo, timeout=remaining)
                    except subprocess.TimeoutExpired:
                        row["maintenance_status"] = "timed-out"
                        budget_exhausted = True
                        rows.append(row)
                        continue
                    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError):
                        row["maintenance_status"] = "failed"
                        rows.append(row)
                        continue

                    row["garbage_entries_before"] = before_git["garbage"]
                    row["packs_before"] = before_git["packs"]
                    try:
                        before_size, before_size_complete = self._directory_size_bounded(
                            repo,
                            deadline=deadline,
                        )
                    except OSError:
                        before_size, before_size_complete = None, False
                    row["bytes_before"] = before_size
                    row["before_measurement_complete"] = bool(before_size_complete)
                    if not before_size_complete:
                        budget_exhausted = time.monotonic() >= deadline
                        row["maintenance_status"] = (
                            "budget-exhausted" if budget_exhausted else "failed"
                        )
                        rows.append(row)
                        continue

                    needs_maintenance = bool(
                        before_git["garbage"] > 0
                        or before_git["packs"] > _core_module.DEFAULT_GIT_MAINTENANCE_PACK_LIMIT
                    )
                    if not needs_maintenance:
                        row["maintenance_status"] = "skipped"
                        row["after_measurement_complete"] = True
                        row["bytes_after"] = before_size
                        row["bytes_reclaimed"] = 0
                        row["garbage_entries_after"] = before_git["garbage"]
                        row["garbage_entries_removed"] = 0
                        row["packs_after"] = before_git["packs"]
                        rows.append(row)
                        continue

                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        budget_exhausted = True
                        row["maintenance_status"] = "budget-exhausted"
                        rows.append(row)
                        continue

                    row["maintenance_attempted"] = True
                    gc_timeout = min(
                        float(_core_module.DEFAULT_GIT_MAINTENANCE_TIMEOUT_SECONDS),
                        remaining,
                    )
                    try:
                        self._git_maintenance(repo, timeout=gc_timeout)
                    except subprocess.TimeoutExpired:
                        row["maintenance_status"] = "timed-out"
                        if gc_timeout >= remaining:
                            budget_exhausted = True
                        rows.append(row)
                        continue
                    except (OSError, RuntimeError, subprocess.CalledProcessError):
                        row["maintenance_status"] = "failed"
                        rows.append(row)
                        continue

                    row["maintenance_status"] = "success"
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        budget_exhausted = True
                        rows.append(row)
                        continue
                    try:
                        after_git = self._git_count_objects(repo, timeout=remaining)
                    except subprocess.TimeoutExpired:
                        budget_exhausted = True
                        rows.append(row)
                        continue
                    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError):
                        rows.append(row)
                        continue

                    row["garbage_entries_after"] = after_git["garbage"]
                    row["garbage_entries_removed"] = (
                        int(row["garbage_entries_before"]) - after_git["garbage"]
                    )
                    row["packs_after"] = after_git["packs"]
                    try:
                        after_size, after_size_complete = self._directory_size_bounded(
                            repo,
                            deadline=deadline,
                        )
                    except OSError:
                        after_size, after_size_complete = None, False
                    row["bytes_after"] = after_size
                    if before_size_complete and after_size_complete:
                        row["bytes_reclaimed"] = int(before_size) - int(after_size)
                    row["after_measurement_complete"] = bool(
                        after_size_complete
                        and row["garbage_entries_after"] is not None
                        and row["packs_after"] is not None
                    )
                    if not after_size_complete and time.monotonic() >= deadline:
                        budget_exhausted = True
            except TimeoutError:
                row["maintenance_status"] = "budget-exhausted"
                budget_exhausted = True

            rows.append(row)

        attempted = sum(int(bool(row["maintenance_attempted"])) for row in rows)
        succeeded = sum(row["maintenance_status"] == "success" for row in rows)
        failed = sum(row["maintenance_status"] == "failed" for row in rows)
        timed_out = sum(row["maintenance_status"] == "timed-out" for row in rows)
        skipped_budget = sum(row["maintenance_status"] == "budget-exhausted" for row in rows)
        reclamation_complete = all(
            row["maintenance_status"] == "skipped"
            or (
                row["maintenance_status"] == "success"
                and bool(row["before_measurement_complete"])
                and bool(row["after_measurement_complete"])
            )
            for row in rows
        )
        bytes_reclaimed = (
            sum(int(row["bytes_reclaimed"]) for row in rows)
            if reclamation_complete
            else None
        )
        garbage_removed = (
            sum(int(row["garbage_entries_removed"]) for row in rows)
            if reclamation_complete
            else None
        )
        packs_before = (
            sum(int(row["packs_before"]) for row in rows)
            if all(row["packs_before"] is not None for row in rows)
            else None
        )
        packs_after = (
            sum(int(row["packs_after"]) for row in rows)
            if all(row["packs_after"] is not None for row in rows)
            else None
        )
        return {
            "repository_maintenance_budget_seconds": budget,
            "repository_maintenance_budget_exhausted": bool(
                budget_exhausted
                or any(row["maintenance_status"] == "budget-exhausted" for row in rows)
            ),
            "repository_maintenance_attempted": attempted,
            "repository_maintenance_succeeded": succeeded,
            "repository_maintenance_failed": failed,
            "repository_maintenance_timed_out": timed_out,
            "repository_maintenance_skipped_budget": skipped_budget,
            "repository_reclamation_complete": reclamation_complete,
            "repository_bytes_reclaimed": bytes_reclaimed,
            "repository_garbage_entries_removed": garbage_removed,
            "repository_packs_before": packs_before,
            "repository_packs_after": packs_after,
            "repository_maintenance": rows,
        }

    def prune(self, *, target_bytes: int | None = None, timeout: float = 30.0) -> dict[str, Any]:
        maintenance = self._repository_maintenance()
        logical = super().prune(target_bytes=target_bytes, timeout=timeout)
        logical.update(maintenance)
        return logical

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
