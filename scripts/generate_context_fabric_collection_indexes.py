#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog, ResourceSpec
from agora_context_fabric.collection_index import (
    CollectionIndex,
    CollectionIndexManager,
    dump_collection_index,
)
from agora_context_fabric.gitstore import GitStore


COLLECTION_IDS = (
    "bible",
    "patristics",
    "greek_literature",
    "translatin-manif",
)
_IMMUTABLE_REVISION_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
_VERIFICATION_STATUSES = frozenset({"experimental", "community", "verified"})


def load_yaml(path: Path):
    with Path(path).open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def configured_revision(resource: ResourceSpec) -> str:
    if resource.member_index_path is None:
        raise ValueError(f"collection {resource.id!r} has no canonical member index path")
    document = load_yaml(resource.member_index_path)
    revision = document.get("source_revision")
    if not isinstance(revision, str) or not _IMMUTABLE_REVISION_RE.fullmatch(revision):
        raise ValueError(
            f"collection {resource.id!r} canonical index must declare a full immutable source_revision"
        )
    return revision.lower()


def generate_resource_index(
    resource: ResourceSpec,
    *,
    source_revision: str,
    store: GitStore,
):
    if resource.kind != "collection":
        raise ValueError(f"resource {resource.id!r} is not a collection")
    repo = store.ensure_metadata(
        resource.repository,
        cache_key=f"collection-index-{resource.id}",
        ref=source_revision,
    )
    resolved_revision = store.selected_revision(repo)
    if resolved_revision.lower() != source_revision.lower():
        raise ValueError(
            f"collection {resource.id!r} resolved {resolved_revision!r}, expected {source_revision!r}"
        )
    return CollectionIndexManager(store).resolve(
        collection_id=resource.id,
        languages=resource.languages,
        repo=repo,
        source_revision=resolved_revision,
        installed_index=None,
    )


def _canonical_member_by_id(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        member["id"]: member
        for member in document.get("members", [])
        if isinstance(member, dict) and isinstance(member.get("id"), str)
    }


def preserve_canonical_verification(
    index: CollectionIndex,
    canonical_document: dict[str, Any] | None,
) -> CollectionIndex:
    """Carry trust annotations across same-revision regeneration, never source findings.

    Status, positive evidence references, and notes are Agora-owned trust metadata.
    Known-issue references are source-derived by the generator and must therefore
    always come from the newly generated index. Trust is also never carried across
    a source revision or member path change.
    """
    if not isinstance(canonical_document, dict):
        return index
    if canonical_document.get("collection_id") != index.collection_id:
        return index
    canonical_revision = canonical_document.get("source_revision")
    if not isinstance(canonical_revision, str):
        return index
    if canonical_revision.casefold() != index.source_revision.casefold():
        return index

    canonical_by_id = _canonical_member_by_id(canonical_document)
    members = []
    for member in index.members:
        previous = canonical_by_id.get(member.id)
        if not isinstance(previous, dict):
            members.append(member)
            continue
        if previous.get("path") != member.path or previous.get("tf_path") != member.tf_path:
            members.append(member)
            continue
        verification = previous.get("verification")
        if not isinstance(verification, dict):
            members.append(member)
            continue

        status = verification.get("status")
        if status not in _VERIFICATION_STATUSES:
            status = member.verification_status
        evidence = tuple(
            reference["check_id"]
            for reference in verification.get("evidence", [])
            if isinstance(reference, dict) and isinstance(reference.get("check_id"), str)
        )
        notes = tuple(
            note for note in verification.get("notes", []) if isinstance(note, str)
        )
        members.append(
            replace(
                member,
                verification_status=status,
                verification_evidence=evidence,
                verification_notes=notes,
            )
        )

    return replace(index, members=tuple(members))


def generate_documents(
    root: Path,
    *,
    resource_ids: Iterable[str] = COLLECTION_IDS,
    cache_dir: Path,
) -> dict[str, str]:
    root = Path(root)
    catalog = Catalog.from_registry(root)
    store = GitStore(Path(cache_dir))
    generated: dict[str, str] = {}
    for resource_id in resource_ids:
        resource = catalog.get(resource_id)
        revision = configured_revision(resource)
        index = generate_resource_index(
            resource,
            source_revision=revision,
            store=store,
        )
        canonical_document = None
        if resource.member_index_path is not None and resource.member_index_path.is_file():
            canonical_document = load_yaml(resource.member_index_path)
        index = preserve_canonical_verification(index, canonical_document)
        generated[resource_id] = dump_collection_index(index)
    return generated


def output_path(root: Path, output_dir: Path | None, resource: ResourceSpec) -> Path:
    if output_dir is not None:
        return Path(output_dir) / f"{resource.id}.yaml"
    if resource.member_index_path is None:
        raise ValueError(f"collection {resource.id!r} has no canonical member index path")
    return Path(resource.member_index_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate complete Context-Fabric collection indexes at their configured immutable revisions."
    )
    parser.add_argument(
        "--resource",
        action="append",
        choices=COLLECTION_IDS,
        dest="resources",
        help="Generate only the selected collection; repeat for multiple collections.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Write generated indexes to a separate directory instead of replacing canonical registry files.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Use an explicit metadata/index cache directory.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Regenerate at the configured revisions and fail if canonical index content differs.",
    )
    args = parser.parse_args()

    resource_ids = tuple(args.resources or COLLECTION_IDS)
    catalog = Catalog.from_registry(ROOT)

    temporary_cache = None
    if args.cache_dir is None:
        temporary_cache = tempfile.TemporaryDirectory(prefix="agora-collection-index-")
        cache_dir = Path(temporary_cache.name)
    else:
        cache_dir = args.cache_dir

    try:
        documents = generate_documents(
            ROOT,
            resource_ids=resource_ids,
            cache_dir=cache_dir,
        )
        errors: list[str] = []
        for resource_id in resource_ids:
            resource = catalog.get(resource_id)
            generated_text = documents[resource_id]
            canonical_path = resource.member_index_path
            if args.check:
                if canonical_path is None or not canonical_path.is_file():
                    errors.append(f"missing canonical collection index: {resource_id}")
                    continue
                canonical = canonical_path.read_text(encoding="utf-8")
                if canonical != generated_text:
                    errors.append(f"stale canonical collection index: {resource_id}")
                continue

            destination = output_path(ROOT, args.output_dir, resource)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(generated_text, encoding="utf-8")
            print(
                f"Wrote {destination} ({len(load_yaml(destination)['members'])} members, "
                f"revision {load_yaml(destination)['source_revision']})"
            )

        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        if args.check:
            print("Context-Fabric collection indexes reproduce exactly at their configured revisions.")
        return 0
    finally:
        if temporary_cache is not None:
            temporary_cache.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
