from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import uuid
from typing import Any, Mapping


REQUEST_IDENTITY_SCHEMA_VERSION = 1
MATERIALIZATION_HOST_SCHEMA_VERSION = 1
ARTIFACT_ID_RE = re.compile(r"^art-[0-9a-f]{32}$")
_HEX_40_RE = re.compile(r"^[0-9a-f]{40}$")
_HEX_64_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ReusableRequestIdentity:
    """Canonical, privacy-bounded identity for one reusable materialization request."""

    key: str
    canonical_json: str


def _require_text(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be non-empty text")
    return value


def _require_digest(value: Any, *, name: str) -> str:
    text = _require_text(value, name=name)
    if _HEX_64_RE.fullmatch(text) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return text


def _require_commit(value: Any, *, name: str) -> str:
    text = _require_text(value, name=name)
    if _HEX_40_RE.fullmatch(text) is None:
        raise ValueError(f"{name} must be a lowercase immutable 40-hex Git commit")
    return text


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"request identity contains non-canonical JSON data: {exc}") from exc


def _validated_authorization(authorization: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(authorization, Mapping):
        raise TypeError("authorization must be a mapping")
    if authorization.get("mode") != "reusable" or authorization.get("reuse_allowed") is not True:
        raise ValueError("reusable request identity requires reusable authorization")

    return {
        "plugin_id": _require_text(authorization.get("plugin_id"), name="authorization.plugin_id"),
        "materializer_id": _require_text(
            authorization.get("materializer_id"), name="authorization.materializer_id"
        ),
        "plugin_ref": _require_commit(
            authorization.get("plugin_ref"), name="authorization.plugin_ref"
        ),
        "execution_identity_sha256": _require_digest(
            authorization.get("execution_identity_sha256"),
            name="authorization.execution_identity_sha256",
        ),
        "attestation_sha256": _require_digest(
            authorization.get("attestation_sha256"),
            name="authorization.attestation_sha256",
        ),
    }


def _validated_source(source: Mapping[str, Any]) -> dict[str, str | None]:
    if not isinstance(source, Mapping):
        raise TypeError("source must be a mapping")
    source_type = _require_text(source.get("type"), name="source.type")
    tree_sha256 = _require_digest(source.get("tree_sha256"), name="source.tree_sha256")
    revision = source.get("resolved_commit")
    if revision is not None:
        revision = _require_commit(revision, name="source.resolved_commit")
    return {
        "type": source_type,
        "tree_sha256": tree_sha256,
        "resolved_commit": revision,
    }


def build_reusable_request_identity(
    *,
    authorization: Mapping[str, Any],
    source: Mapping[str, Any],
    plugin_repository: str,
    plugin_version: str,
    manifest_sha256: str,
    materializer_contract_sha256: str,
    output_format: str,
    sandbox_policy: str,
    options: Any,
) -> ReusableRequestIdentity:
    """Build a deterministic key only from trusted, portable request identity inputs."""

    auth = _validated_authorization(authorization)
    document = {
        "schema_version": REQUEST_IDENTITY_SCHEMA_VERSION,
        "host_schema_version": MATERIALIZATION_HOST_SCHEMA_VERSION,
        "plugin": {
            "id": auth["plugin_id"],
            "repository": _require_text(plugin_repository, name="plugin_repository"),
            "ref": auth["plugin_ref"],
            "version": _require_text(plugin_version, name="plugin_version"),
        },
        "materializer": {
            "id": auth["materializer_id"],
            "manifest_sha256": _require_digest(manifest_sha256, name="manifest_sha256"),
            "contract_sha256": _require_digest(
                materializer_contract_sha256,
                name="materializer_contract_sha256",
            ),
        },
        "execution": {
            "identity_sha256": auth["execution_identity_sha256"],
            "cacheability_attestation_sha256": auth["attestation_sha256"],
            "sandbox_policy": _require_text(sandbox_policy, name="sandbox_policy"),
        },
        "source": _validated_source(source),
        "output_format": _require_text(output_format, name="output_format"),
        "options": options,
    }
    canonical = _canonical_json(document)
    key = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return ReusableRequestIdentity(key=key, canonical_json=canonical)


def new_artifact_id() -> str:
    """Return a store-independent opaque artifact instance identifier."""

    return f"art-{uuid.uuid4().hex}"


def validate_artifact_id(value: Any) -> str:
    """Validate an opaque artifact identifier without touching the filesystem."""

    if not isinstance(value, str):
        raise TypeError("artifact_id must be text")
    if ARTIFACT_ID_RE.fullmatch(value) is None:
        raise ValueError("artifact_id must be an Agora-generated opaque artifact id")
    return value
