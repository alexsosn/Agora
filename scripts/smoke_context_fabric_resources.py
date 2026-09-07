#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))


@dataclass(frozen=True)
class LoadCase:
    resource_id: str
    features: tuple[str, ...]
    member_path_contains: str | None = None
    expected_known_issue: str | None = None
    expected_upstream_error_type: str | None = None
    expected_upstream_error_text: str | None = None


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
    "greek-known-bad": LoadCase(
        "greek_literature",
        (),
        "canonical-greekLit/tlg0001/tlg001/perseus-grc2/1/tf/1.0",
        "context-fabric/duplicate-structure-levels",
        "ValueError",
        "not enough values to unpack",
    ),
}

POSITIVE_CLAIMS = frozenset({"materialization", "load", "representative-content"})
CASE_CLAIMS = {
    "bhsa": POSITIVE_CLAIMS,
    "cuc": POSITIVE_CLAIMS,
    "greek-iliad": POSITIVE_CLAIMS,
    "greek-known-bad": frozenset({"known-issue-canary"}),
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


def validate_case_check_binding(
    case_name: str,
    check_id: str,
    *,
    member_id: str | None,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Bind one live smoke invocation to one exact canonical evidence subject."""
    if case_name not in LOAD_CASES:
        raise RuntimeError(f"unknown smoke case {case_name!r}")
    checks_path = Path(root) / "registry" / "verification-checks.yaml"
    document = yaml.safe_load(checks_path.read_text(encoding="utf-8"))
    checks = document.get("checks", []) if isinstance(document, dict) else []
    matches = [
        check
        for check in checks
        if isinstance(check, dict) and check.get("id") == check_id
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"{case_name}: check {check_id!r} must resolve exactly once, found {len(matches)}"
        )
    check = matches[0]
    if check.get("kind") != "live":
        raise RuntimeError(f"{case_name}: check {check_id!r} is not live evidence")
    contract = (check.get("plugin"), check.get("provider"))
    if contract != ("context-fabric", "context-fabric"):
        raise RuntimeError(
            f"{case_name}: check {check_id!r} has wrong plugin/provider contract {contract!r}"
        )

    case = LOAD_CASES[case_name]
    if case.member_path_contains is None:
        expected_subject = {"type": "resource", "resource_id": case.resource_id}
        if member_id is not None:
            raise RuntimeError(
                f"{case_name}: resource-scoped check unexpectedly resolved member {member_id!r}"
            )
    else:
        if not member_id:
            raise RuntimeError(f"{case_name}: member-scoped check resolved no member")
        expected_subject = {
            "type": "collection-member",
            "resource_id": case.resource_id,
            "member_id": member_id,
        }
    subject = check.get("subject")
    if subject != expected_subject:
        raise RuntimeError(
            f"{case_name}: check {check_id!r} subject {subject!r} does not match "
            f"resolved subject {expected_subject!r}"
        )

    claims = check.get("claims")
    actual_claims = frozenset(claims) if isinstance(claims, list) else frozenset()
    expected_claims = CASE_CLAIMS[case_name]
    if actual_claims != expected_claims:
        raise RuntimeError(
            f"{case_name}: check {check_id!r} claims {sorted(actual_claims)!r} do not match "
            f"the case contract {sorted(expected_claims)!r}"
        )
    return check


def probe_expected_upstream_failure(
    case_name: str,
    dataset: Path,
    *,
    expected_error_type: str,
    expected_error_text: str,
    fabric_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Reproduce one bounded upstream failure so a future fix retires the marker."""
    if fabric_factory is None:
        from cfabric import Fabric

        fabric_factory = Fabric

    try:
        fabric = fabric_factory(locations=str(dataset), silent="deep")
        fabric.loadAll(silent="deep")
    except Exception as exc:
        error_type = type(exc).__name__
        error_text = str(exc)
        if error_type != expected_error_type or expected_error_text not in error_text:
            raise RuntimeError(
                f"{case_name}: unexpected upstream failure while probing known issue: "
                f"{error_type}: {error_text}"
            ) from exc
        return {
            "status": "expected-upstream-failure",
            "error_type": error_type,
            "error_text": error_text,
        }

    raise RuntimeError(
        f"{case_name}: known issue may be fixed upstream; direct Context-Fabric load "
        "succeeded. Re-audit the affected set and retire or update the known issue."
    )


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


def run_case(
    case_name: str,
    cache_dir: Path,
    check_id: str | None = None,
) -> dict[str, Any]:
    from agora_context_fabric.catalog import Catalog
    from agora_context_fabric.gitstore import GitStore
    from agora_context_fabric.resolver import ContextFabricResolver, KnownMemberIssueError
    from agora_context_fabric.service import ContextFabricService
    from cfabric_mcp import corpus_manager

    case = LOAD_CASES[case_name]
    catalog = Catalog.from_registry(ROOT)
    store = GitStore(cache_dir)
    resolver = ContextFabricResolver(catalog, store)
    service = ContextFabricService(catalog, resolver, corpus_manager)
    member = None
    member_id = None
    source_revision = None
    if case.member_path_contains:
        member = select_collection_member(
            resolver.list_members(case.resource_id), case.member_path_contains
        )
        member_id = member.id
        source_revision = member.source_revision

    if check_id is not None:
        validate_case_check_binding(
            case_name,
            check_id,
            member_id=member_id,
        )

    if case.expected_known_issue is not None:
        if member is None:
            raise RuntimeError(f"{case_name}: expected-known-failure case has no selected member")
        if not source_revision:
            raise RuntimeError(f"{case_name}: selected member has no resolved source revision")
        if case.expected_known_issue not in member.verification_known_issues:
            raise RuntimeError(
                f"{case_name}: member {member.id!r} is not marked with expected known issue "
                f"{case.expected_known_issue!r}"
            )
        if not case.expected_upstream_error_type or not case.expected_upstream_error_text:
            raise RuntimeError(
                f"{case_name}: expected-known-failure case has no upstream retirement signature"
            )
        try:
            service.prepare(
                case.resource_id,
                member_id=member_id,
                source_revision=source_revision,
            )
        except KnownMemberIssueError as exc:
            issue_ids = {
                issue.get("id")
                for issue in exc.issues
                if isinstance(issue, dict) and isinstance(issue.get("id"), str)
            }
            if case.expected_known_issue not in issue_ids:
                raise RuntimeError(
                    f"{case_name}: prepare blocked for unexpected known issue(s): "
                    f"{sorted(issue_ids)}"
                ) from exc
        else:
            raise RuntimeError(
                f"{case_name}: prepare unexpectedly accepted member {member.id!r} despite "
                f"known blocking issue {case.expected_known_issue!r}"
            )

        # The normal Agora path above must reject before acquisition. For the one
        # retirement canary only, bypass that guard deliberately, acquire the exact
        # pinned dataset, and run Context-Fabric on a disposable copy. This observes
        # upstream behavior without patching it or letting loader caches mutate the
        # shared revision-addressed Agora snapshot.
        resource = catalog.get(case.resource_id)
        repo = store.ensure_metadata(
            resource.repository,
            cache_key=resource.id,
            ref=source_revision,
        )
        resolved_revision = store.selected_revision(repo)
        if resolved_revision != source_revision:
            raise RuntimeError(
                f"{case_name}: expected source revision {source_revision}, "
                f"resolved {resolved_revision}"
            )
        dataset = store.materialize(repo, member.relative_path, source_revision)
        with tempfile.TemporaryDirectory(prefix="agora-known-failure-probe-") as tmp:
            probe_dataset = Path(tmp) / "dataset"
            shutil.copytree(dataset, probe_dataset)
            upstream_probe = probe_expected_upstream_failure(
                case_name,
                probe_dataset,
                expected_error_type=case.expected_upstream_error_type,
                expected_error_text=case.expected_upstream_error_text,
            )

        report = {
            "case": case_name,
            "status": "expected-known-failure",
            "resource_id": case.resource_id,
            "member_id": member.id,
            "relative_path": member.relative_path,
            "source_revision": source_revision,
            "known_issue": case.expected_known_issue,
            "upstream_probe": upstream_probe,
        }
        if check_id is not None:
            report["check_id"] = check_id
        return report

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
        report = summarize_loaded_corpus(case_name, result, semantic_checks)
        if check_id is not None:
            report["check_id"] = check_id
        return report
    finally:
        service.unload(logical_name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Load representative Context-Fabric resources")
    parser.add_argument("cases", nargs="*", choices=sorted(LOAD_CASES))
    parser.add_argument(
        "--check-id",
        help="Bind one explicit smoke case to one canonical verification check ID.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("~/.cache/agora/context-fabric-smoke").expanduser(),
    )
    args = parser.parse_args()
    if args.check_id is not None and len(args.cases) != 1:
        parser.error("--check-id requires exactly one explicit smoke case")
    case_names = args.cases or list(LOAD_CASES)
    for case_name in case_names:
        if args.check_id is None:
            report = run_case(case_name, args.cache_dir)
        else:
            report = run_case(case_name, args.cache_dir, check_id=args.check_id)
        print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
