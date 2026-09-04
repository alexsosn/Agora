#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))


@dataclass(frozen=True)
class LoadCase:
    resource_id: str
    features: tuple[str, ...]
    member_path_contains: str | None = None


@dataclass(frozen=True)
class SemanticExpectation:
    feature: str
    node: int
    expected: str


LOAD_CASES = {
    "bhsa": LoadCase("bhsa", ("g_cons", "sp")),
    "cuc": LoadCase("cuc", ("sign", "usign")),
    "greek-iliad": LoadCase(
        "greek_literature",
        ("orig", "main"),
        "canonical-greekLit/tlg0012/tlg001/perseus-grc2/1/tf/1.0",
    ),
}


SEMANTIC_EXPECTATIONS = {
    # BHSA 2021: the opening ETCBC slots of Genesis 1:1 are the prefixed
    # preposition B followed by R>CJT, with ETCBC POS values prep/subs.
    "bhsa": (
        SemanticExpectation("g_cons", 1, "B"),
        SemanticExpectation("g_cons", 2, "R>CJT"),
        SemanticExpectation("sp", 1, "prep"),
        SemanticExpectation("sp", 2, "subs"),
    ),
    # CUC 0.2.8: the first encoded Ugaritic sign is ḥ / U+10388.
    "cuc": (
        SemanticExpectation("sign", 1, "ḥ"),
        SemanticExpectation("usign", 1, "𐎈"),
    ),
    # PThU Iliad member: orig preserves source formatting while main is the
    # normalized text feature; both identify the first word of Iliad 1.1.
    "greek-iliad": (
        SemanticExpectation("orig", 1, "μῆνιν"),
        SemanticExpectation("main", 1, "μῆνιν"),
    ),
}


def select_collection_member(members: Iterable[Any], path_contains: str):
    matches = [member for member in members if path_contains in member.relative_path]
    if not matches:
        raise ValueError(f"no collection member matches path fragment {path_contains!r}")
    if len(matches) > 1:
        raise ValueError(f"multiple collection members match path fragment {path_contains!r}")
    return matches[0]


def _normalized_text(value: Any) -> str | None:
    if value is None:
        return None
    return unicodedata.normalize("NFC", str(value).strip())


def check_semantic_expectations(
    case_name: str,
    api: Any,
    expectations: Sequence[SemanticExpectation],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for expectation in expectations:
        feature_api = getattr(api.F, expectation.feature, None)
        if feature_api is None or not callable(getattr(feature_api, "v", None)):
            raise RuntimeError(
                f"{case_name}: loaded corpus does not expose feature {expectation.feature!r}"
            )
        actual = _normalized_text(feature_api.v(expectation.node))
        expected = _normalized_text(expectation.expected)
        if actual != expected:
            raise RuntimeError(
                f"{case_name}: feature {expectation.feature!r} node {expectation.node} "
                f"expected {expected!r}, got {actual!r}"
            )
        checks.append(
            {
                "feature": expectation.feature,
                "node": expectation.node,
                "expected": expected,
                "actual": actual,
            }
        )
    return checks


def summarize_loaded_corpus(
    case_name: str,
    result: dict[str, Any],
    semantic_checks: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    dataset = Path(result["path"])
    if not (dataset / "otype.tf").is_file():
        raise RuntimeError(f"{case_name}: materialized corpus has no otype.tf")
    corpus = result.get("corpus")
    if corpus is None:
        raise RuntimeError(f"{case_name}: loader returned no corpus information")
    source_revision = result.get("source_revision")
    if not source_revision:
        raise RuntimeError(f"{case_name}: loader returned no resolved source revision")
    if not semantic_checks:
        raise RuntimeError(f"{case_name}: no semantic checks were performed")
    return {
        "case": case_name,
        "status": "ok",
        "resource_id": result["resource_id"],
        "member_id": result.get("member_id"),
        "relative_path": result["relative_path"],
        "source_revision": source_revision,
        "has_otype": True,
        "corpus_info_type": type(corpus).__name__,
        "semantic_checks": list(semantic_checks),
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
    source_revision = None
    if case.member_path_contains:
        member = select_collection_member(
            resolver.list_members(case.resource_id), case.member_path_contains
        )
        member_id = member.id
        source_revision = member.source_revision

    result = service.load(
        case.resource_id,
        member_id=member_id,
        source_revision=source_revision,
        features=list(case.features),
    )
    logical_name = result["logical_name"]
    try:
        api = corpus_manager.get_api(logical_name)
        semantic_checks = check_semantic_expectations(
            case_name,
            api,
            SEMANTIC_EXPECTATIONS[case_name],
        )
        return summarize_loaded_corpus(case_name, result, semantic_checks)
    finally:
        service.unload(logical_name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Load representative Context-Fabric resources")
    parser.add_argument("cases", nargs="*", choices=sorted(LOAD_CASES), default=list(LOAD_CASES))
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("~/.cache/agora/context-fabric-smoke").expanduser(),
    )
    args = parser.parse_args()
    for case_name in args.cases:
        print(json.dumps(run_case(case_name, args.cache_dir), sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
