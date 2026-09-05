from __future__ import annotations

from dataclasses import dataclass, field
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
    member_index_path: Path | None = None
    member_index_reference: str | None = None
    collection_discovery: str | None = None
    member_id_scheme: str | None = None
    lazy_members: bool = False
    ref: str | None = None
    tf_path: str | None = None
    parent: str | None = None
    parent_versions: tuple[str, ...] = ()
    module_path: str | None = None
    module_status: str | None = None
    module_coverage: str | None = None
    dependencies: tuple[dict[str, Any], ...] = ()
    description: str | None = None
    period: str | None = None
    verification_status: str = "community"
    verification_notes: tuple[str, ...] = ()
    verification_known_issues: tuple[dict[str, Any], ...] = ()
    licenses: dict[str, str] = field(default_factory=dict)
    integration_issues: tuple[str, ...] = ()
    source_snapshot: dict[str, Any] = field(default_factory=dict)


class Catalog:
    def __init__(self, resources: Iterable[ResourceSpec]):
        self._resources = list(resources)
        self._by_id = {resource.id: resource for resource in self._resources}
        if len(self._by_id) != len(self._resources):
            raise ValueError("duplicate Context-Fabric resource IDs")
        self._modules_by_parent: dict[str, list[ResourceSpec]] = {}
        for resource in self._resources:
            if resource.kind == "feature-module" and resource.parent:
                self._modules_by_parent.setdefault(resource.parent, []).append(resource)
        for modules in self._modules_by_parent.values():
            modules.sort(key=lambda item: item.id.casefold())

    @staticmethod
    def _resources_from_document(
        doc: dict[str, Any],
        *,
        base_dir: Path = Path("."),
        bundled_collection_index_dir: Path | None = None,
    ) -> list[ResourceSpec]:
        resources: list[ResourceSpec] = []
        for item in doc.get("resources", []):
            if item.get("plugin") != "context-fabric":
                continue
            upstream = item.get("upstream") or {}
            repository = upstream.get("repository")
            if not repository:
                raise ValueError(f"resource {item.get('id')!r} has no upstream repository")
            if item.get("kind") == "feature-module":
                missing = [
                    key
                    for key in ("module", "tf_path")
                    if not upstream.get(key)
                ]
                if missing:
                    rendered = ", ".join(f"upstream.{key}" for key in missing)
                    raise ValueError(
                        f"Context-Fabric feature module {item.get('id')!r} requires {rendered}"
                    )
            collection = item.get("collection") or {}
            member_index_reference = collection.get("member_index")
            member_index_path: Path | None = None
            if member_index_reference:
                if bundled_collection_index_dir is not None:
                    member_index_path = bundled_collection_index_dir / Path(member_index_reference).name
                else:
                    member_index_path = base_dir / member_index_reference
            compatibility = item.get("compatibility") or {}
            module = item.get("module") or {}
            verification = item.get("verification") or {}
            notes = verification.get("notes") or []
            if isinstance(notes, str):
                notes = [notes]
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
                    member_index=member_index_reference,
                    member_index_path=member_index_path,
                    member_index_reference=member_index_reference,
                    collection_discovery=collection.get("discovery"),
                    member_id_scheme=collection.get("member_id_scheme"),
                    lazy_members=bool(collection.get("lazy_members", False)),
                    ref=upstream.get("ref"),
                    tf_path=upstream.get("tf_path"),
                    parent=item.get("parent"),
                    parent_versions=tuple(str(value) for value in compatibility.get("parent_versions", [])),
                    module_path=upstream.get("module"),
                    module_status=module.get("status"),
                    module_coverage=module.get("coverage"),
                    dependencies=tuple(dict(value) for value in upstream.get("dependencies", [])),
                    description=item.get("description"),
                    period=item.get("period"),
                    verification_status=verification.get("status", "community"),
                    verification_notes=tuple(notes),
                    verification_known_issues=tuple(
                        dict(value)
                        for value in verification.get("known_issues", [])
                        if isinstance(value, dict)
                    ),
                    licenses=dict(item.get("licenses") or {}),
                    integration_issues=tuple(item.get("integration_issues") or ()),
                    source_snapshot=dict(item.get("source_snapshot") or {}),
                )
            )
        return resources

    @classmethod
    def _from_documents(
        cls,
        paths: Iterable[Path],
        *,
        base_dir: Path,
        bundled_collection_index_dir: Path | None = None,
    ) -> "Catalog":
        resources: list[ResourceSpec] = []
        for path in paths:
            if not path.is_file():
                continue
            with path.open("r", encoding="utf-8") as fh:
                doc = yaml.safe_load(fh)
            resources.extend(
                cls._resources_from_document(
                    doc,
                    base_dir=base_dir,
                    bundled_collection_index_dir=bundled_collection_index_dir,
                )
            )
        return cls(resources)

    @classmethod
    def from_registry(cls, root: Path) -> "Catalog":
        root = Path(root)
        return cls._from_documents(
            (
                root / "registry" / "resources.yaml",
                root / "registry" / "feature-modules.yaml",
            ),
            base_dir=root,
        )

    @classmethod
    def from_plugin_root(cls, plugin_root: Path) -> "Catalog":
        plugin_root = Path(plugin_root)
        return cls._from_documents(
            (
                plugin_root / "resources" / "catalog.yaml",
                plugin_root / "resources" / "feature-modules.yaml",
            ),
            base_dir=plugin_root,
            bundled_collection_index_dir=plugin_root / "resources" / "collections",
        )

    def ids(self) -> list[str]:
        return [resource.id for resource in self._resources]

    def resources(self) -> list[ResourceSpec]:
        return list(self._resources)

    def modules_for(self, parent_id: str) -> list[ResourceSpec]:
        return list(self._modules_by_parent.get(parent_id, ()))

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
                    resource.description or "",
                    resource.period or "",
                    resource.repository,
                    resource.parent or "",
                    resource.module_path or "",
                    resource.module_status or "",
                    resource.module_coverage or "",
                    *resource.languages,
                    *resource.disciplines,
                    *resource.integration_issues,
                ]
            ).casefold()
            if needle and needle not in haystack:
                continue
            matches.append(resource)
        return matches

    def __iter__(self) -> Iterator[ResourceSpec]:
        return iter(self._resources)
