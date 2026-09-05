from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Mapping

import yaml


_IMMUTABLE_REVISION_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
DUPLICATE_STRUCTURE_LEVELS_ISSUE_ID = "context-fabric/duplicate-structure-levels"


@dataclass(frozen=True)
class CollectionIndexMember:
    id: str
    path: str
    tf_path: str
    languages: tuple[str, ...]
    author: str | None = None
    title: str | None = None
    canonical_id: str | None = None
    edition: str | None = None
    verification_status: str = "community"
    verification_evidence: tuple[str, ...] = ()
    verification_notes: tuple[str, ...] = ()
    verification_known_issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class CollectionIndex:
    collection_id: str
    source_revision: str
    index_status: str
    members: tuple[CollectionIndexMember, ...]
    notes: tuple[str, ...] = ()


def member_identity_path(path: str) -> str:
    """Return a version-independent identity for one independently loadable TF root."""
    normalized = path.replace("\\", "/").strip("/")
    marker = "/tf/"
    if marker in normalized:
        return normalized.split(marker, 1)[0]
    parts = PurePosixPath(normalized).parts
    if len(parts) >= 3 and parts[0] == "tf":
        return "/".join(parts[:-1])
    if len(parts) >= 2 and parts[-2] == "tf":
        return "/".join(parts[:-2]) or normalized
    return normalized


def member_id_from_identity(identity_path: str) -> str:
    identity = identity_path.replace("\\", "/").strip("/")
    slug = re.sub(r"[^a-z0-9]+", "-", identity.casefold()).strip("-")
    if not slug:
        slug = "member"
    if len(slug) > 72:
        slug = slug[:72].rstrip("-")
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}"


def parse_tf_header(lines: Iterable[str]) -> dict[str, str]:
    """Parse only Text-Fabric metadata header lines, never feature data rows."""
    metadata: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if not line:
            break
        if not line.startswith("@"):
            break
        body = line[1:]
        if "=" not in body:
            continue
        key, value = body.split("=", 1)
        if key:
            metadata[key] = value
    return metadata


def duplicate_structure_levels(metadata: Mapping[str, str]) -> bool:
    """Mirror Context-Fabric's uniqueness precondition for structureTypes."""
    raw = metadata.get("structureTypes")
    if not raw:
        return False
    levels = [value.strip() for value in raw.split(",") if value.strip()]
    return len(levels) != len(set(levels))


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
        version = PurePosixPath(normalized).name
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


def build_collection_index(
    *,
    collection_id: str,
    source_revision: str,
    roots: Iterable[str],
    languages: Iterable[str],
    metadata_reader: Callable[[str], Mapping[str, str] | None],
) -> CollectionIndex:
    if not _IMMUTABLE_REVISION_RE.fullmatch(source_revision):
        raise ValueError(
            "source_revision must be an immutable commit id "
            "(40 or 64 hexadecimal characters)"
        )
    grouped: dict[str, list[str]] = {}
    for root in roots:
        identity = member_identity_path(root)
        grouped.setdefault(identity, []).append(root)

    member_languages = tuple(languages)
    members: list[CollectionIndexMember] = []
    for identity, versions in grouped.items():
        selected = select_dataset_root(versions)
        metadata = dict(metadata_reader(selected) or {})
        title = metadata.get("title") or metadata.get("_book")
        canonical_id = metadata.get("urn") or metadata.get("filename")
        known_issues = (
            (DUPLICATE_STRUCTURE_LEVELS_ISSUE_ID,)
            if duplicate_structure_levels(metadata)
            else ()
        )
        members.append(
            CollectionIndexMember(
                id=member_id_from_identity(identity),
                path=identity,
                tf_path=selected,
                languages=member_languages,
                author=metadata.get("author"),
                title=title,
                canonical_id=canonical_id,
                edition=metadata.get("edition"),
                verification_known_issues=known_issues,
            )
        )

    return CollectionIndex(
        collection_id=collection_id,
        source_revision=source_revision,
        index_status="complete",
        members=tuple(sorted(members, key=lambda member: member.path.casefold())),
    )


def index_to_document(index: CollectionIndex) -> dict:
    members: list[dict] = []
    for member in index.members:
        item: dict = {
            "id": member.id,
            "path": member.path,
            "tf_path": member.tf_path,
            "languages": list(member.languages),
        }
        if member.author is not None:
            item["author"] = member.author
        if member.title is not None:
            item["title"] = member.title
        if member.canonical_id is not None:
            item["canonical_id"] = member.canonical_id
        if member.edition is not None:
            item["edition"] = member.edition
        verification: dict = {"status": member.verification_status}
        if member.verification_evidence:
            verification["evidence"] = [
                {"check_id": check_id} for check_id in member.verification_evidence
            ]
        if member.verification_notes:
            verification["notes"] = list(member.verification_notes)
        if member.verification_known_issues:
            verification["known_issues"] = [
                {"issue_id": issue_id}
                for issue_id in member.verification_known_issues
            ]
        item["verification"] = verification
        members.append(item)

    document: dict = {
        "schema_version": 1,
        "collection_id": index.collection_id,
        "source_revision": index.source_revision,
        "index_status": index.index_status,
        "members": members,
    }
    if index.notes:
        document["notes"] = list(index.notes)
    return document


