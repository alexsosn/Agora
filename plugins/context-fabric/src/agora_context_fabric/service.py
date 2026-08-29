from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

from .catalog import Catalog, ResourceSpec
from .resolver import CollectionMember, ContextFabricResolver, PreparedCorpus


class ContextFabricService:
    """Client-neutral operations behind Agora's Context-Fabric MCP tools."""

    def __init__(self, catalog: Catalog, resolver: ContextFabricResolver, loader: Any):
        self.catalog = catalog
        self.resolver = resolver
        self.loader = loader

    @staticmethod
    def _resource_dict(resource: ResourceSpec) -> dict[str, Any]:
        return {
            "id": resource.id,
            "name": resource.name,
            "kind": resource.kind,
            "repository": resource.repository,
            "languages": list(resource.languages),
            "disciplines": list(resource.disciplines),
            "member_index": resource.member_index,
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
        return [
            self._resource_dict(resource)
            for resource in self.catalog.search(
                query,
                language=language,
                discipline=discipline,
                kind=kind,
            )
        ]

    def describe_resource(self, resource_id: str) -> dict[str, Any]:
        return self._resource_dict(self.catalog.get(resource_id))

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

    def prepare(
        self,
        resource_id: str,
        *,
        member_id: str | None = None,
    ) -> dict[str, Any]:
        prepared = self.resolver.prepare(resource_id, member_id=member_id)
        return self._prepared_dict(prepared)

    @staticmethod
    def _prepared_dict(prepared: PreparedCorpus) -> dict[str, Any]:
        return {
            "resource_id": prepared.resource_id,
            "member_id": prepared.member_id,
            "logical_name": prepared.logical_name,
            "relative_path": prepared.relative_path,
            "path": str(prepared.path),
        }

    def load(
        self,
        resource_id: str,
        *,
        member_id: str | None = None,
        features: str | list[str] | None = None,
    ) -> dict[str, Any]:
        prepared = self.resolver.prepare(resource_id, member_id=member_id)
        info = self.loader.load(
            str(prepared.path),
            name=prepared.logical_name,
            features=features,
        )
        result = self._prepared_dict(prepared)
        result["corpus"] = self._corpus_info(info)
        return result
