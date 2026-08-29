#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "context-fabric"
PLUGIN_SRC = PLUGIN_ROOT / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.resolver import select_dataset_root


def _selected_root(resource, roots: list[str]) -> str:
    if resource.tf_path is None:
        return select_dataset_root(roots)
    normalized = resource.tf_path.replace("\\", "/").strip("/") or "."
    if normalized not in roots:
        raise ValueError(
            f"configured Text-Fabric path {resource.tf_path!r} was not found"
        )
    return normalized


def audit_catalog(catalog: Catalog, store: GitStore) -> dict[str, Any]:
    resources: list[dict[str, Any]] = []
    failed = 0

    for resource in catalog:
        item: dict[str, Any] = {
            "id": resource.id,
            "name": resource.name,
            "kind": resource.kind,
            "repository": resource.repository,
        }
        if resource.ref is not None:
            item["ref"] = resource.ref
        if resource.tf_path is not None:
            item["configured_tf_path"] = resource.tf_path
        try:
            kwargs = {"cache_key": resource.id}
            if resource.ref is not None:
                kwargs["ref"] = resource.ref
            repo = store.ensure_metadata(resource.repository, **kwargs)
            roots = store.dataset_roots(repo)
            if not roots:
                raise ValueError("no Text-Fabric dataset roots were discovered")

            item["status"] = "ok"
            item["dataset_root_count"] = len(roots)
            if resource.kind == "collection":
                item["sample_roots"] = roots[:10]
            else:
                item["selected_root"] = _selected_root(resource, roots)
        except Exception as exc:  # audit must report all upstream failures
            failed += 1
            item["status"] = "error"
            item["error"] = str(exc)
        resources.append(item)

    checked = len(resources)
    return {
        "ok": failed == 0,
        "checked": checked,
        "passed": checked - failed,
        "failed": failed,
        "resources": resources,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit the v0.1 Context-Fabric upstream repositories using Git tree metadata only. "
            "Corpus blobs are not materialized."
        )
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("~/.cache/agora/context-fabric-audit").expanduser(),
        help="Metadata clone cache directory",
    )
    parser.add_argument(
        "--resource",
        action="append",
        dest="resource_ids",
        help="Audit only this resource ID; may be repeated",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON report path",
    )
    args = parser.parse_args()

    catalog = Catalog.from_plugin_root(PLUGIN_ROOT)
    if args.resource_ids:
        catalog = Catalog([catalog.get(resource_id) for resource_id in args.resource_ids])

    report = audit_catalog(catalog, GitStore(args.cache_dir))
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(text, end="")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
