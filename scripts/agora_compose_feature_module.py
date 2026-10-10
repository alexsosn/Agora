"""Bounded Context-Fabric parent resolver for materializer feature modules.

RED3a is deliberately resolution-only. Neither this module nor its callers may
treat a caller-supplied path as a trusted parent; all trusted bindings originate
in the Context-Fabric resolver's immutable corpus snapshot store.
"""
from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

from scripts.agora_materialize import ParentBinding


_COMMIT_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")


def _relative_parts(raw: str) -> tuple[str, ...]:
    if not isinstance(raw, str) or not raw:
        raise ValueError("parent Text-Fabric required path is empty")
    path = PurePosixPath(raw.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or path.as_posix() == ".":
        raise ValueError(f"parent Text-Fabric path must stay within its snapshot: {raw!r}")
    return path.parts


def _no_symlink_components(root: Path, parts: tuple[str, ...]) -> Path:
    candidate = root
    for part in parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError(f"managed parent snapshot contains a symlink: {candidate}")
    return candidate


def resolve_managed_parent(
    materializer: dict[str, Any],
    resolver: Any,
    *,
    requested_version: str | None = None,
) -> ParentBinding:
    """Resolve one declared corpus dependency to a verified managed snapshot.

    The resolver is the trusted Context-Fabric runtime, not an arbitrary user
    path. This function does not install, execute, publish, or lock anything;
    the caller must hold its cache lease while executing in a later #135 gate.
    """
    declared = materializer.get("parent_input")
    if not isinstance(declared, dict):
        raise ValueError("materializer has no parent_input declaration")
    resource_id = declared["resource"]
    allowed_versions = tuple(declared["parent_versions"])
    resource = resolver.catalog.get(resource_id)
    if resource.kind != "corpus":
        raise ValueError(
            f"parent resource {resource_id!r} must be a corpus, not {resource.kind!r}"
        )

    # For a single permitted version, do not consult changing upstream defaults.
    # For more than one, use the resolver's canonical default only if compatible;
    # otherwise demand an explicit compatible version rather than guessing.
    if requested_version is not None:
        version = requested_version
    elif len(allowed_versions) == 1:
        version = allowed_versions[0]
    else:
        version = resolver.default_corpus_version(resource_id)
    if version not in allowed_versions:
        raise ValueError(
            f"parent version {version!r} is incompatible with {resource_id!r}; "
            f"accepted versions: {', '.join(allowed_versions)}"
        )

    prepared = resolver.prepare(resource_id, version=version)
    if (
        prepared.resource_id != resource_id
        or prepared.member_id is not None
        or prepared.version != version
    ):
        raise ValueError("resolved parent identity/version does not match the declared corpus")
    revision = prepared.source_revision
    if not isinstance(revision, str) or not _COMMIT_RE.fullmatch(revision):
        raise ValueError("resolved parent must have an immutable source revision")

    # Check both structural cache identity and the actual path: a real TF
    # directory outside snapshots cannot be promoted to a trusted resource.
    # No .resolve() on the assembled expected path until symlinks are checked.
    snapshot_directory = Path(resolver.store.snapshots_dir).expanduser()
    if snapshot_directory.is_symlink():
        raise ValueError("managed parent snapshot root must not be a symlink")
    snapshot_root = snapshot_directory.resolve(strict=True)
    relative = prepared.relative_path
    if relative == ".":
        parts = ("__root__",)
    else:
        parts = _relative_parts(relative)
    root_parts = (
        resolver.store.safe_cache_key(resource_id), revision, "corpora", *parts,
    )
    expected = _no_symlink_components(snapshot_root, root_parts)
    supplied_path = Path(prepared.path).expanduser()
    if supplied_path.is_symlink() or not supplied_path.is_dir():
        raise ValueError("managed parent snapshot must be a real directory")
    actual = supplied_path.resolve(strict=True)
    if actual != expected:
        raise ValueError(
            f"resolved parent path is not the expected immutable managed snapshot: {actual}"
        )

    for raw in declared["required_paths"]:
        candidate = _no_symlink_components(expected, _relative_parts(raw))
        if not candidate.is_file():
            raise ValueError(f"managed parent snapshot lacks required Text-Fabric file {raw!r}")

    return ParentBinding(
        path=actual,
        resource_id=resource_id,
        version=version,
        source_revision=revision,
        trusted=True,
        relative_path=prepared.relative_path,
    )
