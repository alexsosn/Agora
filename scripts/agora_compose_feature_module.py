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


def materialize_managed_feature_module(
    *,
    resolver: Any,
    plugin_id: str,
    materializer_id: str,
    source: Path | None,
    output: Path,
    requested_version: str | None = None,
    install_root: Path | None = None,
    registry_path: Path | None = None,
) -> Path:
    """Run a registered feature-module producer under a pinned parent lease.

    RED3c: internal orchestration building block, *not* a CLI or general
    authorization surface. A later gate must construct the Context-Fabric
    resolver from trusted Agora configuration and keep arbitrary callers from
    substituting it. This function never approves or installs plugin code.

    Parent preparation runs outside the materializer sandbox. The managed
    snapshot remains leased across the entire registered execution, including
    final artifact publication and environment integrity re-check.
    """
    from scripts import agora_materialize_registered as registered
    from scripts.agora_materialize import load_manifest, select_materializer

    manifest_path = registered.resolve_installed_manifest(
        plugin_id, install_root=install_root, registry_path=registry_path,
    )
    manifest = load_manifest(manifest_path)
    spec = select_materializer(manifest, materializer_id)
    if "parent_input" not in spec:
        raise ValueError(
            f"materializer {materializer_id!r} has no parent_input; "
            "it is not a parent-dependent feature module"
        )
    binding = resolve_managed_parent(
        spec, resolver, requested_version=requested_version,
    )
    # GitStore.acquire_cache_lease validates that the exact managed object
    # still exists and is a valid corpus snapshot. Eviction cannot race the
    # converter while this shared lease is held.
    with resolver.store.acquire_cache_lease(binding.path):
        return registered.materialize_registered(
            plugin_id=plugin_id,
            materializer_id=materializer_id,
            output=Path(output),
            source=None if source is None else Path(source),
            sandbox="required",
            install_root=install_root,
            registry_path=registry_path,
            parent=binding,
        )



def _bundled_context_fabric_resolver(
    *, cache_dir: Path | None = None,
) -> Any:
    """Build Context-Fabric from Agora's own bundled, pinned resource catalog.

    The caller may choose a cache *location* but not supply a catalog, resolver,
    parent corpus directory or trusted marker. This deliberately differs from
    the injected-resolver unit testing seam above.
    """
    import sys

    source_dir = (
        Path(__file__).resolve().parents[1] / "plugins" / "context-fabric" / "src"
    ).resolve(strict=True)
    plugin_root = source_dir.parent
    if not (plugin_root / "resources" / "catalog.yaml").is_file():
        raise RuntimeError("Agora bundled Context-Fabric catalog is unavailable")
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))

    from agora_context_fabric import catalog as catalog_module
    from agora_context_fabric import gitstore as store_module
    from agora_context_fabric import resolver as resolver_module
    from agora_context_fabric import server as server_module

    # A different Context-Fabric installation may already be in sys.modules
    # when Agora is imported from an editable clone. Do not silently let it
    # redefine the "trusted" bundled resource/corpus identity.
    for module in (
        catalog_module, store_module, resolver_module, server_module,
    ):
        file_path = Path(module.__file__).resolve(strict=True)
        if not file_path.is_relative_to(source_dir):
            raise RuntimeError(
                "Context-Fabric module was imported from outside the Agora bundle"
            )

    selected_cache = (
        Path(cache_dir) if cache_dir is not None else server_module.DEFAULT_CACHE_DIR
    )
    catalog = catalog_module.Catalog.from_plugin_root(plugin_root)
    store = store_module.GitStore(selected_cache)
    return resolver_module.ContextFabricResolver(catalog, store)


def materialize_registered_managed_feature_module(
    *,
    plugin_id: str,
    materializer_id: str,
    output: Path,
    source: Path | None = None,
    requested_version: str | None = None,
    cache_dir: Path | None = None,
    install_root: Path | None = None,
    registry_path: Path | None = None,
) -> Path:
    """Use Agora's bundled corpus catalog for a registered feature module.

    Internal integration entrypoint, not yet a public CLI/MCP tool. Its caller
    cannot provide a resolver, arbitrary parent path, resource catalog or
    `trusted` boolean. The lower-level helper keeps the parent cache leased
    throughout the verified registered materializer's sandboxed execution.
    """
    resolver = _bundled_context_fabric_resolver(cache_dir=cache_dir)
    return materialize_managed_feature_module(
        resolver=resolver,
        plugin_id=plugin_id,
        materializer_id=materializer_id,
        source=source,
        output=output,
        requested_version=requested_version,
        install_root=install_root,
        registry_path=registry_path,
    )
