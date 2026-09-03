from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

from .catalog import Catalog, ResourceSpec
from .resolver import CollectionMember, ContextFabricResolver, PreparedCorpus, dataset_version


class ContextFabricService:
    """Client-neutral operations behind Agora's Context-Fabric MCP tools."""

    def __init__(self, catalog: Catalog, resolver: ContextFabricResolver, loader: Any):
        self.catalog = catalog
        self.resolver = resolver
        self.loader = loader

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
            # Describing a catalog entry must stay deterministic and offline. A
            # configured TF path is packaged metadata and can therefore expose a
            # known default version without resolving upstream HEAD. Floating
            # corpora leave default/availability unknown until prepare/load.
            if resource.tf_path is not None:
                default_version = dataset_version(resource.tf_path)
            registered_modules = [
                self._module_dict(module, default_version)
                for module in self.catalog.modules_for(resource.id)
            ]
            if default_version is not None:
                available_modules = [
                    module
                    for module in registered_modules
                    if module["compatible_with_default"]
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
                {
                    "status": resource.module_status,
                    "coverage": resource.module_coverage,
                }
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
            "verification": {
                "status": resource.verification_status,
                "notes": list(resource.verification_notes),
            },
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

    @staticmethod
    def _member_dict(member: CollectionMember) -> dict[str, Any]:
        return {
            "id": member.id,
            "resource_id": member.resource_id,
            "relative_path": member.relative_path,
            "identity_path": member.identity_path,
            "author": member.author,
            "title": member.title,
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

        members = (
            self.resolver.search_members(resource_id, query)
            if query.strip()
            else self.resolver.list_members(resource_id)
        )
        total = len(members)
        page = members[offset : offset + limit]
        return {
            "resource_id": resource_id,
            "query": query,
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
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        result = self.list_members(
            resource_id,
            query=query,
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
        modules: list[str] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"member_id": member_id, "modules": modules}
        if version is not None:
            kwargs["version"] = version
        prepared = self.resolver.prepare_with_modules(resource_id, **kwargs)
        return self._prepared_dict(prepared)

    @staticmethod
    def _prepared_dict(prepared: PreparedCorpus) -> dict[str, Any]:
        return {
            "resource_id": prepared.resource_id,
            "member_id": prepared.member_id,
            "logical_name": prepared.logical_name,
            "relative_path": prepared.relative_path,
            "version": prepared.version,
            "path": str(prepared.path),
            "source_revision": prepared.source_revision,
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
        features: str | list[str] | None = None,
        modules: list[str] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"member_id": member_id, "modules": modules}
        if version is not None:
            kwargs["version"] = version
        prepared = self.resolver.prepare_with_modules(resource_id, **kwargs)
        info = self.loader.load(
            str(prepared.path),
            name=prepared.logical_name,
            features=features,
        )
        result = self._prepared_dict(prepared)
        result["corpus"] = self._corpus_info(info)
        return result

    def load_resource(
        self,
        resource_id: str,
        *,
        member_id: str | None = None,
        version: str | None = None,
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
        result = self.load(resource_id, **kwargs)
        compatible = dict(result)
        compatible["features"] = features
        return compatible
