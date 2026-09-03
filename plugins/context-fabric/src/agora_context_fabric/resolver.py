from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Iterable

from .catalog import Catalog, ResourceSpec
from .gitstore import GitStore


@dataclass(frozen=True)
class CollectionMember:
    id: str
    resource_id: str
    relative_path: str
    identity_path: str
    author: str | None = None
    title: str | None = None


@dataclass(frozen=True)
class PreparedFeatureModule:
    resource_id: str
    parent_resource_id: str
    module_path: str
    relative_path: str
    path: Path
    source_revision: str | None = None


@dataclass(frozen=True)
class PreparedCorpus:
    resource_id: str
    member_id: str | None
    logical_name: str
    relative_path: str
    path: Path
    source_revision: str | None = None
    modules: tuple[PreparedFeatureModule, ...] = ()


def _member_identity_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip("/")
    marker = "/tf/"
    if marker in normalized:
        return normalized.split(marker, 1)[0]
    parts = PurePosixPath(normalized).parts
    if len(parts) >= 2 and parts[-2] == "tf":
        return "/".join(parts[:-2]) or normalized
    return normalized


def member_id_from_path(path: str) -> str:
    identity = _member_identity_path(path)
    slug = re.sub(r"[^a-z0-9]+", "-", identity.casefold()).strip("-")
    if not slug:
        slug = "member"
    if len(slug) > 72:
        slug = slug[:72].rstrip("-")
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}"


def _natural_tokens(value: str) -> tuple[tuple[int, int | str], ...]:
    tokens: list[tuple[int, int | str]] = []
    for token in re.split(r"(\d+)", value.casefold()):
        if not token:
            continue
        if token.isdigit():
            tokens.append((1, int(token)))
        else:
            tokens.append((0, token))
    return tuple(tokens)


def _dataset_rank(path: str) -> tuple[int, tuple[tuple[int, int | str], ...], int, str]:
    normalized = path.replace("\\", "/").strip("/")
    if normalized == ".":
        return (0, tuple(), 0, normalized)
    marker = "/tf/"
    if normalized.startswith("tf/"):
        version = normalized[3:]
        return (3, _natural_tokens(version), -normalized.count("/"), normalized)
    if marker in normalized:
        version = normalized.rsplit(marker, 1)[1]
        return (2, _natural_tokens(version), -normalized.count("/"), normalized)
    return (1, _natural_tokens(normalized), -normalized.count("/"), normalized)


def select_dataset_root(roots: Iterable[str]) -> str:
    candidates = sorted(set(roots))
    if not candidates:
        raise ValueError("no Text-Fabric dataset roots were discovered")
    return max(candidates, key=_dataset_rank)


def dataset_version(path: str) -> str:
    normalized = path.replace("\\", "/").strip("/")
    if not normalized or normalized == ".":
        return "."
    return PurePosixPath(normalized).name


