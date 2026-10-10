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


from contextlib import ExitStack
from dataclasses import dataclass


@dataclass(frozen=True)
class ModulePublicationPlan:
    module_id: str
    plugin_id: str
    materializer_id: str
    source: Path | None
    parent_id: str
    parent_revision: str
    version: str
    output: Path
    lock_path: Path
    spec: dict[str, Any]


class BatchMaterializationError(RuntimeError):
    """A later converter failed after earlier verified modules were published."""

    def __init__(self, failed_module_id: str, published: dict[str, Path]):
        self.failed_module_id = failed_module_id
        self.published = dict(published)
        super().__init__(
            f"module {failed_module_id!r} failed; "
            f"already published: {', '.join(self.published) or '(none)'}"
        )


def _plan_requested_feature_module(
    *,
    resolver: Any,
    module_id: str,
    plugin_id: str,
    materializer_id: str,
    source: Path | None = None,
    requested_version: str | None = None,
    install_root: Path | None = None,
    registry_path: Path | None = None,
) -> ModulePublicationPlan:
    """Share exact registry/manifest and target preflight across one/batch runs."""
    from scripts import agora_materialize as host
    from scripts import agora_materialize_registered as registered

    module = resolver.catalog.get(module_id)
    if module.kind != "feature-module":
        raise ValueError(f"requested {module_id!r} is not a feature module")
    if module.acquisition_strategy != "local-module":
        raise ValueError(
            f"module {module_id!r} is not a local-module and must not be materialized here"
        )
    # A matching parent/version alone would allow any registered converter to
    # impersonate a canonical module ID. Authorization must originate in the
    # bundled, reviewed resource registry. Current local-only modules without a
    # producer declaration remain unpublishable until that pin is reviewed.
    binding = getattr(module, "materializer", None)
    if (
        not isinstance(binding, dict)
        or set(binding) != {"plugin", "id"}
        or binding["plugin"] != plugin_id
        or binding["id"] != materializer_id
    ):
        raise ValueError(
            f"module {module_id!r} has no matching catalog-bound registered producer"
        )
    if not isinstance(module.parent, str) or not module.parent:
        raise ValueError("feature module must declare a parent corpus")
    if not isinstance(module.tf_path, str) or not module.tf_path:
        raise ValueError("feature module has no local Text-Fabric target")
    parent = resolver.catalog.get(module.parent)
    if parent.kind != "corpus":
        raise ValueError(f"feature module parent {module.parent!r} is not a corpus")
    versions = tuple(module.parent_versions)
    if not versions:
        raise ValueError("feature module declares no compatible parent versions")
    if requested_version is None:
        if len(versions) != 1:
            raise ValueError("select a parent version explicitly for multi-version modules")
        version = versions[0]
    else:
        version = requested_version
    if version not in versions:
        raise ValueError(
            f"parent version {version!r} is incompatible with module {module_id!r}"
        )
    if PurePosixPath(module.tf_path).name != version:
        raise ValueError(
            f"module {module_id!r} TF path {module.tf_path!r} is inconsistent "
            f"with selected parent version {version!r}"
        )
    if not isinstance(parent.tf_path, str) or (
        PurePosixPath(parent.tf_path).name != version
    ):
        raise ValueError("catalog parent default TF path differs from chosen version")

    # Version compatibility alone never proves the node identity: a materialized
    # weft is valid only against the actual pinned parent source tree.
    if (
        not isinstance(parent.ref, str)
        or not _COMMIT_RE.fullmatch(parent.ref)
    ):
        raise ValueError("parent corpus has no pinned immutable source revision")
    pinned = tuple(
        dependency.get("ref")
        for dependency in module.dependencies
        if dependency.get("role") == "parent-base"
    )
    if not pinned or any(
        not isinstance(revision, str)
        or revision.casefold() != parent.ref.casefold()
        for revision in pinned
    ):
        raise ValueError("feature module parent-base revision differs from catalog parent")

    # Check the *actual installed* producer declaration rather than trusting an
    # arbitrary caller-supplied plugin/materializer pair for this module ID.
    manifest_path = registered.resolve_installed_manifest(
        plugin_id, install_root=install_root, registry_path=registry_path
    )
    manifest = host.load_manifest(manifest_path)
    spec = host.select_materializer(manifest, materializer_id)
    parent_input = spec.get("parent_input")
    composition = spec["output"].get("composition")
    if (
        not isinstance(parent_input, dict)
        or parent_input["resource"] != module.parent
        or version not in parent_input["parent_versions"]
        or not isinstance(composition, dict)
        or composition.get("kind") != "feature-module"
        or composition.get("parent") != module.parent
        or version not in composition["compatibility"]["parent_versions"]
    ):
        raise ValueError(
            f"installed materializer {materializer_id!r} is not compatible with "
            f"requested feature module {module_id!r} on {module.parent}@{version}"
        )

    store = resolver.store
    output = store.local_feature_module_path(module.id, module.tf_path)
    # All paths are computed from the catalog; re-check every component in the
    # local module cache instead of resolving a symlinked alias out of the cache.
    root = store.cache_dir
    try:
        parts = output.relative_to(root).parts
    except ValueError as exc:
        raise ValueError("local module destination escapes Context-Fabric cache") from exc
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"local module publication path is symlinked: {current}")

    # Different registered producers could otherwise race for the same module
    # destination. Hold this per-module persistent lock through the runtime and
    # final host atomic publication; never overwrite even an *empty* directory.
    lock_path = store.locks_dir / (
        f"materialized-module-{store.safe_cache_key(module.id)}.lock"
    )

    return ModulePublicationPlan(
        module_id=module_id,
        plugin_id=plugin_id,
        materializer_id=materializer_id,
        source=source,
        parent_id=module.parent,
        parent_revision=parent.ref,
        version=version,
        output=output,
        lock_path=lock_path,
        spec=spec,
    )


