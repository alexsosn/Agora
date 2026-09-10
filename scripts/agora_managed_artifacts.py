from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import uuid
from typing import Any, Mapping, Sequence


REQUEST_IDENTITY_SCHEMA_VERSION = 1
ARTIFACT_RECEIPT_SCHEMA_VERSION = 1
PAYLOAD_MANIFEST_SCHEMA_VERSION = 1
MATERIALIZATION_HOST_SCHEMA_VERSION = 1
ARTIFACT_ID_RE = re.compile(r"^art-[0-9a-f]{32}$")
_HEX_40_RE = re.compile(r"^[0-9a-f]{40}$")
_HEX_64_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ReusableRequestIdentity:
    """Canonical, privacy-bounded identity for one reusable materialization request."""

    key: str
    canonical_json: str


@dataclass(frozen=True)
class ArtifactPaths:
    """Private paths derived only from one validated opaque artifact identifier."""

    object: Path
    payload: Path
    receipt: Path
    staging: Path


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
        raise ValueError(f"value contains non-canonical JSON data: {exc}") from exc


def _validated_json_value(value: Any, *, name: str) -> Any:
    """Validate the exact JSON data model without Python's coercive extensions."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{name} must contain only finite JSON numbers")
        return value
    if isinstance(value, list):
        return [
            _validated_json_value(item, name=f"{name}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{name} object keys must be strings")
            normalized[key] = _validated_json_value(item, name=f"{name}.{key}")
        return normalized
    raise ValueError(
        f"{name} must contain only canonical JSON objects, arrays, strings, numbers, booleans, or null"
    )


def _validated_options(options: Any) -> dict[str, Any]:
    if not isinstance(options, Mapping):
        raise ValueError("options must be a JSON object mapping")
    normalized = _validated_json_value(options, name="options")
    assert isinstance(normalized, dict)
    return normalized


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
        "options": _validated_options(options),
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


def _safe_relative_path(value: Any, *, name: str) -> str:
    text = _require_text(value, name=name)
    if "\\" in text:
        raise ValueError(f"{name} must use a contained POSIX-style relative path")
    path = PurePosixPath(text)
    if path.is_absolute() or text != path.as_posix() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{name} must be a contained normalized relative path")
    return text


def _validated_required_paths(required_paths: Sequence[str]) -> tuple[str, ...]:
    if isinstance(required_paths, (str, bytes)):
        raise TypeError("required_paths must be a sequence of relative paths")
    normalized = tuple(
        _safe_relative_path(value, name="required_path") for value in required_paths
    )
    if len(normalized) != len(set(normalized)):
        raise ValueError("required_paths contains duplicate paths")
    return normalized


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _contained_root(path: Path, *, name: str) -> Path:
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f"{name} cannot be a symlink")
    if not path.is_dir():
        raise ValueError(f"{name} must be an existing directory")
    return path.resolve()


def _scan_payload(payload: Path, *, allow_cfm: bool) -> list[dict[str, str]]:
    root = _contained_root(payload, name="payload")
    entries: list[dict[str, str]] = []

    def visit(directory: Path, rel_prefix: PurePosixPath | None = None) -> None:
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise ValueError(f"payload cannot be inspected: {exc}") from exc
        for item in children:
            rel = PurePosixPath(item.name) if rel_prefix is None else rel_prefix / item.name
            rel_name = rel.as_posix()
            try:
                is_link = item.is_symlink()
            except OSError as exc:
                raise ValueError(f"payload entry {rel_name!r} cannot be inspected: {exc}") from exc
            if is_link:
                raise ValueError(f"payload symlink is forbidden: {rel_name}")
            if rel.parts[0] == ".cfm":
                if not allow_cfm:
                    raise ValueError("top-level .cfm is reserved for Context-Fabric consumer state")
                # Consumer state is mutable and excluded from the canonical payload
                # identity, but every descendant must still be an ordinary contained
                # file/directory and never a symlink.
                if item.is_dir(follow_symlinks=False):
                    visit_cfm(Path(item.path), rel)
                elif not item.is_file(follow_symlinks=False):
                    raise ValueError(f"unsupported .cfm payload entry kind: {rel_name}")
                continue
            candidate = Path(item.path)
            resolved = candidate.resolve(strict=False)
            if not resolved.is_relative_to(root):
                raise ValueError(f"payload entry escapes containment: {rel_name}")
            if item.is_dir(follow_symlinks=False):
                entries.append({"path": rel_name, "kind": "directory"})
                visit(candidate, rel)
            elif item.is_file(follow_symlinks=False):
                entries.append(
                    {"path": rel_name, "kind": "file", "sha256": _sha256_file(candidate)}
                )
            else:
                raise ValueError(f"unsupported payload entry kind: {rel_name}")

    def visit_cfm(directory: Path, rel_prefix: PurePosixPath) -> None:
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise ValueError(f".cfm consumer state cannot be inspected: {exc}") from exc
        for item in children:
            rel = rel_prefix / item.name
            rel_name = rel.as_posix()
            if item.is_symlink():
                raise ValueError(f".cfm consumer-state symlink is forbidden: {rel_name}")
            candidate = Path(item.path)
            if not candidate.resolve(strict=False).is_relative_to(root):
                raise ValueError(f".cfm consumer state escapes containment: {rel_name}")
            if item.is_dir(follow_symlinks=False):
                visit_cfm(candidate, rel)
            elif not item.is_file(follow_symlinks=False):
                raise ValueError(f"unsupported .cfm consumer-state entry kind: {rel_name}")

    visit(Path(payload))
    return entries


def _manifest_digest(entries: Sequence[Mapping[str, Any]]) -> str:
    canonical = _canonical_json(
        {"schema_version": PAYLOAD_MANIFEST_SCHEMA_VERSION, "entries": list(entries)}
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_payload_manifest(
    payload: Path,
    *,
    required_paths: Sequence[str],
) -> dict[str, Any]:
    """Build the immutable converter/host payload identity before .cfm exists."""

    required = _validated_required_paths(required_paths)
    root = _contained_root(Path(payload), name="payload")
    entries = _scan_payload(root, allow_cfm=False)
    by_path = {entry["path"]: entry for entry in entries}
    for required_path in required:
        entry = by_path.get(required_path)
        if entry is None:
            raise ValueError(f"required payload path is missing: {required_path}")
    return {
        "schema_version": PAYLOAD_MANIFEST_SCHEMA_VERSION,
        "entries": entries,
        "digest_sha256": _manifest_digest(entries),
    }


def _validated_manifest_document(manifest: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, Mapping):
        raise TypeError("payload manifest must be a mapping")
    if set(manifest) != {"schema_version", "entries", "digest_sha256"}:
        raise ValueError("payload manifest has unexpected or missing fields")
    if manifest.get("schema_version") != PAYLOAD_MANIFEST_SCHEMA_VERSION:
        raise ValueError("payload manifest schema version is unsupported")
    raw_entries = manifest.get("entries")
    if not isinstance(raw_entries, list):
        raise ValueError("payload manifest entries must be a list")
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_entries):
        if not isinstance(raw, Mapping):
            raise ValueError(f"payload manifest entry {index} is malformed")
        kind = raw.get("kind")
        expected_keys = {"path", "kind", "sha256"} if kind == "file" else {"path", "kind"}
        if set(raw) != expected_keys or kind not in {"file", "directory"}:
            raise ValueError(f"payload manifest entry {index} has invalid kind or fields")
        path = _safe_relative_path(raw.get("path"), name=f"payload manifest entry {index}.path")
        if path == ".cfm" or path.startswith(".cfm/"):
            raise ValueError("payload manifest cannot claim reserved .cfm consumer state")
        if path in seen:
            raise ValueError(f"payload manifest contains duplicate path: {path}")
        seen.add(path)
        entry = {"path": path, "kind": kind}
        if kind == "file":
            entry["sha256"] = _require_digest(
                raw.get("sha256"), name=f"payload manifest entry {index}.sha256"
            )
        entries.append(entry)
    if entries != sorted(entries, key=lambda item: item["path"]):
        raise ValueError("payload manifest entries must be canonically path-sorted")
    digest = _require_digest(manifest.get("digest_sha256"), name="payload manifest digest_sha256")
    if digest != _manifest_digest(entries):
        raise ValueError("payload manifest digest does not match its entries")
    return {
        "schema_version": PAYLOAD_MANIFEST_SCHEMA_VERSION,
        "entries": entries,
        "digest_sha256": digest,
    }


def validate_payload_manifest(
    payload: Path,
    manifest: Mapping[str, Any],
    *,
    required_paths: Sequence[str],
) -> str:
    """Validate immutable payload bytes while permitting only later .cfm state."""

    expected = _validated_manifest_document(manifest)
    required = _validated_required_paths(required_paths)
    actual_entries = _scan_payload(Path(payload), allow_cfm=True)
    if actual_entries != expected["entries"]:
        raise ValueError("payload integrity does not match the canonical manifest")
    by_path = {entry["path"]: entry for entry in actual_entries}
    for required_path in required:
        if required_path not in by_path:
            raise ValueError(f"required payload path is missing: {required_path}")
    return expected["digest_sha256"]


def _validated_plugin(plugin: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(plugin, Mapping):
        raise TypeError("plugin must be a mapping")
    return {
        "id": _require_text(plugin.get("id"), name="plugin.id"),
        "repository": _require_text(plugin.get("repository"), name="plugin.repository"),
        "ref": _require_commit(plugin.get("ref"), name="plugin.ref"),
        "version": _require_text(plugin.get("version"), name="plugin.version"),
    }


def _validated_cacheability(cacheability: Mapping[str, Any], *, disposition: str) -> dict[str, Any]:
    if not isinstance(cacheability, Mapping):
        raise TypeError("cacheability must be a mapping")
    mode = cacheability.get("mode")
    reuse_allowed = cacheability.get("reuse_allowed")
    attestation = cacheability.get("attestation_sha256")
    if disposition == "reusable":
        if mode != "reusable" or reuse_allowed is not True:
            raise ValueError("reusable artifact requires reusable cacheability authorization")
        return {
            "mode": "reusable",
            "reuse_allowed": True,
            "attestation_sha256": _require_digest(
                attestation, name="cacheability.attestation_sha256"
            ),
        }
    if mode not in {"unknown", "non-reusable"} or reuse_allowed is not False:
        raise ValueError("one-shot artifact requires unknown or non-reusable cacheability")
    if attestation is not None:
        raise ValueError("one-shot cacheability cannot carry a reusable attestation")
    return {"mode": mode, "reuse_allowed": False, "attestation_sha256": None}


def _validated_sandbox(sandbox: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(sandbox, Mapping):
        raise TypeError("sandbox must be a mapping")
    if set(sandbox) != {"policy", "backend"}:
        raise ValueError("sandbox receipt must contain exactly policy and backend")
    return {
        "policy": _require_text(sandbox.get("policy"), name="sandbox.policy"),
        "backend": _require_text(sandbox.get("backend"), name="sandbox.backend"),
    }


def build_artifact_receipt(
    *,
    artifact_id: str,
    disposition: str,
    request_key: str | None,
    plugin: Mapping[str, Any],
    materializer_id: str,
    execution_identity_sha256: str,
    cacheability: Mapping[str, Any],
    source: Mapping[str, Any],
    manifest_sha256: str,
    materializer_contract_sha256: str,
    output_format: str,
    required_paths: Sequence[str],
    payload_manifest: Mapping[str, Any],
    sandbox: Mapping[str, Any],
) -> dict[str, Any]:
    """Construct the immutable local-only managed-artifact trust receipt."""

    artifact = validate_artifact_id(artifact_id)
    if disposition not in {"reusable", "one-shot"}:
        raise ValueError("artifact disposition must be reusable or one-shot")
    if disposition == "reusable":
        key = _require_digest(request_key, name="reusable request_key")
    else:
        if request_key is not None:
            raise ValueError("one-shot artifact must not carry a request key")
        key = None

    return {
        "schema_version": ARTIFACT_RECEIPT_SCHEMA_VERSION,
        "request_identity_schema_version": REQUEST_IDENTITY_SCHEMA_VERSION,
        "host_schema_version": MATERIALIZATION_HOST_SCHEMA_VERSION,
        "artifact_id": artifact,
        "disposition": disposition,
        "request_key": key,
        "plugin": _validated_plugin(plugin),
        "materializer": {
            "id": _require_text(materializer_id, name="materializer_id"),
            "manifest_sha256": _require_digest(manifest_sha256, name="manifest_sha256"),
            "contract_sha256": _require_digest(
                materializer_contract_sha256, name="materializer_contract_sha256"
            ),
        },
        "execution_identity_sha256": _require_digest(
            execution_identity_sha256, name="execution_identity_sha256"
        ),
        "cacheability": _validated_cacheability(cacheability, disposition=disposition),
        "source": _validated_source(source),
        "output_format": _require_text(output_format, name="output_format"),
        "required_paths": list(_validated_required_paths(required_paths)),
        "payload_manifest": _validated_manifest_document(payload_manifest),
        "sandbox": _validated_sandbox(sandbox),
        "redistribution": "local-only",
    }


def validate_artifact_receipt(
    receipt: Mapping[str, Any],
    *,
    artifact_id: str,
) -> dict[str, Any]:
    """Validate the receipt without granting authority to unknown extra fields."""

    if not isinstance(receipt, Mapping):
        raise TypeError("artifact receipt must be a mapping")
    allowed = {
        "schema_version",
        "request_identity_schema_version",
        "host_schema_version",
        "artifact_id",
        "disposition",
        "request_key",
        "plugin",
        "materializer",
        "execution_identity_sha256",
        "cacheability",
        "source",
        "output_format",
        "required_paths",
        "payload_manifest",
        "sandbox",
        "redistribution",
    }
    if set(receipt) != allowed:
        raise ValueError("artifact receipt has unexpected or missing authority-bearing fields")
    if receipt.get("schema_version") != ARTIFACT_RECEIPT_SCHEMA_VERSION:
        raise ValueError("artifact receipt schema version is unsupported")
    if receipt.get("request_identity_schema_version") != REQUEST_IDENTITY_SCHEMA_VERSION:
        raise ValueError("artifact receipt request identity schema version is unsupported")
    if receipt.get("host_schema_version") != MATERIALIZATION_HOST_SCHEMA_VERSION:
        raise ValueError("artifact receipt host schema version is unsupported")
    if receipt.get("redistribution") != "local-only":
        raise ValueError("managed artifacts are local-only")

    expected_artifact = validate_artifact_id(artifact_id)
    if receipt.get("artifact_id") != expected_artifact:
        raise ValueError("artifact receipt id does not match requested artifact")
    disposition = receipt.get("disposition")
    if disposition not in {"reusable", "one-shot"}:
        raise ValueError("artifact receipt disposition is invalid")
    request_key = receipt.get("request_key")
    if disposition == "reusable":
        _require_digest(request_key, name="reusable request_key")
    elif request_key is not None:
        raise ValueError("one-shot artifact receipt must not carry a request key")

    _validated_plugin(receipt.get("plugin"))
    materializer = receipt.get("materializer")
    if not isinstance(materializer, Mapping) or set(materializer) != {"id", "manifest_sha256", "contract_sha256"}:
        raise ValueError("artifact receipt materializer binding is malformed")
    _require_text(materializer.get("id"), name="materializer.id")
    _require_digest(materializer.get("manifest_sha256"), name="materializer.manifest_sha256")
    _require_digest(materializer.get("contract_sha256"), name="materializer.contract_sha256")
    _require_digest(receipt.get("execution_identity_sha256"), name="execution_identity_sha256")
    _validated_cacheability(receipt.get("cacheability"), disposition=disposition)

    source = receipt.get("source")
    if not isinstance(source, Mapping) or set(source) != {"type", "tree_sha256", "resolved_commit"}:
        raise ValueError("artifact receipt source identity is malformed")
    _validated_source(source)
    _require_text(receipt.get("output_format"), name="output_format")
    required = receipt.get("required_paths")
    if not isinstance(required, list):
        raise ValueError("artifact receipt required_paths must be a list")
    _validated_required_paths(required)
    _validated_manifest_document(receipt.get("payload_manifest"))
    _validated_sandbox(receipt.get("sandbox"))
    return dict(receipt)


class ManagedArtifactStore:
    """Path-safe private layout primitive for later transactional publication slices."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def ensure_private_root(self) -> Path:
        if self.root.is_symlink():
            raise ValueError("managed artifact store root cannot be a symlink")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            os.chmod(self.root, 0o700)
        return self.root

    def _assert_safe_existing(self, path: Path) -> None:
        root = self.root.resolve(strict=False)
        candidate = Path(path)
        try:
            relative = candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("managed artifact path escapes store containment") from exc

        current = self.root
        if current.exists() and current.is_symlink():
            raise ValueError("managed artifact store root cannot be a symlink")
        for part in relative.parts:
            current = current / part
            if current.exists() or current.is_symlink():
                try:
                    mode = current.lstat().st_mode
                except OSError as exc:
                    raise ValueError(f"managed artifact path cannot be inspected: {exc}") from exc
                if stat.S_ISLNK(mode):
                    raise ValueError("managed artifact path cannot traverse a symlink")
        if not candidate.resolve(strict=False).is_relative_to(root):
            raise ValueError("managed artifact path escapes store containment")

    def paths(self, artifact_id: str, *, require_safe_existing: bool = False) -> ArtifactPaths:
        artifact = validate_artifact_id(artifact_id)
        object_path = self.root / "objects" / artifact
        paths = ArtifactPaths(
            object=object_path,
            payload=object_path / "payload",
            receipt=object_path / "receipt.json",
            staging=self.root / "tmp" / f"{artifact}.stage",
        )
        if require_safe_existing:
            for candidate in (paths.object, paths.payload, paths.receipt, paths.staging):
                self._assert_safe_existing(candidate)
        return paths
