#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("plugins/context-fabric/resources/catalog.yaml")
MODULE_OUTPUT = Path("plugins/context-fabric/resources/feature-modules.yaml")
COLLECTION_OUTPUT = Path("plugins/context-fabric/resources/collections")


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_catalog_document(root: Path = ROOT) -> dict[str, Any]:
    """Build the installed catalog as a lossless v0.1 subset of resources.yaml."""
    root = Path(root)
    resources_doc = load_yaml(root / "registry" / "resources.yaml")
    scope_doc = load_yaml(root / "registry" / "v0.1.yaml")

    by_id = {
        item["id"]: item
        for item in resources_doc.get("resources", [])
        if item.get("plugin") == "context-fabric"
    }
    ordered: list[dict[str, Any]] = []
    for resource_id in scope_doc["required_resources"]:
        try:
            item = by_id[resource_id]
        except KeyError as exc:
            raise ValueError(
                f"v0.1 Context-Fabric resource {resource_id!r} is missing from registry/resources.yaml"
            ) from exc
        ordered.append(item)

    return {
        "schema_version": resources_doc["schema_version"],
        "resources": ordered,
    }


def build_feature_modules_document(root: Path = ROOT) -> dict[str, Any]:
    """Build the installed feature-module catalog losslessly from the registry shard."""
    root = Path(root)
    document = load_yaml(root / "registry" / "feature-modules.yaml")
    resources: list[dict[str, Any]] = []
    for item in document.get("resources", []):
        if item.get("plugin") != "context-fabric":
            continue
        if item.get("kind") == "feature-module":
            upstream = item.get("upstream") or {}
            missing = [key for key in ("module", "tf_path") if not upstream.get(key)]
            if missing:
                rendered = ", ".join(f"upstream.{key}" for key in missing)
                raise ValueError(
                    f"Context-Fabric feature module {item.get('id')!r} requires {rendered}"
                )
        resources.append(item)
    return {
        "schema_version": document["schema_version"],
        "resources": resources,
    }


def build_collection_index_documents(root: Path = ROOT) -> dict[Path, dict[str, Any]]:
    """Project canonical collection indexes into the self-contained plugin package."""
    root = Path(root)
    documents: dict[Path, dict[str, Any]] = {}
    for item in build_catalog_document(root)["resources"]:
        if item.get("kind") != "collection":
            continue
        collection = item.get("collection") or {}
        member_index = collection.get("member_index")
        if not member_index:
            raise ValueError(f"collection {item.get('id')!r} has no member_index")
        source = root / member_index
        if not source.is_file():
            raise ValueError(
                f"collection {item.get('id')!r} references missing member index {member_index!r}"
            )
        destination = COLLECTION_OUTPUT / source.name
        documents[destination] = load_yaml(source)
    return documents


def catalog_text(document: dict[str, Any]) -> str:
    return yaml.safe_dump(
        document,
        sort_keys=False,
        allow_unicode=True,
        width=1000,
    )


def generate(root: Path = ROOT) -> str:
    return catalog_text(build_catalog_document(root))


def generate_feature_modules(root: Path = ROOT) -> str:
    return catalog_text(build_feature_modules_document(root))


def check(root: Path = ROOT) -> list[str]:
    root = Path(root)
    expected_documents: list[tuple[Path, dict[str, Any]]] = [
        (OUTPUT, build_catalog_document(root)),
        (MODULE_OUTPUT, build_feature_modules_document(root)),
    ]
    expected_documents.extend(build_collection_index_documents(root).items())
    errors: list[str] = []
    for relative_path, expected in expected_documents:
        path = root / relative_path
        if not path.is_file():
            errors.append(f"missing generated runtime catalog: {relative_path}")
            continue
        actual = load_yaml(path)
        if actual != expected:
            errors.append(f"stale generated runtime catalog: {relative_path}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the self-contained Context-Fabric plugin resource catalogs."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the committed runtime catalogs are missing or stale.",
    )
    args = parser.parse_args()

    if args.check:
        errors = check(ROOT)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print("Context-Fabric runtime catalogs and collection indexes are fresh and lossless.")
        return 0

    outputs: list[tuple[Path, str]] = [
        (OUTPUT, generate(ROOT)),
        (MODULE_OUTPUT, generate_feature_modules(ROOT)),
    ]
    outputs.extend(
        (relative_path, catalog_text(document))
        for relative_path, document in build_collection_index_documents(ROOT).items()
    )
    for relative_path, text in outputs:
        path = ROOT / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"Wrote {relative_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