def _assert_unpublished_destination(root: Path, output: Path) -> None:
    try:
        parts = output.relative_to(root).parts
    except ValueError as exc:
        raise ValueError("local module destination escapes Context-Fabric cache") from exc
    current = root
    if current.is_symlink():
        raise ValueError(f"local module publication path is symlinked: {current}")
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"local module publication path is symlinked: {current}")
    if output.exists() or output.is_symlink():
        raise ValueError(
            f"feature module destination already published at {output}; "
            "refusing to overwrite or reuse it implicitly"
        )


def materialize_requested_feature_module(
    *,
    module_id: str,
    plugin_id: str,
    materializer_id: str,
    source: Path | None = None,
    requested_version: str | None = None,
    cache_dir: Path | None = None,
    install_root: Path | None = None,
    registry_path: Path | None = None,
) -> Path:
    """Publish one explicitly selected, canonical producer into a local module slot."""
    from scripts import agora_install_materializer as installer

    resolver = _bundled_context_fabric_resolver(cache_dir=cache_dir)
    plan = _plan_requested_feature_module(
        resolver=resolver, module_id=module_id, plugin_id=plugin_id,
        materializer_id=materializer_id, source=source,
        requested_version=requested_version, install_root=install_root,
        registry_path=registry_path,
    )
    with installer._lock(plan.lock_path):
        _assert_unpublished_destination(resolver.store.cache_dir, plan.output)
        return materialize_managed_feature_module(
            resolver=resolver,
            plugin_id=plugin_id,
            materializer_id=materializer_id,
            source=source,
            output=plan.output,
            requested_version=plan.version,
            install_root=install_root,
            registry_path=registry_path,
        )


