#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("plugins/context-fabric/resources/catalog.yaml")


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_catalog_document(root: Path = ROOT) -> dict[str, Any]:
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
        "schema_version": 1,
        "source": "registry/resources.yaml",
        "release": scope_doc["release"],
        "resources": ordered,
    }


def catalog_text(document: dict[str, Any]) -> str:
    return yaml.safe_dump(
        document,
        sort_keys=False,
        allow_unicode=True,
        width=1000,
    )


def generate(root: Path = ROOT) -> str:
    return catalog_text(build_catalog_document(root))


def check(root: Path = ROOT) -> list[str]:
    root = Path(root)
    expected = generate(root)
    path = root / OUTPUT
    if not path.is_file():
        return [f"missing generated runtime catalog: {OUTPUT}"]
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        return [f"stale generated runtime catalog: {OUTPUT}"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the self-contained Context-Fabric plugin resource catalog."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the committed runtime catalog is missing or stale.",
    )
    args = parser.parse_args()

    if args.check:
        errors = check(ROOT)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print("Context-Fabric runtime catalog is fresh.")
        return 0

    path = ROOT / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate(ROOT), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
