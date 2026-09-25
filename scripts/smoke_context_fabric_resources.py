#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
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
    modules: tuple[str, ...] = ()


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
    # Regression smoke for the feature-module overlay path. It is not bound to
    # a registry verification check (checks describe resources and collection
    # members only), so it never promotes module evidence.
    "bhsa-phono": LoadCase("bhsa", ("g_cons", "phono"), modules=("bhsa-phono",)),
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
    # BHSA 2021 + ETCBC/phono: the module's phonetic transcription must align
    # with the parent's first two slots (B / R>CJT of Genesis 1:1).
    "bhsa-phono": (
        SemanticExpectation("g_cons", 1, "B"),
        SemanticExpectation("phono", 1, "bᵊ"),
        SemanticExpectation("phono", 2, "rēšˌîṯ"),
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
    if case_name not in CASE_CLAIMS:
        raise RuntimeError(f"{case_name}: case has no registry verification check contract")
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


def _tree_bytes(root: Path) -> int:
    """Apparent bytes under ``root``, counted like the store's own accounting.

    Symlinks are skipped and every path is counted, so files hard-linked
    between a snapshot and its overlay count once per path, exactly as
    ``cache_status``/``remove_cached`` count them.
    """

    total = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            candidate = Path(dirpath) / name
            try:
                if not candidate.is_symlink():
                    total += candidate.stat().st_size
            except OSError:
                continue
    return total


def _subject_cache_paths(
    store: Any,
    resource_id: str,
    member_id: str | None,
) -> list[str]:
    from agora_context_fabric.resolver import member_id_from_path

    paths: list[str] = []
    for entry in store.cache_entries(resource_id):
        if member_id is not None:
            relative_path = entry.get("relative_path")
            if entry.get("kind") != "corpus-snapshot" or not isinstance(relative_path, str):
                continue
            if member_id_from_path(relative_path) != member_id:
                continue
        paths.append(str(entry["path"]))
    return paths


# Removed bytes must show up as an on-disk reduction; allow a little slack for
# access stamps and metadata files that are rewritten while removing.
ON_DISK_RECLAIM_FRACTION = 0.9


def exercise_cache_lifecycle(
    case_name: str,
    case: LoadCase,
    service: Any,
    store: Any,
    *,
    member_id: str | None,
    first_result: dict[str, Any],
    reload_and_check: Callable[[], tuple[dict[str, Any], list[dict[str, Any]]]],
) -> dict[str, Any]:
    """Check unload, then remove, confirm the space is reclaimed, prune, reload.

    This exercises the user-facing cleanup path (unload_corpus,
    remove_cached_corpus, prune_corpus_cache) on a real corpus and proves a
    removed corpus can be exported, compiled and loaded again with the same
    content. The persistent Git metadata repository and its selected revision
    are deliberately kept by removal, so the reload is cold for snapshot
    export and compilation, not for Git metadata or revision selection.
    """

    status = service.cache_status()
    if status.get("loaded_corpora"):
        raise RuntimeError(
            f"{case_name}: corpora still loaded after unload: {status['loaded_corpora']!r}"
        )

    subjects = [(case.resource_id, member_id)] + [(module, None) for module in case.modules]
    cache_root = Path(store.cache_dir)
    bytes_on_disk_before = _tree_bytes(cache_root)
    cache_bytes_before = int(status["cache_bytes"])
    removals: list[dict[str, Any]] = []
    removed_paths: list[str] = []
    for resource_id, subject_member in subjects:
        paths = _subject_cache_paths(store, resource_id, subject_member)
        if not paths:
            raise RuntimeError(f"{case_name}: no cache objects found for {resource_id!r}")
        removal = service.remove_cached(resource_id, member_id=subject_member)
        if not removal.get("complete"):
            raise RuntimeError(f"{case_name}: removing {resource_id!r} was incomplete: {removal!r}")
        if removal.get("removed_entries") != removal.get("matched_entries"):
            raise RuntimeError(f"{case_name}: not every matched {resource_id!r} object was removed")
        if int(removal.get("removed_bytes", 0)) <= 0:
            raise RuntimeError(f"{case_name}: removing {resource_id!r} reclaimed no bytes")
        removals.append(
            {
                "resource_id": resource_id,
                "member_id": subject_member,
                "removed_entries": removal["removed_entries"],
                "removed_bytes": int(removal["removed_bytes"]),
            }
        )
        removed_paths.extend(paths)

    survivors = [path for path in removed_paths if Path(path).exists()]
    if survivors:
        raise RuntimeError(f"{case_name}: removed cache objects still exist: {survivors!r}")
    for resource_id, subject_member in subjects:
        if _subject_cache_paths(store, resource_id, subject_member):
            raise RuntimeError(f"{case_name}: cache still indexes removed {resource_id!r} objects")

    removed_bytes = sum(item["removed_bytes"] for item in removals)
    after_remove = service.cache_status()
    if int(after_remove["cache_bytes"]) > cache_bytes_before - removed_bytes:
        raise RuntimeError(
            f"{case_name}: cache_status still counts removed bytes "
            f"({cache_bytes_before} -> {after_remove['cache_bytes']}, removed {removed_bytes})"
        )
    bytes_on_disk_after = _tree_bytes(cache_root)
    reclaimed_apparent = bytes_on_disk_before - bytes_on_disk_after
    if reclaimed_apparent < removed_bytes * ON_DISK_RECLAIM_FRACTION:
        raise RuntimeError(
            f"{case_name}: only {reclaimed_apparent} bytes left the cache directory after "
            f"removing {removed_bytes} bytes"
        )

    # Nothing removable is left, so prune must neither be blocked nor grow the
    # cache; it also runs the bounded Git metadata maintenance.
    prune = service.prune_cache()
    if int(prune.get("skipped_in_use", 0)) or int(prune.get("blocked_by_transition", 0)):
        raise RuntimeError(f"{case_name}: prune was blocked: {prune!r}")
    if int(prune.get("after_bytes", 0)) > int(after_remove["cache_bytes"]):
        raise RuntimeError(
            f"{case_name}: cache grew during prune ({after_remove['cache_bytes']} -> "
            f"{prune.get('after_bytes')})"
        )
    for resource_id, subject_member in subjects:
        if _subject_cache_paths(store, resource_id, subject_member):
            raise RuntimeError(f"{case_name}: prune resurrected removed {resource_id!r} objects")

    started = time.monotonic()
    reloaded, semantic_checks = reload_and_check()
    reload_seconds = round(time.monotonic() - started, 1)
    if reloaded.get("source_revision") != first_result.get("source_revision"):
        raise RuntimeError(
            f"{case_name}: reload resolved {reloaded.get('source_revision')!r}, first load "
            f"resolved {first_result.get('source_revision')!r}"
        )
    return {
        "status": "ok",
        "removals": removals,
        "removed_bytes": removed_bytes,
        # Apparent bytes: files hard-linked between an overlay and its parent
        # snapshot are counted per path, like cache_status counts them.
        "reclaimed_apparent_bytes": reclaimed_apparent,
        "cache_bytes_before": cache_bytes_before,
        "cache_bytes_after_remove": int(after_remove["cache_bytes"]),
        "prune_removed_entries": prune.get("removed_entries"),
        "prune_removed_bytes": prune.get("removed_bytes"),
        "cache_bytes_after_prune": prune.get("after_bytes"),
        "reload_seconds": reload_seconds,
        "reload_semantic_checks": semantic_checks,
    }


def run_case(
    case_name: str,
    cache_dir: Path,
    check_id: str | None = None,
    *,
    lifecycle: bool = False,
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
        if lifecycle:
            report["lifecycle"] = {
                "status": "not-applicable",
                "reason": "the known-issue canary never loads through Agora",
            }
        return report

    def load_and_check() -> tuple[dict[str, Any], list[dict[str, Any]]]:
        load_kwargs: dict[str, Any] = {
            "member_id": member_id,
            "source_revision": source_revision,
            "features": list(case.features),
        }
        if case.modules:
            load_kwargs["modules"] = list(case.modules)
        loaded = service.load(case.resource_id, **load_kwargs)
        logical_name = loaded["logical_name"]
        try:
            api = corpus_manager.get_api(logical_name)
            checks = check_semantic_expectations(
                case_name,
                api,
                SEMANTIC_EXPECTATIONS[case_name],
            )
        finally:
            service.unload(logical_name)
        return loaded, checks

    result, semantic_checks = load_and_check()
    report = summarize_loaded_corpus(case_name, result, semantic_checks)
    if case.modules:
        report["modules"] = list(case.modules)
    if check_id is not None:
        report["check_id"] = check_id
    if lifecycle:
        report["lifecycle"] = exercise_cache_lifecycle(
            case_name,
            case,
            service,
            store,
            member_id=member_id,
            first_result=result,
            reload_and_check=load_and_check,
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Load representative Context-Fabric resources")
    parser.add_argument("cases", nargs="*", choices=sorted(LOAD_CASES))
    parser.add_argument(
        "--check-id",
        help="Bind one explicit smoke case to one canonical verification check ID.",
    )
    parser.add_argument(
        "--lifecycle",
        action="store_true",
        help=(
            "After a successful load, unload, remove and prune the cached corpus, "
            "check the space was reclaimed, then reload it and re-check content."
        ),
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
        options: dict[str, Any] = {"lifecycle": True} if args.lifecycle else {}
        if args.check_id is None:
            report = run_case(case_name, args.cache_dir, **options)
        else:
            report = run_case(case_name, args.cache_dir, check_id=args.check_id, **options)
        print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
