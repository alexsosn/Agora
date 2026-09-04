#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILE = ROOT / "research" / "candidates.yaml"


def load_candidates(path: Path = DEFAULT_FILE) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    return list(doc.get("candidates", []))


def _latest_live_smoke(candidate: dict[str, Any]) -> str | None:
    evidence = candidate.get("evidence") or []
    if not evidence:
        return None
    return (evidence[-1].get("live_smoke") or {}).get("status")


def filter_candidates(
    candidates: Iterable[dict[str, Any]],
    *,
    priority: str | None = None,
    data_license_status: str | None = None,
    authentication: str | None = None,
    live_smoke: str | None = None,
    technical_readiness: str | None = None,
    annotation_maturity: str | None = None,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for candidate in candidates:
        if priority is not None and candidate.get("priority") != priority:
            continue
        legal = candidate.get("legal") or {}
        data_license = legal.get("data_license") or {}
        if data_license_status is not None and data_license.get("status") != data_license_status:
            continue
        if authentication is not None and legal.get("authentication") != authentication:
            continue
        if live_smoke is not None and _latest_live_smoke(candidate) != live_smoke:
            continue
        assessment = candidate.get("assessment") or {}
        if (
            technical_readiness is not None
            and assessment.get("technical_readiness") != technical_readiness
        ):
            continue
        if (
            annotation_maturity is not None
            and candidate.get("annotation_maturity") != annotation_maturity
        ):
            continue
        matches.append(candidate)
    return sorted(matches, key=lambda item: item["id"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Query structured Agora candidate research")
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    parser.add_argument("--priority", choices=["P0", "P1", "P2", "wanted"])
    parser.add_argument(
        "--data-license-status",
        choices=["known", "unknown", "not-applicable"],
    )
    parser.add_argument(
        "--authentication",
        choices=["none", "optional", "required", "unknown", "not-applicable"],
    )
    parser.add_argument(
        "--live-smoke",
        choices=["success", "failure", "pending", "not-tested", "not-applicable"],
    )
    parser.add_argument(
        "--technical-readiness",
        choices=["ready", "promising", "blocked", "unknown"],
    )
    parser.add_argument(
        "--annotation-maturity",
        choices=[
            "generated",
            "manually-reviewed",
            "mixed",
            "snapshot-wip",
            "unknown",
            "not-applicable",
        ],
    )
    parser.add_argument("--ids-only", action="store_true")
    args = parser.parse_args()

    matches = filter_candidates(
        load_candidates(args.file),
        priority=args.priority,
        data_license_status=args.data_license_status,
        authentication=args.authentication,
        live_smoke=args.live_smoke,
        technical_readiness=args.technical_readiness,
        annotation_maturity=args.annotation_maturity,
    )
    if args.ids_only:
        for candidate in matches:
            print(candidate["id"])
    else:
        print(json.dumps(matches, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
