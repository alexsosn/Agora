from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml


@dataclass(frozen=True)
class ResourceSpec:
    id: str
    name: str
    plugin: str
    provider: str
    kind: str
    repository: str
    languages: tuple[str, ...]
    disciplines: tuple[str, ...]
    member_index: str | None = None


class Catalog:
    def __init__(self, resources: Iterable[ResourceSpec]):
        self._resources = list(resources)
        self._by_id = {resource.id: resource for resource in self._resources}
        if len(self._by_id) != len(self._resources):
            raise ValueError("duplicate Context-Fabric resource IDs")

    @staticmethod
    def _resources_from_document(doc: dict[str, Any]) -> list[ResourceSpec]:
        resources: list[ResourceSpec] = []
        for item in doc.get("resources", []):
            if item.get("plugin") != "context-fabric":
                continue
            upstream = item.get("upstream") or {}
            repository = upstream.get("repository")
            if not repository:
                raise ValueError(f"resource {item.get('id')!r} has no upstream repository")
            collection = item.get("collection") or {}
            resources.append(
                ResourceSpec(
                    id=item["id"],
                    name=item["name"],
                    plugin=item["plugin"],
                    provider=item["provider"],
                    kind=item["kind"],
                    repository=repository,
                    languages=tuple(item.get("languages", [])),
                    disciplines=tuple(item.get("disciplines", [])),
                    member_index=collection.get("member_index"),
                )
            )
        return resources

    @classmethod
    def from_registry(cls, root: Path) -> "Catalog":
        root = Path(root)
        with (root / "registry" / "resources.yaml").open("r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        return cls(cls._resources_from_document(doc))

    @classmethod
    def from_plugin_root(cls, plugin_root: Path) -> "Catalog":
        plugin_root = Path(plugin_root)
        with (plugin_root / "resources" / "catalog.yaml").open("r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        return cls(cls._resources_from_document(doc))

    def ids(self) -> list[str]:
        return [resource.id for resource in self._resources]

    def resources(self) -> list[ResourceSpec]:
        return list(self._resources)

    def get(self, resource_id: str) -> ResourceSpec:
        try:
            return self._by_id[resource_id]
        except KeyError as exc:
            raise KeyError(f"unknown Context-Fabric resource: {resource_id}") from exc

    def search(
        self,
        query: str = "",
        *,
        language: str | None = None,
        discipline: str | None = None,
        kind: str | None = None,
    ) -> list[ResourceSpec]:
        needle = query.casefold().strip()
        matches: list[ResourceSpec] = []
        for resource in self._resources:
            if language and language not in resource.languages:
                continue
            if discipline and discipline not in resource.disciplines:
                continue
            if kind and kind != resource.kind:
                continue
            haystack = " ".join(
                [
                    resource.id,
                    resource.name,
                    resource.repository,
                    *resource.languages,
                    *resource.disciplines,
                ]
            ).casefold()
            if needle and needle not in haystack:
                continue
            matches.append(resource)
        return matches

    def __iter__(self) -> Iterator[ResourceSpec]:
        return iter(self._resources)