def _candidate_versions_for_request(
    resolver: Any,
    entry: dict[str, Any],
    *,
    install_root: Path | None = None,
    registry_path: Path | None = None,
) -> tuple[str, set[str]]:
    """Read review-pinned version intersection without preparing the parent."""
    from scripts import agora_materialize as host
    from scripts import agora_materialize_registered as registered

    module = resolver.catalog.get(entry["module_id"])
    producer = getattr(module, "materializer", None)
    if (
        module.kind != "feature-module"
        or module.acquisition_strategy != "local-module"
        or not isinstance(producer, dict)
        or producer != {
            "plugin": entry["plugin_id"],
            "id": entry["materializer_id"],
        }
    ):
        raise ValueError(
            f"module {entry['module_id']!r} has no matching catalog-bound producer"
        )
    if not isinstance(module.parent, str) or not module.parent:
        raise ValueError("feature module must declare a parent corpus")
    manifest_path = registered.resolve_installed_manifest(
        entry["plugin_id"], install_root=install_root, registry_path=registry_path,
    )
    spec = host.select_materializer(
        host.load_manifest(manifest_path), entry["materializer_id"],
    )
    parent_input = spec.get("parent_input")
    composition = spec.get("output", {}).get("composition")
    if (
        not isinstance(parent_input, dict)
        or parent_input.get("resource") != module.parent
        or not isinstance(composition, dict)
        or composition.get("kind") != "feature-module"
        or composition.get("parent") != module.parent
    ):
        raise ValueError(
            f"registered producer {entry['materializer_id']!r} has incompatible parent"
        )
    compatible = composition.get("compatibility", {}).get("parent_versions", [])
    versions = (
        set(module.parent_versions)
        & set(parent_input["parent_versions"])
        & set(compatible)
    )
    if not versions:
        raise ValueError(
            f"no common compatible parent version for module {entry['module_id']!r}"
        )
    return module.parent, versions