def index_from_document(document: Mapping) -> CollectionIndex:
    members: list[CollectionIndexMember] = []
    for item in document.get("members", []):
        verification = item.get("verification") or {}
        evidence = tuple(
            ref["check_id"]
            for ref in verification.get("evidence", [])
            if isinstance(ref, Mapping) and isinstance(ref.get("check_id"), str)
        )
        known_issues = tuple(
            ref["issue_id"]
            for ref in verification.get("known_issues", [])
            if isinstance(ref, Mapping) and isinstance(ref.get("issue_id"), str)
        )
        members.append(
            CollectionIndexMember(
                id=item["id"],
                path=item["path"],
                tf_path=item.get("tf_path") or item["path"],
                languages=tuple(item.get("languages", ())),
                author=item.get("author"),
                title=item.get("title"),
                canonical_id=item.get("canonical_id"),
                edition=item.get("edition"),
                verification_status=verification.get("status", "community"),
                verification_evidence=evidence,
                verification_notes=tuple(verification.get("notes", ())),
                verification_known_issues=known_issues,
            )
        )
    return CollectionIndex(
        collection_id=document["collection_id"],
        source_revision=document["source_revision"],
        index_status=document["index_status"],
        members=tuple(members),
        notes=tuple(document.get("notes", ())),
    )


def load_collection_index(path: Path) -> CollectionIndex:
    with Path(path).open("r", encoding="utf-8") as fh:
        return index_from_document(yaml.safe_load(fh))


def dump_collection_index(index: CollectionIndex) -> str:
    return yaml.safe_dump(
        index_to_document(index),
        sort_keys=False,
        allow_unicode=True,
        width=1000,
    )


class CollectionIndexManager:
    """Resolve installed or locally generated indexes for one exact Git revision."""

    def __init__(self, store) -> None:
        self.store = store
        self.cache_dir = Path(store.cache_dir) / "collection-indexes"

    def _cache_path(self, collection_id: str, source_revision: str) -> Path:
        return (
            self.cache_dir
            / self.store.safe_cache_key(collection_id)
            / f"{source_revision}.yaml"
        )

    @staticmethod
    def _matching_index(
        path: Path,
        *,
        collection_id: str,
        source_revision: str,
    ) -> CollectionIndex | None:
        if not path.is_file():
            return None
        try:
            index = load_collection_index(path)
        except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError):
            return None
        if (
            index.collection_id != collection_id
            or index.source_revision != source_revision
            or index.index_status != "complete"
        ):
            return None
        return index

    @staticmethod
    def _clean_metadata(metadata: Mapping) -> dict[str, str]:
        return {
            str(key): str(value)
            for key, value in metadata.items()
            if isinstance(key, str) and isinstance(value, (str, int, float, bool))
        }

    def _metadata_for(self, repo: Path, tf_path: str, revision: str) -> Mapping[str, str]:
        prefix = "" if tf_path == "." else f"{tf_path}/"
        merged: dict[str, str] = {}

        try:
            book_metadata = self.store.tf_header_metadata(
                repo,
                f"{prefix}_book.tf",
                revision,
            )
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
            book_metadata = {}
        merged.update(self._clean_metadata(book_metadata))

        try:
            text_metadata = self.store.tf_header_metadata(
                repo,
                f"{prefix}otext.tf",
                revision,
            )
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
            text_metadata = {}
        cleaned_text_metadata = self._clean_metadata(text_metadata)
        for key in ("structureTypes", "structureFeatures"):
            if key in cleaned_text_metadata:
                merged[key] = cleaned_text_metadata[key]
        return merged

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            temporary.write_text(text, encoding="utf-8")
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def resolve(
        self,
        *,
        collection_id: str,
        languages: Iterable[str],
        repo: Path,
        source_revision: str,
        installed_index: str | Path | None = None,
    ) -> CollectionIndex:
        if installed_index is not None:
            installed = self._matching_index(
                Path(installed_index),
                collection_id=collection_id,
                source_revision=source_revision,
            )
            if installed is not None:
                return installed

        cached_path = self._cache_path(collection_id, source_revision)
        cached = self._matching_index(
            cached_path,
            collection_id=collection_id,
            source_revision=source_revision,
        )
        if cached is not None:
            return cached

        roots = self.store.dataset_roots(repo, source_revision)
        index = build_collection_index(
            collection_id=collection_id,
            source_revision=source_revision,
            roots=roots,
            languages=languages,
            metadata_reader=lambda tf_path: self._metadata_for(
                repo, tf_path, source_revision
            ),
        )
        self._atomic_write(cached_path, dump_collection_index(index))
        return index
