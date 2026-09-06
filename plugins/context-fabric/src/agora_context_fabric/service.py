from __future__ import annotations

import shutil
import threading
import time
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping

from .catalog import Catalog, ResourceSpec
from .load_safety import (
    cfm_marker,
    cfm_version_dir,
    compile_budget_bytes,
    compile_timeout_seconds,
    current_cfm_version,
    directory_bytes,
    source_tf_bytes,
)
from .resolver import (
    CollectionMember,
    ContextFabricResolver,
    PreparedCorpus,
    dataset_version,
    member_id_from_path,
)


class ContextFabricService:
    """Client-neutral operations behind Agora's Context-Fabric MCP tools."""

    _LIFECYCLE_LOCK_STRIPES = 64
    _COMPILE_LOCK_TIMEOUT_SECONDS = 0.25

    def __init__(
        self,
        catalog: Catalog,
        resolver: ContextFabricResolver,
        loader: Any,
        *,
        cold_compiler: Any | None = None,
        cfm_version: str | None = None,
    ):
        self.catalog = catalog
        self.resolver = resolver
        self.loader = loader
        self.store = getattr(resolver, "store", None)
        self.cold_compiler = cold_compiler
        self.cfm_version = (
            cfm_version
            if cfm_version is not None
            else (current_cfm_version() if cold_compiler is not None else None)
        )
        self._loaded_leases: dict[str, Any] = {}
        self._loaded_names_lock = threading.RLock()
        self._lifecycle_locks = tuple(
            threading.RLock() for _ in range(self._LIFECYCLE_LOCK_STRIPES)
        )
        self._active_loads: dict[str, dict[str, Any]] = {}
        self._active_by_path: dict[str, str] = {}
        self._active_loads_lock = threading.RLock()

    @staticmethod
    def _module_dict(module: ResourceSpec, default_version: str | None = None) -> dict[str, Any]:
        return {
            "id": module.id,
            "name": module.name,
            "status": module.module_status,
            "coverage": module.module_coverage,
            "compatible_parent_versions": list(module.parent_versions),
            "compatible_with_default": (
                default_version in module.parent_versions if default_version is not None else None
            ),
        }

    @staticmethod
    def _known_issue_map(resource: ResourceSpec) -> dict[str, dict[str, Any]]:
        return {
            issue["id"]: dict(issue)
            for issue in resource.verification_known_issues
            if isinstance(issue.get("id"), str)
        }

    def _resource_dict(
        self,
        resource: ResourceSpec,
        *,
        resolve_modules: bool = False,
    ) -> dict[str, Any]:
        default_version: str | None = None
        registered_modules: list[dict[str, Any]] | None = None
        available_modules: list[dict[str, Any]] | None = None
        if resolve_modules and resource.kind == "corpus":
            if resource.tf_path is not None:
                default_version = dataset_version(resource.tf_path)
            registered_modules = [
                self._module_dict(module, default_version)
                for module in self.catalog.modules_for(resource.id)
            ]
            if default_version is not None:
                available_modules = [
                    module for module in registered_modules if module["compatible_with_default"]
                ]

        verification: dict[str, Any] = {
            "status": resource.verification_status,
            "notes": list(resource.verification_notes),
        }
        if resource.verification_known_issues:
            verification["known_issues"] = [
                dict(issue) for issue in resource.verification_known_issues
            ]

        return {
            "id": resource.id,
            "name": resource.name,
            "description": resource.description,
            "period": resource.period,
            "kind": resource.kind,
            "repository": resource.repository,
            "languages": list(resource.languages),
            "disciplines": list(resource.disciplines),
            "parent": resource.parent,
            "compatibility": (
                {"parent_versions": list(resource.parent_versions)}
                if resource.kind == "feature-module"
                else None
            ),
            "module": (
                {"status": resource.module_status, "coverage": resource.module_coverage}
                if resource.kind == "feature-module"
                else None
            ),
            "default_version": default_version,
            "available_modules": available_modules,
            "registered_modules": registered_modules,
            "member_index": resource.member_index,
            "collection": (
                {
                    "discovery": resource.collection_discovery,
                    "member_id_scheme": resource.member_id_scheme,
                    "lazy_members": resource.lazy_members,
                    "member_index": resource.member_index,
                }
                if resource.kind == "collection"
                else None
            ),
            "verification": verification,
            "licenses": dict(resource.licenses),
            "integration_issues": list(resource.integration_issues),
            "source_snapshot": dict(resource.source_snapshot),
            "source": {
                "repository": resource.repository,
                "configured_ref": resource.ref,
                "tf_path": resource.tf_path,
                "module": resource.module_path,
                "dependencies": [dict(value) for value in resource.dependencies],
            },
        }

    def _member_dict(self, member: CollectionMember) -> dict[str, Any]:
        resource = self.catalog.get(member.resource_id)
        issue_by_id = self._known_issue_map(resource)
        known_issues: list[dict[str, Any]] = []
        for issue_id in member.verification_known_issues:
            issue = issue_by_id.get(issue_id)
            if issue is None:
                raise RuntimeError(
                    f"collection member {member.id!r} references unknown known issue {issue_id!r} "
                    f"for resource {member.resource_id!r}"
                )
            known_issues.append(dict(issue))
        verification: dict[str, Any] = {
            "status": member.verification_status,
            "evidence": [
                {"check_id": check_id}
                for check_id in member.verification_evidence
            ],
            "notes": list(member.verification_notes),
        }
        if known_issues:
            verification["known_issues"] = known_issues
        return {
            "id": member.id,
            "resource_id": member.resource_id,
            "relative_path": member.relative_path,
            "identity_path": member.identity_path,
            "source_revision": member.source_revision,
            "author": member.author,
            "title": member.title,
            "canonical_id": member.canonical_id,
            "edition": member.edition,
            "verification": verification,
        }

    @staticmethod
    def _corpus_info(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, Mapping):
            return dict(value)
        if is_dataclass(value):
            return asdict(value)
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            return model_dump()
        as_dict = getattr(value, "dict", None)
        if callable(as_dict):
            return as_dict()
        return str(value)

    def _require_store(self) -> Any:
        if self.store is None:
            raise RuntimeError("Context-Fabric cache store is not configured")
        return self.store

    def _lifecycle_lock(self, logical_name: str) -> threading.RLock:
        return self._lifecycle_locks[hash(logical_name) % len(self._lifecycle_locks)]

    def _warm_marker(self, path: Path) -> Path | None:
        if self.cold_compiler is None:
            return None
        if self.cfm_version is None:
            raise RuntimeError("Context-Fabric CFM version is unavailable for cold-load safety")
        return cfm_marker(path, self.cfm_version)

    def _is_warm(self, path: Path) -> bool:
        marker = self._warm_marker(path)
        return marker is not None and marker.is_file()

    def _reserve_active_load(
        self,
        prepared: PreparedCorpus,
        *,
        source_bytes: int,
        budget_bytes: int,
        timeout_seconds: float,
    ) -> tuple[str, threading.Event]:
        path_key = str(Path(prepared.path).resolve())
        with self._active_loads_lock:
            existing_id = self._active_by_path.get(path_key)
            if existing_id is not None:
                raise RuntimeError(
                    f"Context-Fabric cold load is already active for {prepared.logical_name!r} "
                    f"(load_id={existing_id}); inspect corpus_cache_status instead of retrying"
                )
            load_id = uuid.uuid4().hex
            cancel_event = threading.Event()
            try:
                free_bytes = int(shutil.disk_usage(prepared.path).free)
            except OSError:
                free_bytes = None
            self._active_loads[load_id] = {
                "load_id": load_id,
                "path_key": path_key,
                "resource_id": prepared.resource_id,
                "member_id": prepared.member_id,
                "logical_name": prepared.logical_name,
                "path": str(prepared.path),
                "phase": "preflight",
                "started_monotonic": time.monotonic(),
                "source_bytes": source_bytes,
                "observed_compiled_bytes": (
                    directory_bytes(cfm_version_dir(prepared.path, self.cfm_version))
                    if self.cfm_version is not None
                    else 0
                ),
                "compile_budget_bytes": budget_bytes,
                "observed_free_bytes": free_bytes,
                "min_free_bytes": int(getattr(self.store, "min_free_bytes", 0)),
                "timeout_seconds": timeout_seconds,
                "cancel_event": cancel_event,
            }
            self._active_by_path[path_key] = load_id
            return load_id, cancel_event

    def _update_active(self, load_id: str, **values: Any) -> None:
        with self._active_loads_lock:
            record = self._active_loads.get(load_id)
            if record is not None:
                record.update(values)

    def _progress_active(self, load_id: str, observation: dict[str, Any]) -> None:
        allowed = {
            key: observation[key]
            for key in (
                "observed_compiled_bytes",
                "observed_free_bytes",
                "elapsed_seconds",
            )
            if key in observation
        }
        if allowed:
            self._update_active(load_id, **allowed)

    def _clear_active(self, load_id: str) -> None:
        with self._active_loads_lock:
            record = self._active_loads.pop(load_id, None)
            if record is None:
                return
            path_key = str(record["path_key"])
            if self._active_by_path.get(path_key) == load_id:
                self._active_by_path.pop(path_key, None)

    def _active_snapshot(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        with self._active_loads_lock:
            records = [dict(record) for record in self._active_loads.values()]
        result: list[dict[str, Any]] = []
        for record in records:
            event = record.pop("cancel_event")
            started = float(record.pop("started_monotonic"))
            record.pop("path_key", None)
            record["elapsed_seconds"] = max(
                float(record.get("elapsed_seconds", 0.0)),
                max(0.0, now - started),
            )
            record["cancellation_capable"] = record.get("phase") in {
                "preflight",
                "compiling",
            }
            record["cancellation_requested"] = bool(event.is_set())
            result.append(record)
        return sorted(result, key=lambda item: str(item["load_id"]))

    def _cleanup_incomplete_current_cfm(self, path: Path) -> None:
        if self.cfm_version is None:
            return
        marker = cfm_marker(path, self.cfm_version)
        if marker.is_file():
            return
        current = cfm_version_dir(path, self.cfm_version)
        if not current.exists():
            return
        if current.is_symlink() or current.parent.is_symlink():
            raise RuntimeError(
                f"refusing to clean unsafe incomplete Context-Fabric cache path: {current}"
            )
        try:
            shutil.rmtree(current)
        except Exception as exc:
            raise RuntimeError(
                "failed to clean incomplete Context-Fabric compiled output; residual path "
                f"remains at {current}"
            ) from exc
        if current.exists():
            raise RuntimeError(
                "failed to clean incomplete Context-Fabric compiled output; residual path "
                f"remains at {current}"
            )

    def list_resources(
        self,
        query: str = "",
        *,
        language: str | None = None,
        discipline: str | None = None,
        kind: str | None = None,
    ) -> list[dict[str, Any]]:
        matches = self.catalog.search(
            query,
            language=language,
            discipline=discipline,
            kind=kind,
        )
        if kind is None:
            matches = [resource for resource in matches if resource.kind != "feature-module"]
        return [self._resource_dict(resource) for resource in matches]

    def describe_resource(self, resource_id: str) -> dict[str, Any]:
        return self._resource_dict(self.catalog.get(resource_id), resolve_modules=True)

    def list_members(
        self,
        resource_id: str,
        *,
        query: str = "",
        source_revision: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        if offset < 0:
            raise ValueError("offset must be >= 0")
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if limit > 100:
            raise ValueError("limit must be <= 100")
        resource = self.catalog.get(resource_id)
        if resource.kind != "collection":
            raise ValueError(f"resource {resource_id!r} is not a collection")

        resolve_members = getattr(self.resolver, "resolve_members", None)
        if callable(resolve_members):
            listing = resolve_members(
                resource_id,
                query=query,
                source_revision=source_revision,
            )
            members = list(listing.members)
            resolved_source_revision = listing.source_revision
        else:
            if source_revision is not None:
                raise RuntimeError(
                    "configured Context-Fabric resolver cannot honor collection source_revision"
                )
            members = (
                self.resolver.search_members(resource_id, query)
                if query.strip()
                else self.resolver.list_members(resource_id)
            )
            revisions = {
                member.source_revision
                for member in members
                if getattr(member, "source_revision", None)
            }
            resolved_source_revision = next(iter(revisions)) if len(revisions) == 1 else None

        total = len(members)
        page = members[offset : offset + limit]
        return {
            "resource_id": resource_id,
            "query": query,
            "source_revision": resolved_source_revision,
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(page) < total,
            "members": [self._member_dict(member) for member in page],
        }

    def list_collection_members(
        self,
        resource_id: str,
        *,
        query: str = "",
        source_revision: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        result = self.list_members(
            resource_id,
            query=query,
            source_revision=source_revision,
            offset=offset,
            limit=limit,
        )
        compatible = dict(result)
        compatible["items"] = compatible.pop("members")
        return compatible

    def prepare(
        self,
        resource_id: str,
        *,
        member_id: str | None = None,
        version: str | None = None,
        source_revision: str | None = None,
        modules: list[str] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"member_id": member_id, "modules": modules}
        if version is not None:
            kwargs["version"] = version
        if source_revision is not None:
            kwargs["source_revision"] = source_revision
        prepared = self.resolver.prepare_with_modules(resource_id, **kwargs)
        return self._prepared_dict(
            prepared,
            cache_residency="evictable" if self.store is not None else "unmanaged",
        )

    @staticmethod
    def _prepared_dict(
        prepared: PreparedCorpus,
        *,
        cache_residency: str,
    ) -> dict[str, Any]:
        return {
            "resource_id": prepared.resource_id,
            "member_id": prepared.member_id,
            "logical_name": prepared.logical_name,
            "relative_path": prepared.relative_path,
            "version": prepared.version,
            "path": str(prepared.path),
            "source_revision": prepared.source_revision,
            "cache_residency": cache_residency,
            "modules": [
                {
                    "id": module.resource_id,
                    "module": module.module_path,
                    "relative_path": module.relative_path,
                    "source_revision": module.source_revision,
                }
                for module in prepared.modules
            ],
        }

    def _parent_warm_load(
        self,
        prepared: PreparedCorpus,
        new_lease: Any,
        *,
        features: str | list[str] | None,
    ) -> dict[str, Any]:
        logical_name = prepared.logical_name
        with self._lifecycle_lock(logical_name):
            with self._loaded_names_lock:
                previous_lease = self._loaded_leases.get(logical_name)

            try:
                info = self.loader.load(
                    str(prepared.path),
                    name=logical_name,
                    features=features,
                )
            except Exception:
                new_lease.release()
                raise

            with self._loaded_names_lock:
                self._loaded_leases[logical_name] = new_lease
            if previous_lease is not None:
                previous_lease.release()

            result = self._prepared_dict(prepared, cache_residency="leased")
            result["corpus"] = self._corpus_info(info)
            return result

    def load(
        self,
        resource_id: str,
        *,
        member_id: str | None = None,
        version: str | None = None,
        source_revision: str | None = None,
        features: str | list[str] | None = None,
        modules: list[str] | None = None,
        max_compile_gb: float | None = None,
        max_compile_minutes: float | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"member_id": member_id, "modules": modules}
        if version is not None:
            kwargs["version"] = version
        if source_revision is not None:
            kwargs["source_revision"] = source_revision

        if self.store is None:
            prepared = self.resolver.prepare_with_modules(resource_id, **kwargs)
            info = self.loader.load(
                str(prepared.path),
                name=prepared.logical_name,
                features=features,
            )
            result = self._prepared_dict(prepared, cache_residency="unmanaged")
            result["corpus"] = self._corpus_info(info)
            return result

        with self.store.cache_transition():
            prepared = self.resolver.prepare_with_modules(resource_id, **kwargs)
            new_lease = self.store.acquire_cache_lease(
                prepared.path,
                transition_held=True,
            )

        if self.cold_compiler is None:
            return self._parent_warm_load(
                prepared,
                new_lease,
                features=features,
            )

        active_id: str | None = None
        installed_lease = False
        try:
            if not self._is_warm(prepared.path):
                source_bytes = source_tf_bytes(prepared.path)
                budget_bytes = compile_budget_bytes(
                    source_bytes,
                    max_compile_gb=max_compile_gb,
                )
                timeout_seconds = compile_timeout_seconds(
                    max_compile_minutes=max_compile_minutes,
                )
                active_id, cancel_event = self._reserve_active_load(
                    prepared,
                    source_bytes=source_bytes,
                    budget_bytes=budget_bytes,
                    timeout_seconds=timeout_seconds,
                )

                try:
                    compile_context = self.store.compile_lock(
                        prepared.path,
                        timeout=self._COMPILE_LOCK_TIMEOUT_SECONDS,
                    )
                    with compile_context:
                        # Another process can finish between the initial warm
                        # check and our acquisition of the exact-object lock.
                        if not self._is_warm(prepared.path):
                            # Remove only stale/incomplete current-format output
                            # before assigning this attempt ownership.
                            self._cleanup_incomplete_current_cfm(prepared.path)
                            self._update_active(active_id, phase="compiling")
                            try:
                                self.cold_compiler.run(
                                    path=prepared.path,
                                    logical_name=prepared.logical_name,
                                    features=features,
                                    compile_budget_bytes=budget_bytes,
                                    timeout_seconds=timeout_seconds,
                                    min_free_bytes=int(self.store.min_free_bytes),
                                    cancel_event=cancel_event,
                                    progress=lambda observation: self._progress_active(
                                        active_id,
                                        observation,
                                    ),
                                )
                            except BaseException:
                                try:
                                    self._cleanup_incomplete_current_cfm(prepared.path)
                                except BaseException as cleanup_exc:
                                    raise RuntimeError(
                                        "Context-Fabric cold load failed and cleanup also failed; "
                                        f"residual compiled output may remain under "
                                        f"{cfm_version_dir(prepared.path, self.cfm_version)}"
                                    ) from cleanup_exc
                                raise

                            marker = self._warm_marker(prepared.path)
                            if marker is None or not marker.is_file():
                                self._cleanup_incomplete_current_cfm(prepared.path)
                                raise RuntimeError(
                                    "contained Context-Fabric cold-load worker exited successfully "
                                    "without the current-format completion marker; refusing to "
                                    "fall back to an in-process cold compile"
                                )
                        self._update_active(active_id, phase="warm-load")
                except TimeoutError as exc:
                    raise RuntimeError(
                        "another Agora process is already compiling this exact Context-Fabric "
                        f"cache object for {prepared.logical_name!r}; retry after it completes"
                    ) from exc

            result = self._parent_warm_load(
                prepared,
                new_lease,
                features=features,
            )
            installed_lease = True
            return result
        finally:
            if active_id is not None:
                self._clear_active(active_id)
            if not installed_lease:
                # _parent_warm_load releases on loader failure. CacheLease.release
                # is idempotent, so this also covers every pre-warm failure.
                new_lease.release()

    def cancel_load(self, load_id: str) -> dict[str, Any]:
        with self._active_loads_lock:
            record = self._active_loads.get(load_id)
            if record is None:
                return {
                    "found": False,
                    "load_id": load_id,
                    "cancellation_requested": False,
                    "phase": None,
                }
            phase = str(record["phase"])
            event = record["cancel_event"]
            cancellation_capable = phase in {"preflight", "compiling"}
            if cancellation_capable:
                event.set()
            return {
                "found": True,
                "load_id": load_id,
                "cancellation_requested": bool(event.is_set()) if cancellation_capable else False,
                "phase": phase,
            }

    def unload(self, logical_name: str) -> dict[str, Any]:
        """Unload one Agora-loaded corpus by the logical name returned by load."""
        if not logical_name:
            raise ValueError("logical_name is required")
        with self._lifecycle_lock(logical_name):
            with self._loaded_names_lock:
                lease = self._loaded_leases.get(logical_name)
            if lease is None:
                return {
                    "logical_name": logical_name,
                    "was_loaded": False,
                    "released_path": None,
                    "loaded": False,
                }

            self.loader.unload(logical_name)
            with self._loaded_names_lock:
                current = self._loaded_leases.get(logical_name)
                if current is lease:
                    self._loaded_leases.pop(logical_name, None)
            lease.release()
            return {
                "logical_name": logical_name,
                "was_loaded": True,
                "released_path": str(lease.path),
                "loaded": False,
            }

    def cache_status(self) -> dict[str, Any]:
        store = self._require_store()
        result = dict(store.cache_status())
        with self._loaded_names_lock:
            loaded = dict(self._loaded_leases)
        result["loaded_corpora"] = [
            {"logical_name": name, "path": str(lease.path)}
            for name, lease in sorted(loaded.items())
        ]
        result["active_loads"] = self._active_snapshot()
        return result

    def prune_cache(self, *, target_bytes: int | None = None) -> dict[str, Any]:
        store = self._require_store()
        result = dict(store.prune(target_bytes=target_bytes))
        result["cache"] = self.cache_status()
        return result

    def remove_cached(
        self,
        resource_id: str,
        *,
        member_id: str | None = None,
        source_revision: str | None = None,
    ) -> dict[str, Any]:
        store = self._require_store()
        resource = self.catalog.get(resource_id)
        if resource.kind != "collection" and member_id is not None:
            raise ValueError(f"resource {resource_id!r} is not a collection; member_id is invalid")

        matched: list[dict[str, Any]] = []
        for entry in store.cache_entries(resource_id):
            if source_revision is not None and entry["revision"] != source_revision:
                continue
            if member_id is not None:
                if entry["kind"] != "corpus-snapshot":
                    continue
                relative_path = entry.get("relative_path")
                if not isinstance(relative_path, str) or member_id_from_path(relative_path) != member_id:
                    continue
            matched.append(entry)

        result = store.remove_cache_objects(
            [Path(str(entry["path"])) for entry in matched]
        )
        blocked = int(result.get("blocked_by_transition", 0))
        return {
            "resource_id": resource_id,
            "member_id": member_id,
            "source_revision": source_revision,
            "matched_entries": len(matched),
            "matched_bytes": sum(int(entry["size_bytes"]) for entry in matched),
            **result,
            "complete": result["skipped_in_use"] == 0 and blocked == 0,
        }

    def load_resource(
        self,
        resource_id: str,
        *,
        member_id: str | None = None,
        version: str | None = None,
        source_revision: str | None = None,
        features: str | list[str] | None = None,
        modules: list[str] | None = None,
        max_compile_gb: float | None = None,
        max_compile_minutes: float | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "member_id": member_id,
            "features": features,
            "modules": modules,
            "max_compile_gb": max_compile_gb,
            "max_compile_minutes": max_compile_minutes,
        }
        if version is not None:
            kwargs["version"] = version
        if source_revision is not None:
            kwargs["source_revision"] = source_revision
        result = self.load(resource_id, **kwargs)
        compatible = dict(result)
        compatible["features"] = features
        return compatible
