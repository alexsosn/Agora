from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Iterable

from .catalog import Catalog, ResourceSpec
from .collection_index import (
    CollectionIndexManager,
    member_id_from_identity,
    member_identity_path,
)
from .gitstore import GitStore


_IMMUTABLE_REVISION_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")


@dataclass(frozen=True)
class CollectionMember:
    id: str
    resource_id: str
    relative_path: str
    identity_path: str
    author: str | None = None
    title: str | None = None
    source_revision: str | None = None


@dataclass(frozen=True)
class CollectionMemberListing:
    source_revision: str
    members: tuple[CollectionMember, ...]


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
    version: str | None = None
    source_revision: str | None = None
    modules: tuple[PreparedFeatureModule, ...] = ()


def member_id_from_path(path: str) -> str:
    """Preserve the historical public member-ID helper over the shared index logic."""
    return member_id_from_identity(member_identity_path(path))


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


def select_dataset_version(roots: Iterable[str], version: str) -> str:
    candidates = [root for root in roots if dataset_version(root) == version]
    if not candidates:
        available = sorted({dataset_version(root) for root in roots}, key=_natural_tokens)
        rendered = ", ".join(available) if available else "none"
        raise ValueError(
            f"Text-Fabric dataset version {version!r} was not found; available versions: {rendered}"
        )
    return select_dataset_root(candidates)


