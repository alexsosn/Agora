from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
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
class PreparedCorpus:
    resource_id: str
    member_id: str | None
    logical_name: str
    relative_path: str
    path: Path


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
        return (2, _natural_tokens(version), -normalized.count("/"), normalized)
    if marker in normalized:
        version = normalized.rsplit(marker, 1)[1]
        return (2, _natural_tokens(version), -normalized.count("/"), normalized)
    return (1, _natural_tokens(normalized), -normalized.count("/"), normalized)


def select_dataset_root(roots: Iterable[str]) -> str:
    candidates = sorted(set(roots))
    if not candidates:
        raise ValueError("no Text-Fabric dataset roots were discovered")
    return max(candidates, key=_dataset_rank)


class ContextFabricResolver:
    def __init__(self, catalog: Catalog, store: GitStore):
        self.catalog = catalog
        self.store = store

    def _repo(self, resource: ResourceSpec) -> Path:
        return self.store.ensure_metadata(resource.repository, cache_key=resource.id)

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
            author = parts[0] if len(parts) > 1 else None
            title = parts[-1] if parts else identity
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
        repo = self._repo(resource)
        return self._collection_members_from_roots(resource, self.store.dataset_roots(repo))

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
        repo = self._repo(resource)

        if resource.kind == "collection":
            if not member_id:
                raise ValueError(f"member_id is required for collection resource {resource_id!r}")
            members = {member.id: member for member in self._collection_members_from_roots(
                resource, self.store.dataset_roots(repo)
            )}
            try:
                member = members[member_id]
            except KeyError as exc:
                raise KeyError(f"unknown member {member_id!r} in collection {resource_id!r}") from exc
            local = self.store.materialize(repo, member.relative_path)
            return PreparedCorpus(
                resource_id=resource.id,
                member_id=member.id,
                logical_name=f"{resource.id}:{member.id}",
                relative_path=member.relative_path,
                path=local,
            )

        if member_id is not None:
            raise ValueError(f"resource {resource_id!r} is not a collection; member_id is invalid")
        relative = select_dataset_root(self.store.dataset_roots(repo))
        local = self.store.materialize(repo, relative)
        return PreparedCorpus(
            resource_id=resource.id,
            member_id=None,
            logical_name=resource.id,
            relative_path=relative,
            path=local,
        )
