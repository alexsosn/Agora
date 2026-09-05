from __future__ import annotations

import threading
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping

from .catalog import Catalog, ResourceSpec
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

    def __init__(self, catalog: Catalog, resolver: ContextFabricResolver, loader: Any):
        self.catalog = catalog
        self.resolver = resolver
        self.loader = loader
        self.store = getattr(resolver, "store", None)
        self._loaded_leases: dict[str, Any] = {}
        self._loaded_names_lock = threading.RLock()
        self._lifecycle_locks = tuple(
            threading.RLock() for _ in range(self._LIFECYCLE_LOCK_STRIPES)
        )

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

    def load(
        self,
        resource_id: str,
        *,
        member_id: str | None = None,
        version: str | None = None,
        source_revision: str | None = None,
        features: str | list[str] | None = None,
        modules: list[str] | None = None,
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
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "member_id": member_id,
            "features": features,
            "modules": modules,
        }
        if version is not None:
            kwargs["version"] = version
        if source_revision is not None:
            kwargs["source_revision"] = source_revision
        result = self.load(resource_id, **kwargs)
        compatible = dict(result)
        compatible["features"] = features
        return compatible
