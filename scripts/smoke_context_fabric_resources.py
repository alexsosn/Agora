#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))


@dataclass(frozen=True)
class LoadCase:
    resource_id: str
    member_path_contains: str | None = None


LOAD_CASES = {
    "bhsa": LoadCase("bhsa"),
    "cuc": LoadCase("cuc"),
    "greek-iliad": LoadCase(
        "greek_literature",
        "canonical-greekLit/tlg0012/tlg001/perseus-grc2/1/tf/1.0",
    ),
}


def select_collection_member(members: Iterable[Any], path_contains: str):
    matches = [member for member in members if path_contains in member.relative_path]
    if not matches:
        raise ValueError(f"no collection member matches path fragment {path_contains!r}")
    if len(matches) > 1:
        raise ValueError(f"multiple collection members match path fragment {path_contains!r}")
    return matches[0]


def summarize_loaded_corpus(case_name: str, result: dict[str, Any]) -> dict[str, Any]:
    dataset = Path(result["path"])
    if not (dataset / "otype.tf").is_file():
        raise RuntimeError(f"{case_name}: materialized corpus has no otype.tf")
    corpus = result.get("corpus")
    if corpus is None:
        raise RuntimeError(f"{case_name}: loader returned no corpus information")
    return {
        "case": case_name,
        "status": "ok",
        "resource_id": result["resource_id"],
        "member_id": result.get("member_id"),
        "relative_path": result["relative_path"],
        "source_revision": result.get("source_revision"),
        "has_otype": True,
        "corpus_info_type": type(corpus).__name__,
    }


def run_case(case_name: str, cache_dir: Path) -> dict[str, Any]:
    from agora_context_fabric.catalog import Catalog
    from agora_context_fabric.gitstore import GitStore
    from agora_context_fabric.resolver import ContextFabricResolver
    from agora_context_fabric.service import ContextFabricService
    from cfabric_mcp import corpus_manager

    case = LOAD_CASES[case_name]
    catalog = Catalog.from_registry(ROOT)
    resolver = ContextFabricResolver(catalog, GitStore(cache_dir))
    service = ContextFabricService(catalog, resolver, corpus_manager)
    member_id = None
    if case.member_path_contains:
        member = select_collection_member(
            resolver.list_members(case.resource_id), case.member_path_contains
        )
        member_id = member.id
    return summarize_loaded_corpus(
        case_name,
        service.load(case.resource_id, member_id=member_id),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Load representative Context-Fabric resources")
    parser.add_argument("cases", nargs="*", choices=sorted(LOAD_CASES), default=list(LOAD_CASES))
    parser.add_argument("--cache-dir", type=Path, default=Path("~/.cache/agora/context-fabric-smoke").expanduser())
    args = parser.parse_args()
    for case_name in args.cases:
        print(json.dumps(run_case(case_name, args.cache_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
