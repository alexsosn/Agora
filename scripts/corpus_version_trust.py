from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence


_REQUIRED_POSITIVE_CLAIMS = frozenset({"materialization", "load", "representative-content"})
_REQUIRED_TRUST_FINGERPRINTS = frozenset(
    {"verification-check", "workflow", "smoke", "promotion-verifier"}
)


def _candidate_value(candidate: Any, name: str) -> Any:
    value = getattr(candidate, name, None)
    if value is None:
        raise ValueError(f"candidate {name} is required")
    return value


def _candidate_tf_version(candidate: Any) -> str:
    path = _candidate_value(candidate, "tf_path")
    if not isinstance(path, str) or not path:
        raise ValueError("candidate tf_path must be non-empty text")
    pure = PurePosixPath(path)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("candidate tf_path must be a safe relative path")
    return pure.name


def assess_stage_a_candidate(
    resource: Mapping[str, Any],
    candidate: Any,
    *,
    feature_modules: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Classify a selected immutable candidate before candidate-specific live evidence.

    Stage A is deliberately conservative: changing effective dataset identity
    invalidates a stale ``verified`` claim, while compatibility/licensing state is
    reported rather than inferred or strengthened.
    """

    if not isinstance(resource, Mapping):
        raise TypeError("resource must be a mapping")
    resource_id = resource.get("id")
    candidate_resource_id = _candidate_value(candidate, "resource_id")
    if not isinstance(resource_id, str) or candidate_resource_id != resource_id:
        raise ValueError("candidate resource identity does not match the registry resource")

    candidate_revision = _candidate_value(candidate, "source_revision")
    candidate_tf_path = _candidate_value(candidate, "tf_path")
    upstream = resource.get("upstream")
    if not isinstance(upstream, Mapping):
        raise ValueError("resource upstream metadata is missing")
    identity_changed = (
        upstream.get("ref") != candidate_revision
        or upstream.get("tf_path") != candidate_tf_path
    )

    verification = resource.get("verification")
    current_status = verification.get("status") if isinstance(verification, Mapping) else None
    if current_status not in {"experimental", "community", "verified"}:
        raise ValueError("resource verification status is missing or unsupported")
    verification_status = (
        "community" if identity_changed and current_status == "verified" else current_status
    )

    blocking_reasons: list[str] = []
    candidate_parent_version = _candidate_tf_version(candidate)
    for module in feature_modules:
        if not isinstance(module, Mapping) or module.get("parent") != resource_id:
            continue
        compatibility = module.get("compatibility")
        parent_versions = (
            compatibility.get("parent_versions")
            if isinstance(compatibility, Mapping)
            else None
        )
        module_id = module.get("id", "<unknown-module>")
        if (
            not isinstance(parent_versions, list)
            or not all(isinstance(value, str) and value for value in parent_versions)
        ):
            blocking_reasons.append(
                f"feature module {module_id!r} has malformed parent compatibility metadata"
            )
            continue
        if candidate_parent_version not in parent_versions:
            blocking_reasons.append(
                f"feature module {module_id!r} is not compatible with candidate parent version "
                f"{candidate_parent_version!r}"
            )

    licenses = resource.get("licenses")
    evidence = licenses.get("evidence") if isinstance(licenses, Mapping) else None
    license_status = evidence.get("status") if isinstance(evidence, Mapping) else None
    caveats: list[str] = []
    if license_status not in {"resolved", None}:
        caveats.append(
            f"license/redistribution evidence remains {license_status!r}; candidate adoption "
            "must not strengthen the existing licensing claim"
        )

    return {
        "resource_id": resource_id,
        "source_revision": candidate_revision,
        "tf_path": candidate_tf_path,
        "verification_status": verification_status,
        "verification_pending": identity_changed,
        "license_evidence_status": license_status,
        "blocking_reasons": blocking_reasons,
        "caveats": caveats,
    }


def _fingerprint_drift(
    trusted: Mapping[str, Any], candidate: Mapping[str, Any]
) -> list[str]:
    reasons: list[str] = []
    for name in sorted(_REQUIRED_TRUST_FINGERPRINTS):
        trusted_value = trusted.get(name)
        candidate_value = candidate.get(name)
        if not isinstance(trusted_value, str) or not trusted_value:
            reasons.append(f"trusted base {name} fingerprint is missing")
            continue
        if not isinstance(candidate_value, str) or not candidate_value:
            reasons.append(f"candidate {name} fingerprint is missing")
            continue
        if trusted_value != candidate_value:
            reasons.append(
                f"candidate {name} fingerprint differs from the trusted base"
            )
    return reasons


def _evidence_reasons(
    resource_id: str,
    candidate: Any,
    candidate_pr_head: str,
    evidence: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    if evidence.get("pr_head") != candidate_pr_head:
        reasons.append("verification evidence is bound to a different PR head")
    if evidence.get("resource_id") != resource_id:
        reasons.append("verification evidence is bound to a different resource")
    if evidence.get("source_revision") != _candidate_value(candidate, "source_revision"):
        reasons.append("verification evidence is bound to a different source revision")
    if evidence.get("tf_path") != _candidate_value(candidate, "tf_path"):
        reasons.append("verification evidence is bound to a different TF path")
    if evidence.get("check_kind") == "known-issue-canary":
        reasons.append("known-issue canary evidence cannot satisfy positive promotion claims")
    if evidence.get("evidence_level") != "verified":
        reasons.append("promotion requires verified-level live evidence")
    claims = evidence.get("claims")
    claim_set = set(claims) if isinstance(claims, list) and all(isinstance(c, str) for c in claims) else set()
    missing = sorted(_REQUIRED_POSITIVE_CLAIMS - claim_set)
    if missing:
        reasons.append(
            "verification evidence is missing required positive claims: " + ", ".join(missing)
        )
    check_id = evidence.get("check_id")
    if not isinstance(check_id, str) or not check_id:
        reasons.append("verification evidence has no stable check id")
    return reasons


def assess_stage_b_promotion(
    resource_id: str,
    candidate: Any,
    *,
    candidate_pr_head: str,
    evidence: Sequence[Mapping[str, Any]],
    trusted_base_fingerprints: Mapping[str, Any],
    candidate_fingerprints: Mapping[str, Any],
) -> dict[str, Any]:
    """Decide whether exact candidate evidence may restore ``verified`` status.

    The candidate cannot self-authorize by changing an evidence producer or the
    promotion verifier: those surfaces must remain byte-equivalent to trusted base
    fingerprints for automatic Stage-B promotion.
    """

    if _candidate_value(candidate, "resource_id") != resource_id:
        raise ValueError("candidate resource identity does not match promotion subject")
    if not isinstance(candidate_pr_head, str) or not candidate_pr_head:
        raise ValueError("candidate_pr_head must be non-empty text")
    if not isinstance(trusted_base_fingerprints, Mapping) or not isinstance(
        candidate_fingerprints, Mapping
    ):
        raise TypeError("trust fingerprints must be mappings")

    blocking_reasons = _fingerprint_drift(
        trusted_base_fingerprints, candidate_fingerprints
    )

    valid_evidence = False
    evidence_failures: list[str] = []
    for row in evidence:
        if not isinstance(row, Mapping):
            evidence_failures.append("verification evidence row is malformed")
            continue
        reasons = _evidence_reasons(resource_id, candidate, candidate_pr_head, row)
        if not reasons:
            valid_evidence = True
            break
        evidence_failures.extend(reasons)

    if not valid_evidence:
        if evidence_failures:
            # Keep the result deterministic and concise while retaining every
            # distinct trust failure observed across supplied evidence rows.
            blocking_reasons.extend(dict.fromkeys(evidence_failures))
        else:
            blocking_reasons.append("no exact candidate verification evidence was supplied")

    can_promote = not blocking_reasons and valid_evidence
    return {
        "resource_id": resource_id,
        "can_promote": can_promote,
        "verification_status": "verified" if can_promote else "community",
        "promoted_subjects": [resource_id] if can_promote else [],
        "blocking_reasons": blocking_reasons,
    }