class ContextFabricResolver:
    def __init__(self, catalog: Catalog, store: GitStore):
        self.catalog = catalog
        self.store = store

    def _repo(self, resource: ResourceSpec) -> tuple[Path, str]:
        kwargs = {"cache_key": resource.id}
        if resource.ref is not None:
            kwargs["ref"] = resource.ref
        repo = self.store.ensure_metadata(resource.repository, **kwargs)
        return repo, self.store.selected_revision(repo)

    @staticmethod
    def _select_resource_root(resource: ResourceSpec, roots: Iterable[str]) -> str:
        candidates = list(roots)
        if resource.tf_path is None:
            return select_dataset_root(candidates)
        normalized = resource.tf_path.replace("\\", "/").strip("/") or "."
        if normalized not in candidates:
            raise ValueError(
                f"configured Text-Fabric path {resource.tf_path!r} was not found for resource {resource.id!r}"
            )
        return normalized

    def _collection_members_from_roots(
        self, resource: ResourceSpec, roots: Iterable[str]
    ) -> list[CollectionMember]:
        grouped: dict[str, list[str]] = {}
        for root in roots:
            identity = _member_identity_path(root)
            grouped.setdefault(identity, []).append(root)

        members: list[CollectionMember] = []
        for identity, versions in grouped.items():
            selected = select_dataset_root(versions)
            parts = PurePosixPath(identity).parts
            author = parts[0] if len(parts) == 2 else None
            title = parts[1] if len(parts) == 2 else None
            members.append(
                CollectionMember(
                    id=member_id_from_path(selected),
                    resource_id=resource.id,
                    relative_path=selected,
                    identity_path=identity,
                    author=author,
                    title=title,
                )
            )
        return sorted(members, key=lambda member: member.relative_path.casefold())

    def list_members(self, resource_id: str) -> list[CollectionMember]:
        resource = self.catalog.get(resource_id)
        if resource.kind != "collection":
            raise ValueError(f"resource {resource_id!r} is not a collection")
        repo, revision = self._repo(resource)
        return self._collection_members_from_roots(
            resource, self.store.dataset_roots(repo, revision)
        )

    def search_members(self, resource_id: str, query: str) -> list[CollectionMember]:
        needle = query.casefold().strip()
        if not needle:
            return self.list_members(resource_id)
        matches: list[CollectionMember] = []
        for member in self.list_members(resource_id):
            haystack = " ".join(
                part
                for part in (
                    member.id,
                    member.relative_path,
                    member.identity_path,
                    member.author,
                    member.title,
                )
                if part
            ).casefold()
            if needle in haystack:
                matches.append(member)
        return matches

    def prepare(self, resource_id: str, *, member_id: str | None = None) -> PreparedCorpus:
        resource = self.catalog.get(resource_id)

        if resource.kind == "feature-module":
            raise ValueError(
                f"feature module {resource_id!r} must be selected while preparing its parent corpus {resource.parent!r}"
            )

        if resource.kind == "collection":
            if not member_id:
                raise ValueError(f"member_id is required for collection resource {resource_id!r}")
            repo, revision = self._repo(resource)
            members = {
                member.id: member
                for member in self._collection_members_from_roots(
                    resource, self.store.dataset_roots(repo, revision)
                )
            }
            try:
                member = members[member_id]
            except KeyError as exc:
                raise KeyError(
                    f"unknown member {member_id!r} in collection {resource_id!r}"
                ) from exc
            local = self.store.materialize(repo, member.relative_path, revision)
            return PreparedCorpus(
                resource_id=resource.id,
                member_id=member.id,
                logical_name=f"{resource.id}:{member.id}",
                relative_path=member.relative_path,
                path=local,
                source_revision=revision,
            )

        if member_id is not None:
            raise ValueError(f"resource {resource_id!r} is not a collection; member_id is invalid")
        repo, revision = self._repo(resource)
        relative = self._select_resource_root(
            resource, self.store.dataset_roots(repo, revision)
        )
        local = self.store.materialize(repo, relative, revision)
        return PreparedCorpus(
            resource_id=resource.id,
            member_id=None,
            logical_name=resource.id,
            relative_path=relative,
            path=local,
            source_revision=revision,
        )

    def _prepare_feature_modules(
        self,
        prepared: PreparedCorpus,
        module_ids: Iterable[str],
    ) -> tuple[PreparedFeatureModule, ...]:
        parent = self.catalog.get(prepared.resource_id)
        if parent.kind != "corpus":
            raise ValueError("feature modules can currently be selected only for corpus resources")

        version = dataset_version(prepared.relative_path)
        seen: set[str] = set()
        selected: list[PreparedFeatureModule] = []
        for module_id in module_ids:
            if module_id in seen:
                raise ValueError(f"feature module {module_id!r} was selected more than once")
            seen.add(module_id)
            module = self.catalog.get(module_id)
            if module.kind != "feature-module":
                raise ValueError(f"resource {module_id!r} is not a feature module")
            if module.parent != parent.id:
                raise ValueError(
                    f"feature module {module_id!r} belongs to {module.parent!r}, not {parent.id!r}"
                )
            if version not in module.parent_versions:
                compatible = ", ".join(module.parent_versions)
                raise ValueError(
                    f"feature module {module_id!r} is not compatible with {parent.id!r} version {version!r}; "
                    f"compatible versions: {compatible}"
                )
            if not module.tf_path or not module.module_path:
                raise ValueError(f"feature module {module_id!r} has incomplete upstream path metadata")
            repo, revision = self._repo(module)
            local = self.store.materialize_feature_module(repo, module.tf_path, revision)
            selected.append(
                PreparedFeatureModule(
                    resource_id=module.id,
                    parent_resource_id=parent.id,
                    module_path=module.module_path,
                    relative_path=module.tf_path,
                    path=local,
                    source_revision=revision,
                )
            )
        return tuple(selected)

    @staticmethod
    def _link_features(source: Path, target: Path) -> None:
        for source_file in sorted(source.glob("*.tf")):
            destination = target / source_file.name
            if destination.exists():
                destination.unlink()
            try:
                os.link(source_file, destination)
            except OSError:
                shutil.copy2(source_file, destination)

    def _overlay(self, prepared: PreparedCorpus, modules: tuple[PreparedFeatureModule, ...]) -> Path:
        digest_input = "\n".join(
            [
                prepared.resource_id,
                prepared.relative_path,
                prepared.source_revision or "",
                *(
                    f"{module.resource_id}:{module.relative_path}:{module.source_revision or ''}"
                    for module in modules
                ),
            ]
        )
        digest = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()[:16]
        overlays = self.store.cache_dir / "overlays"
        overlays.mkdir(parents=True, exist_ok=True)
        destination = overlays / f"{self.store.safe_cache_key(prepared.logical_name)}-{digest}"
        if destination.is_dir():
            return destination

        temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=overlays))
        try:
            self._link_features(prepared.path, temporary)
            for module in modules:
                self._link_features(module.path, temporary)
            if not (temporary / "otype.tf").is_file():
                raise FileNotFoundError("composed Text-Fabric corpus has no otype.tf")
            try:
                temporary.rename(destination)
            except FileExistsError:
                pass
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        return destination

    def prepare_with_modules(
        self,
        resource_id: str,
        *,
        member_id: str | None = None,
        modules: Iterable[str] | None = None,
    ) -> PreparedCorpus:
        prepared = self.prepare(resource_id, member_id=member_id)
        module_ids = tuple(modules or ())
        if not module_ids:
            return prepared
        selected = self._prepare_feature_modules(prepared, module_ids)
        overlay = self._overlay(prepared, selected)
        return replace(prepared, path=overlay, modules=selected)
