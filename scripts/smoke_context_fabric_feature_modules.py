#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gc
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.resolver import ContextFabricResolver
from agora_context_fabric.service import ContextFabricService


def required_cases(report: dict[str, Any]) -> list[dict[str, Any]]:
    required = set(report.get("load_smoke_required", []))
    by_id = {item["id"]: item for item in report.get("resources", [])}
    cases: list[dict[str, Any]] = []
    for module_id in sorted(required):
        item = by_id.get(module_id)
        if item is None:
            raise ValueError(f"audit report names missing load-smoke module {module_id!r}")
        if item.get("status") != "ok":
            raise ValueError(f"cannot load-smoke failed audit item {module_id!r}")
        if item.get("compatibility_evidence") != "load-smoke-required":
            raise ValueError(f"audit item {module_id!r} is not marked load-smoke-required")
        cases.append(item)
    return cases


def feature_names(item: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for filename in item.get("feature_files", []):
        if not filename.endswith(".tf") or filename.startswith("otext@"):
            continue
        names.append(filename[:-3])
    if not names:
        raise ValueError(f"load-smoke module {item['id']!r} exposes no loadable feature names")
    return names


def run_smokes(report: dict[str, Any], cache_dir: Path) -> dict[str, Any]:
    from cfabric_mcp.corpus_manager import CorpusManager

    catalog = Catalog.from_registry(ROOT)
    store = GitStore(cache_dir)
    resolver = ContextFabricResolver(catalog, store)
    results: list[dict[str, Any]] = []

    for item in required_cases(report):
        module = catalog.get(item["id"])
        if not module.parent:
            raise ValueError(f"load-smoke module {module.id!r} has no parent")
        features = feature_names(item)
        for version in module.parent_versions:
            manager = CorpusManager()
            service = ContextFabricService(catalog, resolver, manager)
            result = service.load(
                module.parent,
                version=version,
                modules=[module.id],
                features=features,
            )
            expected_name = f"{module.parent}@{version}+{module.id}"
            if result["logical_name"] != expected_name:
                raise RuntimeError(
                    f"{module.id}: loaded name {result['logical_name']!r} != {expected_name!r}"
                )
            corpus = result.get("corpus")
            if not corpus:
                raise RuntimeError(f"{module.id}: loader returned no corpus information")
            results.append(
                {
                    "id": module.id,
                    "parent": module.parent,
                    "parent_version": version,
                    "logical_name": result["logical_name"],
                    "source_revision": result.get("source_revision"),
                    "module_source_revision": result["modules"][0].get("source_revision"),
                    "features": features,
                    "status": "ok",
                }
            )
            manager.unload(result["logical_name"])
            del service, manager, result, corpus
            gc.collect()

    return {
        "ok": True,
        "checked": len(results),
        "modules": sorted({item["id"] for item in results}),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Real-load Context-Fabric feature modules that lack self-describing core metadata."
    )
    parser.add_argument("--audit-report", type=Path, required=True)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("~/.cache/agora/context-fabric-audit").expanduser(),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = json.loads(args.audit_report.read_text(encoding="utf-8"))
    result = run_smokes(report, args.cache_dir)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    print(text, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
