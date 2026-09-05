#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path
from typing import Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog, ResourceSpec
from agora_context_fabric.collection_index import CollectionIndexManager, dump_collection_index
from agora_context_fabric.gitstore import GitStore


COLLECTION_IDS = (
    "bible",
    "patristics",
    "greek_literature",
    "translatin-manif",
)
_IMMUTABLE_REVISION_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")


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