class ContextFabricResolver:
    def __init__(self, catalog: Catalog, store: GitStore):
        self.catalog = catalog
        self.store = store
        self._collection_indexes: CollectionIndexManager | None = None

    def _collection_index_manager(self) -> CollectionIndexManager:
        if self._collection_indexes is None:
            self._collection_indexes = CollectionIndexManager(self.store)
        return self._collection_indexes

    def _repo(self, resource: ResourceSpec) -> tuple[Path, str]:
        kwargs = {"cache_key": resource.id}
        if resource.ref is not None:
            kwargs["ref"] = resource.ref
        repo = self.store.ensure_metadata(resource.repository, **kwargs)
        return repo, self.store.selected_revision(repo)

    def _collection_repo(
        self,
        resource: ResourceSpec,
        source_revision: str | None,
    ) -> tuple[Path, str]:
        if source_revision is None:
            return self._repo(resource)
        if not _IMMUTABLE_REVISION_RE.fullmatch(source_revision):
            raise ValueError(
                "source_revision must be an immutable commit id "
                "(40 or 64 hexadecimal characters)"
            )
        repo = self.store.repositories_dir / self.store.safe_cache_key(resource.id)
        if not (repo / ".git").is_dir():
            raise ValueError(
                f"source revision {source_revision!r} is not available in the cached repository "
                f"for collection {resource.id!r}; omit source_revision to resolve current upstream state"
            )
        try:
            resolved = self.store._resolved_revision(repo, source_revision)
        except subprocess.CalledProcessError as exc:
            raise ValueError(
                f"source revision {source_revision!r} is not available in the cached repository "
                f"for collection {resource.id!r}; no fallback to current upstream state was attempted"
            ) from exc
        return repo, resolved

    def _collection_index(
        self,
        resource: ResourceSpec,
        repo: Path,
        revision: str,
        *,
        requested_revision: str | None,
    ):
        try:
            return self._collection_index_manager().resolve(
                collection_id=resource.id,
                languages=resource.languages,
                repo=repo,
                source_revision=revision,
                installed_index=resource.member_index_path or resource.member_index,
            )
        except subprocess.CalledProcessError as exc:
            if requested_revision is None:
                raise
            raise ValueError(
                f"source revision {requested_revision!r} is not available in the cached repository "
                f"for collection {resource.id!r}; no fallback to current upstream state was attempted"
            ) from exc

    @staticmethod
    def _member_from_index(resource: ResourceSpec, member, revision: str) -> CollectionMember:
        return CollectionMember(
            id=member.id,
            resource_id=resource.id,
            relative_path=member.tf_path,
            identity_path=member.path,
            author=member.author,
            title=member.title,
            source_revision=revision,
        )

    @staticmethod
    def _select_resource_root(
        resource: ResourceSpec,
        roots: Iterable[str],
        version: str | None = None,
    ) -> str:
        candidates = list(roots)
        if resource.tf_path is None:
            if version is None:
                return select_dataset_root(candidates)
            return select_dataset_version(candidates, version)
        normalized = resource.tf_path.replace("\\", "/").strip("/") or "."
        configured_version = dataset_version(normalized)
        if version is not None and version != configured_version:
            raise ValueError(
                f"resource {resource.id!r} is pinned to Text-Fabric version {configured_version!r}, "
                f"not requested version {version!r}"
            )
        if normalized not in candidates:
            raise ValueError(
                f"configured Text-Fabric path {resource.tf_path!r} was not found for resource {resource.id!r}"
            )
        return normalized

    def corpus_versions(self, resource_id: str) -> tuple[str, ...]:
        resource = self.catalog.get(resource_id)
        if resource.kind != "corpus":
            raise ValueError(f"resource {resource_id!r} is not a corpus")
        repo, revision = self._repo(resource)
        roots = self.store.dataset_roots(repo, revision)
        if resource.tf_path is not None:
            relative = self._select_resource_root(resource, roots)
            return (dataset_version(relative),)
        return tuple(sorted({dataset_version(root) for root in roots}, key=_natural_tokens))

    def default_corpus_version(self, resource_id: str) -> str:
        resource = self.catalog.get(resource_id)
        if resource.kind != "corpus":
            raise ValueError(f"resource {resource_id!r} is not a corpus")
        repo, revision = self._repo(resource)
        relative = self._select_resource_root(resource, self.store.dataset_roots(repo, revision))
        return dataset_version(relative)

    def resolve_members(
        self,
        resource_id: str,
        *,
        query: str = "",
        source_revision: str | None = None,
    ) -> CollectionMemberListing:
        resource = self.catalog.get(resource_id)
        if resource.kind != "collection":
            raise ValueError(f"resource {resource_id!r} is not a collection")
        repo, revision = self._collection_repo(resource, source_revision)
        index = self._collection_index(
            resource,
            repo,
            revision,
            requested_revision=source_revision,
        )
        members = [
            self._member_from_index(resource, member, revision)
            for member in index.members
        ]
        needle = query.casefold().strip()
        if needle:
            members = [
                member
                for member in members
                if needle
                in " ".join(
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
            ]
        return CollectionMemberListing(source_revision=revision, members=tuple(members))

    def list_members(
        self,
        resource_id: str,
        *,
        source_revision: str | None = None,
    ) -> list[CollectionMember]:
        return list(
            self.resolve_members(resource_id, source_revision=source_revision).members
        )

    def search_members(
        self,
        resource_id: str,
        query: str,
        *,
        source_revision: str | None = None,
    ) -> list[CollectionMember]:
        return list(
            self.resolve_members(
                resource_id,
                query=query,
                source_revision=source_revision,
            ).members
        )

    def prepare(
        self,
        resource_id: str,
        *,
        member_id: str | None = None,
        version: str | None = None,
        source_revision: str | None = None,
    ) -> PreparedCorpus:
        resource = self.catalog.get(resource_id)
        if resource.kind == "feature-module":
            raise ValueError(
                f"feature module {resource_id!r} must be selected while preparing its parent corpus {resource.parent!r}"
            )
        if resource.kind == "collection":
            if version is not None:
                raise ValueError("version selection is supported only for corpus resources")
            if not member_id:
                raise ValueError(f"member_id is required for collection resource {resource_id!r}")
            repo, revision = self._collection_repo(resource, source_revision)
            index = self._collection_index(
                resource,
                repo,
                revision,
                requested_revision=source_revision,
            )
            members = {member.id: member for member in index.members}
            try:
                member = members[member_id]
            except KeyError as exc:
                raise KeyError(f"unknown member {member_id!r} in collection {resource_id!r}") from exc
            local = self.store.materialize(repo, member.tf_path, revision)
            resolved_version = dataset_version(member.tf_path)
            return PreparedCorpus(
                resource_id=resource.id,
                member_id=member.id,
                logical_name=f"{resource.id}:{member.id}",
                relative_path=member.tf_path,
                path=local,
                version=resolved_version,
                source_revision=revision,
            )
        if source_revision is not None:
            raise ValueError("source_revision selection is supported only for collection resources")
        if member_id is not None:
            raise ValueError(f"resource {resource_id!r} is not a collection; member_id is invalid")
        repo, revision = self._repo(resource)
        relative = self._select_resource_root(
            resource,
            self.store.dataset_roots(repo, revision),
            version,
        )
        resolved_version = dataset_version(relative)
        local = self.store.materialize(repo, relative, revision)
        logical_name = resource.id if version is None else f"{resource.id}@{resolved_version}"
        return PreparedCorpus(
            resource_id=resource.id,
            member_id=None,
            logical_name=logical_name,
            relative_path=relative,
            path=local,
            version=resolved_version,
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
        version = prepared.version or dataset_version(prepared.relative_path)
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
    def _link_features(source: Path, target: Path, *, allow_warp: bool) -> None:
        for source_file in sorted(source.glob("*.tf")):
            if not allow_warp and source_file.name in GitStore.FORBIDDEN_FEATURE_MODULE_FILES:
                raise ValueError(
                    f"feature module cannot replace parent warp file {source_file.name!r}"
                )
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
                *(f"{module.resource_id}:{module.relative_path}:{module.source_revision or ''}" for module in modules),
            ]
        )
        digest = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()[:16]
        revision = prepared.source_revision or "unknown"
        overlays = self.store.overlays_dir / self.store.safe_cache_key(prepared.resource_id) / revision
        overlays.mkdir(parents=True, exist_ok=True)
        destination = overlays / digest
        if destination.is_dir():
            self.store.touch_cache_object(destination)
            return destination
        temporary = Path(tempfile.mkdtemp(prefix=f".{digest}-", dir=overlays))
        try:
            self._link_features(prepared.path, temporary, allow_warp=True)
            for module in modules:
                self._link_features(module.path, temporary, allow_warp=False)
            if not (temporary / "otype.tf").is_file():
                raise FileNotFoundError("composed Text-Fabric corpus has no otype.tf")
            try:
                temporary.rename(destination)
            except FileExistsError:
                pass
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        self.store.touch_cache_object(destination)
        return destination

    def prepare_with_modules(
        self,
        resource_id: str,
        *,
        member_id: str | None = None,
        version: str | None = None,
        source_revision: str | None = None,
        modules: Iterable[str] | None = None,
    ) -> PreparedCorpus:
        # A prepare result is evictable after return, but the complete preparation
        # transaction (including module composition) must not race with deletion
        # of source paths it is actively reading.
        with self.store.cache_transition():
            prepared = self.prepare(
                resource_id,
                member_id=member_id,
                version=version,
                source_revision=source_revision,
            )
            module_ids = tuple(modules or ())
            if not module_ids:
                return prepared
            selected = self._prepare_feature_modules(prepared, module_ids)
            overlay = self._overlay(prepared, selected)
            logical_name = "+".join(
                [prepared.logical_name, *(module.resource_id for module in selected)]
            )
            return replace(
                prepared,
                logical_name=logical_name,
                path=overlay,
                modules=selected,
            )