def materialize_requested_feature_modules(
    requests: list[dict[str, Any]],
    *,
    cache_dir: Path | None = None,
    install_root: Path | None = None,
    registry_path: Path | None = None,
    requested_versions: dict[str, str] | None = None,
) -> dict[str, Path]:
    """Batch explicitly selected feature modules with a shared immutable parent.

    Every producer is preflighted before preparing a parent or executing code.
    Distinct parent groups are independent; a group holds one snapshot lease
    across all of its sandboxed runs. Publication is per-module and no-clobber;
    a later producer failure reports already-published output explicitly.
    """
    from scripts import agora_install_materializer as installer
    from scripts import agora_materialize_registered as registered

    if not isinstance(requests, (list, tuple)) or not requests:
        raise ValueError("module batch requests must be a nonempty sequence")
    seen: set[str] = set()
    for entry in requests:
        if not isinstance(entry, dict) or set(entry) != {
            "module_id", "plugin_id", "materializer_id", "source"
        }:
            raise ValueError("each batch module request must declare exact producer and source keys")
        module_id = entry["module_id"]
        if not isinstance(module_id, str) or not module_id:
            raise ValueError("module ID must be a nonempty string")
        if module_id in seen:
            raise ValueError(f"duplicate module request {module_id!r}")
        seen.add(module_id)
    resolver = _bundled_context_fabric_resolver(cache_dir=cache_dir)
    if requested_versions is not None and not isinstance(requested_versions, dict):
        raise ValueError("requested_versions must be a mapping of parent resource to TF version")
    version_overrides = requested_versions or {}
    by_parent: dict[str, set[str]] = {}
    candidate_parents = []
    for entry in requests:
        parent_id, candidates = _candidate_versions_for_request(
            resolver, entry, install_root=install_root, registry_path=registry_path,
        )
        candidate_parents.append(parent_id)
        if parent_id in by_parent:
            by_parent[parent_id].intersection_update(candidates)
        else:
            by_parent[parent_id] = set(candidates)
        if not by_parent[parent_id]:
            raise ValueError(
                f"requested modules have no common compatible version for parent {parent_id!r}"
            )

    unknown = set(version_overrides) - set(by_parent)
    if unknown:
        raise ValueError(f"requested versions name unknown parents: {sorted(unknown)}")
    selected: dict[str, str] = {}
    for parent_id, choices in by_parent.items():
        explicit = version_overrides.get(parent_id)
        if explicit is not None:
            if explicit not in choices:
                raise ValueError(
                    f"requested parent version {explicit!r} is incompatible with all "
                    f"selected modules for {parent_id!r}"
                )
            selected[parent_id] = explicit
        elif len(choices) == 1:
            selected[parent_id] = next(iter(choices))
        else:
            raise ValueError(
                f"parent {parent_id!r} has ambiguous common versions "
                f"{sorted(choices)}; specify requested_versions"
            )

    # The existing single-module plan performs the full immutable catalog,
    # manifest, output and producer validation using the already negotiated
    # common parent version; never silently fall back to per-module defaults.
    plans = tuple(
        _plan_requested_feature_module(
            resolver=resolver,
            module_id=entry["module_id"],
            plugin_id=entry["plugin_id"],
            materializer_id=entry["materializer_id"],
            source=entry["source"],
            requested_version=selected[parent_id],
            install_root=install_root,
            registry_path=registry_path,
        )
        for entry, parent_id in zip(requests, candidate_parents)
    )
    # Filesystem identity, not just logical resource ID, defines publication.
    # Even distinct catalog names must not alias one output (e.g. on platforms
    # with case-insensitive paths or future path-normalization policies).
    destinations = [str(plan.output).casefold() for plan in plans]
    if len(set(destinations)) != len(destinations):
        raise ValueError("duplicate canonical local-module publication destination")

    groups: dict[tuple[str, str, str], list[ModulePublicationPlan]] = {}
    parents: dict[str, tuple[str, str]] = {}
    for plan in plans:
        identity = (plan.version, plan.parent_revision)
        previous = parents.setdefault(plan.parent_id, identity)
        if previous != identity:
            raise ValueError(
                f"requested modules for parent {plan.parent_id!r} have incompatible "
                "version or immutable revision; select one compatible version"
            )
        groups.setdefault((plan.parent_id, *identity), []).append(plan)

    results: dict[str, Path] = {}
    # Lock all destinations in deterministic order so a batch never deadlocks
    # another batch with the same modules requested in reverse order.
    with ExitStack() as stack:
        locks = sorted({plan.lock_path for plan in plans}, key=str)
        for lock_path in locks:
            stack.enter_context(installer._lock(lock_path))
        # No producer runs until EVERY canonical output is absent and safe.
        for plan in plans:
            _assert_unpublished_destination(resolver.store.cache_dir, plan.output)

        bindings = {}
        # Prepare and lease EVERY parent group before the FIRST converter runs.
        # A broken second parent therefore cannot leave an unreported partial
        # publication of modules from the first group.
        for (parent_id, version, revision), parent_plans in groups.items():
            binding = resolve_managed_parent(
                parent_plans[0].spec, resolver, requested_version=version
            )
            if (
                binding.resource_id != parent_id
                or binding.version != version
                or binding.source_revision.casefold() != revision.casefold()
            ):
                raise ValueError("prepared parent differs from pinned batch catalog identity")
            stack.enter_context(resolver.store.acquire_cache_lease(binding.path))
            bindings[(parent_id, version, revision)] = binding

        for identity, parent_plans in groups.items():
            binding = bindings[identity]
            for plan in parent_plans:
                try:
                    results[plan.module_id] = registered.materialize_registered(
                        plugin_id=plan.plugin_id,
                        materializer_id=plan.materializer_id,
                        source=plan.source,
                        output=plan.output,
                        sandbox="required",
                        install_root=install_root,
                        registry_path=registry_path,
                        parent=binding,
                    )
                except Exception as exc:
                    raise BatchMaterializationError(plan.module_id, results) from exc
    return results
