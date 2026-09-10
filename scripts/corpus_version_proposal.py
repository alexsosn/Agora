from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping, Sequence

import yaml

from scripts.check_materializer_releases import ReleaseDiscoveryError, _commit_sha


_RESOURCE_START = re.compile(r"^- id:\s+")
_FIELD_KEY = re.compile(r"^(?P<indent> +)(?P<key>[A-Za-z0-9_-]+):")
_ALLOWED_VERIFICATION = frozenset({"experimental", "community", "verified"})


def _scalar(value: str) -> str:
    """Emit a YAML-safe string without relying on whole-document reserialization."""

    return json.dumps(value, ensure_ascii=False)


def _field_range(lines: list[str], *, indent: int, key: str) -> tuple[int, int]:
    prefix = " " * indent + key + ":"
    matches = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    if len(matches) != 1:
        raise ReleaseDiscoveryError(
            f"expected exactly one {key!r} field at indentation {indent}, found {len(matches)}"
        )
    start = matches[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = _FIELD_KEY.match(lines[index])
        if match is not None and len(match.group("indent")) == indent:
            end = index
            break
    return start, end


def _newline(lines: Sequence[str]) -> str:
    for line in lines:
        if line.endswith("\r\n"):
            return "\r\n"
    return "\n"


def _replace_flow_scalar(line: str, key: str, value: str) -> str:
    ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
    body = line[: -len(ending)] if ending else line
    open_brace = body.find("{")
    close_brace = body.rfind("}")
    if open_brace < 0 or close_brace <= open_brace:
        raise ReleaseDiscoveryError(f"cannot safely edit non-flow mapping for {key!r}")
    inner = body[open_brace + 1 : close_brace]
    pattern = re.compile(rf"(?P<prefix>(?:^|,\s*){re.escape(key)}\s*:\s*)(?P<value>[^,}}]*)")
    match = pattern.search(inner)
    replacement = _scalar(value)
    if match is not None:
        inner = inner[: match.start("value")] + replacement + inner[match.end("value") :]
    else:
        separator = ", " if inner.strip() else ""
        inner = inner + separator + f"{key}: {replacement}"
    return body[: open_brace + 1] + inner + body[close_brace:] + ending


def _set_block_scalar(
    lines: list[str], *, parent_indent: int, parent_key: str, key: str, value: str
) -> list[str]:
    start, end = _field_range(lines, indent=parent_indent, key=parent_key)
    header = lines[start]
    after_colon = header.split(":", 1)[1].strip()
    if after_colon:
        if not after_colon.startswith("{"):
            raise ReleaseDiscoveryError(
                f"cannot safely edit inline {parent_key!r} value that is not a flow mapping"
            )
        lines[start] = _replace_flow_scalar(header, key, value)
        return lines

    child_indent = parent_indent + 2
    prefix = " " * child_indent + key + ":"
    hits = [i for i in range(start + 1, end) if lines[i].startswith(prefix)]
    if len(hits) > 1:
        raise ReleaseDiscoveryError(f"duplicate {parent_key}.{key} field")
    nl = _newline(lines)
    replacement = " " * child_indent + f"{key}: {_scalar(value)}{nl}"
    if hits:
        lines[hits[0]] = replacement
    else:
        lines.insert(end, replacement)
    return lines


def _remove_block_child(
    lines: list[str], *, parent_indent: int, parent_key: str, child_key: str
) -> list[str]:
    start, end = _field_range(lines, indent=parent_indent, key=parent_key)
    header = lines[start]
    after_colon = header.split(":", 1)[1].strip()
    if after_colon:
        if child_key in after_colon:
            raise ReleaseDiscoveryError(
                f"cannot safely remove inline {parent_key}.{child_key}; use block form"
            )
        return lines

    child_indent = parent_indent + 2
    prefix = " " * child_indent + child_key + ":"
    hits = [i for i in range(start + 1, end) if lines[i].startswith(prefix)]
    if len(hits) > 1:
        raise ReleaseDiscoveryError(f"duplicate {parent_key}.{child_key} field")
    if not hits:
        return lines
    child_start = hits[0]
    child_end = end
    for index in range(child_start + 1, end):
        match = _FIELD_KEY.match(lines[index])
        if match is not None and len(match.group("indent")) == child_indent:
            child_end = index
            break
    del lines[child_start:child_end]
    return lines


def _rewrite_verification(lines: list[str], status: str) -> list[str]:
    if status not in _ALLOWED_VERIFICATION:
        raise ReleaseDiscoveryError(f"unsupported proposal verification status {status!r}")
    start, _ = _field_range(lines, indent=2, key="verification")
    header = lines[start]
    after_colon = header.split(":", 1)[1].strip()
    if after_colon:
        if "evidence" in after_colon:
            raise ReleaseDiscoveryError(
                "cannot safely remove inline verification evidence; use block verification form"
            )
        lines[start] = _replace_flow_scalar(header, "status", status)
        return lines

    lines = _set_block_scalar(
        lines, parent_indent=2, parent_key="verification", key="status", value=status
    )
    # Evidence for a previous source identity may never survive candidate promotion.
    lines = _remove_block_child(
        lines, parent_indent=2, parent_key="verification", child_key="evidence"
    )
    return lines


def _accepted_lines(candidate: Mapping[str, Any], nl: str) -> list[str]:
    publication_version = candidate.get("publication_version")
    signal = candidate.get("signal")
    source_revision = candidate.get("source_revision")
    tf_path = candidate.get("tf_path")
    if not isinstance(publication_version, str) or not publication_version:
        raise ReleaseDiscoveryError("candidate publication_version must be non-empty text")
    if not isinstance(signal, str) or not signal:
        raise ReleaseDiscoveryError("candidate signal must be non-empty text")
    source_revision = _commit_sha(source_revision, where="promotion candidate source revision")
    result = [
        f"    accepted:{nl}",
        f"      publication_version: {_scalar(publication_version)}{nl}",
        f"      signal: {_scalar(signal)}{nl}",
        f"      source_revision: {_scalar(source_revision)}{nl}",
    ]
    if tf_path is not None:
        if not isinstance(tf_path, str) or not tf_path:
            raise ReleaseDiscoveryError("candidate tf_path must be non-empty text when present")
        pure = PurePosixPath(tf_path)
        if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            raise ReleaseDiscoveryError("candidate tf_path must be a safe relative path")
        result.append(f"      tf_path: {_scalar(pure.as_posix())}{nl}")
    return result


def _rewrite_accepted(lines: list[str], candidate: Mapping[str, Any]) -> list[str]:
    start, end = _field_range(lines, indent=2, key="version_tracking")
    after_colon = lines[start].split(":", 1)[1].strip()
    if after_colon:
        raise ReleaseDiscoveryError(
            "proposal-mode version_tracking must use block form for byte-preserving accepted-state edits"
        )
    nl = _newline(lines)
    prefix = "    accepted:"
    hits = [i for i in range(start + 1, end) if lines[i].startswith(prefix)]
    if len(hits) > 1:
        raise ReleaseDiscoveryError("duplicate version_tracking.accepted field")
    replacement = _accepted_lines(candidate, nl)
    if not hits:
        lines[end:end] = replacement
        return lines

    accepted_start = hits[0]
    accepted_end = end
    for index in range(accepted_start + 1, end):
        match = _FIELD_KEY.match(lines[index])
        if match is not None and len(match.group("indent")) == 4:
            accepted_end = index
            break
    lines[accepted_start:accepted_end] = replacement
    return lines


def _rewrite_resource_block(
    block: str, *, candidate: Mapping[str, Any], verification_status: str
) -> str:
    lines = block.splitlines(keepends=True)
    source_revision = _commit_sha(
        candidate.get("source_revision"), where="promotion candidate source revision"
    )
    tf_path = candidate.get("tf_path")
    if not isinstance(tf_path, str) or not tf_path:
        raise ReleaseDiscoveryError("proposal candidate must carry a concrete tf_path")
    pure = PurePosixPath(tf_path)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ReleaseDiscoveryError("proposal candidate tf_path must be a safe relative path")

    lines = _set_block_scalar(
        lines, parent_indent=2, parent_key="upstream", key="ref", value=source_revision
    )
    lines = _set_block_scalar(
        lines, parent_indent=2, parent_key="upstream", key="tf_path", value=pure.as_posix()
    )
    lines = _rewrite_verification(lines, verification_status)
    lines = _rewrite_accepted(lines, candidate)
    return "".join(lines)


def apply_promotions_to_text(
    original_text: str,
    parsed_registry: Mapping[str, Any],
    promotions: Sequence[Mapping[str, Any]],
) -> str:
    """Apply reviewed corpus promotions without reserializing unrelated registry bytes.

    The supplied ``parsed_registry`` is part of the stale-state guard: it must be the
    exact YAML interpretation of ``original_text``. Promotions are keyed by stable
    resource id and applied in registry order, so caller order cannot affect output.
    """

    if not promotions:
        return original_text
    reparsed = yaml.safe_load(original_text)
    if reparsed != parsed_registry:
        raise ReleaseDiscoveryError("registry text changed since the supplied parsed state")
    resources = parsed_registry.get("resources") if isinstance(parsed_registry, Mapping) else None
    if not isinstance(resources, list):
        raise ReleaseDiscoveryError("resource registry has malformed resources list")

    by_id: dict[str, Mapping[str, Any]] = {}
    for promotion in promotions:
        if not isinstance(promotion, Mapping):
            raise ReleaseDiscoveryError("promotion record is malformed")
        resource_id = promotion.get("resource_id")
        if not isinstance(resource_id, str) or not resource_id:
            raise ReleaseDiscoveryError("promotion resource_id must be non-empty text")
        if resource_id in by_id:
            raise ReleaseDiscoveryError(f"duplicate promotion for resource {resource_id!r}")
        by_id[resource_id] = promotion

    starts = [i for i, line in enumerate(original_text.splitlines(keepends=True)) if _RESOURCE_START.match(line)]
    all_lines = original_text.splitlines(keepends=True)
    if len(starts) != len(resources):
        raise ReleaseDiscoveryError(
            "cannot byte-preservingly map YAML resources to text blocks; resource layout is unexpected"
        )
    prefix = all_lines[: starts[0]] if starts else all_lines
    blocks: list[str] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(all_lines)
        blocks.append("".join(all_lines[start:end]))

    seen: set[str] = set()
    for index, resource in enumerate(resources):
        if not isinstance(resource, Mapping):
            raise ReleaseDiscoveryError("resource registry contains a malformed resource")
        resource_id = resource.get("id")
        if resource_id not in by_id:
            continue
        promotion = by_id[str(resource_id)]
        tracking = resource.get("version_tracking")
        if not isinstance(tracking, Mapping):
            raise ReleaseDiscoveryError(f"resource {resource_id!r} has no version_tracking state")
        previous = promotion.get("previous")
        current_accepted = tracking.get("accepted")
        comparable_current = copy.deepcopy(current_accepted)
        if isinstance(comparable_current, Mapping) and isinstance(previous, Mapping):
            current_revision = comparable_current.get("source_revision")
            if current_revision is not None:
                comparable_current["source_revision"] = str(current_revision)
        if comparable_current != previous:
            raise ReleaseDiscoveryError(
                f"stale accepted state for resource {resource_id!r}: current state changed from expected previous state"
            )
        candidate = promotion.get("candidate")
        if not isinstance(candidate, Mapping):
            raise ReleaseDiscoveryError(f"promotion candidate for {resource_id!r} is malformed")
        verification_status = promotion.get("verification_status")
        if not isinstance(verification_status, str):
            raise ReleaseDiscoveryError(
                f"promotion verification status for {resource_id!r} is malformed"
            )
        blocks[index] = _rewrite_resource_block(
            blocks[index], candidate=candidate, verification_status=verification_status
        )
        seen.add(str(resource_id))

    missing = sorted(set(by_id) - seen)
    if missing:
        raise ReleaseDiscoveryError(f"promotion targets unknown resources: {missing!r}")
    updated = "".join(prefix) + "".join(blocks)
    # Fail closed if a local edit produced invalid YAML before touching the caller's file.
    yaml.safe_load(updated)
    return updated


def _candidate_mapping(candidate: Any) -> dict[str, str]:
    publication_version = getattr(candidate, "publication_version", None)
    tf_path = getattr(candidate, "tf_path", None)
    if publication_version is None and isinstance(tf_path, str) and tf_path:
        # tf-directories has no release publication; the selected TF directory is
        # its logical publication label while the source revision remains separate.
        publication_version = PurePosixPath(tf_path).name
    if not isinstance(publication_version, str) or not publication_version:
        raise ReleaseDiscoveryError("proposal candidate has no stable publication identity")
    signal = getattr(candidate, "signal", None)
    source_revision = getattr(candidate, "source_revision", None)
    if not isinstance(signal, str) or not signal:
        raise ReleaseDiscoveryError("proposal candidate has no discovery signal")
    source_revision = _commit_sha(source_revision, where="proposal candidate source revision")
    if not isinstance(tf_path, str) or not tf_path:
        raise ReleaseDiscoveryError("proposal candidate has no Text-Fabric path")
    return {
        "publication_version": publication_version,
        "signal": signal,
        "source_revision": source_revision,
        "tf_path": tf_path,
    }


def discover_promotions(
    registry: Mapping[str, Any],
    feature_modules: Sequence[Mapping[str, Any]],
    *,
    api: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Discover all opted-in candidates before returning any mutation proposal."""

    # Lazy import avoids a circular import when check_corpus_versions.py exposes
    # apply_promotions_to_text and also serves as the CLI entrypoint.
    from scripts.check_corpus_versions import (
        discover_dataset_candidate,
        discover_source_candidate,
    )
    from scripts.corpus_version_trust import assess_stage_a_candidate

    resources = registry.get("resources") if isinstance(registry, Mapping) else None
    if not isinstance(resources, list):
        raise ReleaseDiscoveryError("resource registry has malformed resources list")

    promotions: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    for resource in resources:
        if not isinstance(resource, Mapping):
            raise ReleaseDiscoveryError("resource registry contains a malformed resource")
        tracking = resource.get("version_tracking")
        if not isinstance(tracking, Mapping):
            continue
        promotion_policy = tracking.get("promotion")
        if not isinstance(promotion_policy, Mapping):
            raise ReleaseDiscoveryError(
                f"resource {resource.get('id')!r} has malformed promotion policy"
            )
        promotion_mode = promotion_policy.get("mode")
        if promotion_mode == "pinned":
            continue
        source = discover_source_candidate(dict(resource), api)
        if source is None:
            continue
        candidate = discover_dataset_candidate(dict(resource), source, api)
        stage_a = assess_stage_a_candidate(
            resource,
            candidate,
            feature_modules=feature_modules,
        )
        candidate_map = _candidate_mapping(candidate)
        accepted = tracking.get("accepted")
        unchanged = (
            accepted == candidate_map
            and resource.get("upstream", {}).get("ref") == candidate_map["source_revision"]
            and resource.get("upstream", {}).get("tf_path") == candidate_map["tf_path"]
        )
        if unchanged:
            continue
        observation = {
            "resource_id": resource.get("id"),
            "promotion_mode": promotion_mode,
            "previous": copy.deepcopy(accepted),
            "candidate": candidate_map,
            "verification_status": stage_a["verification_status"],
            "verification_pending": stage_a["verification_pending"],
            "license_evidence_status": stage_a["license_evidence_status"],
            "blocking_reasons": list(stage_a["blocking_reasons"]),
            "caveats": list(stage_a["caveats"]),
            "release_url": getattr(candidate, "release_url", None),
        }
        observations.append(observation)
        if stage_a["blocking_reasons"]:
            raise ReleaseDiscoveryError(
                f"candidate for resource {resource.get('id')!r} is blocked: "
                + "; ".join(stage_a["blocking_reasons"])
            )
        if promotion_mode == "proposal":
            promotions.append(
                {
                    "resource_id": resource.get("id"),
                    "previous": copy.deepcopy(accepted),
                    "candidate": candidate_map,
                    "verification_status": stage_a["verification_status"],
                }
            )
        elif promotion_mode != "discovery-only":
            raise ReleaseDiscoveryError(
                f"unsupported promotion mode {promotion_mode!r} for resource {resource.get('id')!r}"
            )

    promotions.sort(key=lambda row: str(row["resource_id"]))
    observations.sort(key=lambda row: str(row["resource_id"]))
    return promotions, observations


def _render_pr_body(observations: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "Automated passive corpus-version proposal. **Review required; this workflow never auto-merges.**",
        "",
        "Each proposed source revision is immutable. Verification may be downgraded when dataset identity changes; licensing claims are never strengthened automatically.",
        "",
    ]
    if not observations:
        lines.append("No corpus version changes were discovered.")
        return "\n".join(lines) + "\n"
    for row in observations:
        candidate = row["candidate"]
        previous = row.get("previous") or {}
        lines.extend(
            [
                f"### `{row['resource_id']}`",
                f"- publication: `{previous.get('publication_version', '<none>')}` → `{candidate['publication_version']}`",
                f"- source: `{previous.get('source_revision', '<none>')}` → `{candidate['source_revision']}`",
                f"- TF path: `{previous.get('tf_path', '<none>')}` → `{candidate['tf_path']}`",
                f"- verification in proposal: `{row['verification_status']}`",
            ]
        )
        if row.get("release_url"):
            lines.append(f"- release: {row['release_url']}")
        for caveat in row.get("caveats", []):
            lines.append(f"- caveat: {caveat}")
        lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Passively discover and propose corpus version updates")
    parser.add_argument("--registry", default="registry/resources.yaml")
    parser.add_argument("--feature-modules", default="registry/feature-modules.yaml")
    parser.add_argument("--report")
    parser.add_argument("--pr-body")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    registry_path = Path(args.registry)
    original = registry_path.read_text(encoding="utf-8")
    registry = yaml.safe_load(original)
    feature_doc = yaml.safe_load(Path(args.feature_modules).read_text(encoding="utf-8"))
    feature_modules = feature_doc.get("resources", []) if isinstance(feature_doc, Mapping) else []
    if not isinstance(feature_modules, list):
        raise ReleaseDiscoveryError("feature-module registry has malformed resources list")

    # Deliberately unauthenticated: Agora's GITHUB_TOKEN is repository-scoped and
    # must not be forwarded to arbitrary public upstream repositories.
    from scripts.check_corpus_versions import public_github_api

    promotions, observations = discover_promotions(
        registry,
        feature_modules,
        api=public_github_api(),
    )
    updated = apply_promotions_to_text(original, registry, promotions)
    if args.apply and updated != original:
        registry_path.write_text(updated, encoding="utf-8")

    report = {
        "schema_version": 1,
        "promotion_count": len(promotions),
        "observations": observations,
    }
    if args.report:
        Path(args.report).write_text(
            json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if args.pr_body:
        Path(args.pr_body).write_text(_render_pr_body(observations), encoding="utf-8")
    if not args.report:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0
