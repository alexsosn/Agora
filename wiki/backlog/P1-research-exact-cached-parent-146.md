# Research: exact cached corpus snapshots for materializer parent bindings (#146)

## Problem boundary

Feature-module materializers such as Burns need a canonical parent corpus as a second read-only execution input. #134 defines the parent/version composition declaration and #135 provides the provider-neutral execution binding/lifetime seam. The missing Context-Fabric capability is intentionally narrower: given a canonical corpus resource ID, exact Text-Fabric version, and immutable source revision, identify an already-resident corpus snapshot and provide an eviction-safe lease factory without any network, Git refresh, export, fallback, or ordinary `prepare()` behavior.

This is a trust lookup, not acquisition.

## Current cache model

`GitStore` stores exported snapshots under revision-addressed paths and records an external identity sidecar for each touched cache object. `_cache_identity()` derives these identities from the managed path:

- `kind`: `corpus-snapshot` or `feature-module-snapshot` for source snapshots, `overlay` for compositions;
- `resource_id`;
- exact source `revision`;
- repository-relative TF `relative_path`.

`touch_cache_object()` writes the corresponding `object-meta/<object-id>.json`. `_discover_cache_paths()` is deliberately conservative: it returns only objects whose sidecar exists, resolves to the same managed root, and exactly matches the identity derived from that root. It does not recursively guess TF roots. `cache_entries()` builds on that strict discovery and additionally validates the object contents.

This is the right source of truth for cache-only lookup. Scanning `snapshots/` directly would undo the conservative cache-discovery design.

## Existing lease model

`GitStore.acquire_cache_lease(path)` acquires the shared cache-transition lock, then a cross-process shared object lock, validates the object, touches it, and returns a `CacheLease`. Eviction takes the opposite exclusive object lock, so a held lease prevents detach/removal until release. `CacheLease` releases explicitly, as a context manager, and defensively in `__del__`.

One important detail: `acquire_cache_lease(path)` itself does not require the external identity sidecar to pre-exist or match; after validating the managed directory it calls `touch_cache_object()`, which writes/replaces the sidecar from path-derived identity. Therefore #146 must not resolve a trusted sidecar once and later call the generic lease blindly. The provider-side descriptor/lease factory must revalidate that the exact sidecar-backed identity is still discoverable before execution so stale/tampered/deleted sidecars fail closed rather than being silently healed.

The existing generic lease semantics should not be tightened globally in this ticket because other Context-Fabric lifecycle paths may legitimately lease managed objects independently of #146's trust lookup.

## Why ordinary resolver APIs are too permissive

`ContextFabricResolver.prepare()` for a corpus calls `_repo()`, which calls `GitStore.ensure_metadata()`. `ensure_metadata()` may clone/fetch/select upstream Git state. The resolver then discovers dataset roots and `GitStore.materialize()` may export a missing snapshot. Explicit offline/source-mode support elsewhere is useful for user-facing loading, but it still operates through repository selection/materialization semantics and is not an exact sidecar-backed trust lookup.

A materializer parent must never trigger these paths implicitly. #146 should not call:

- `ensure_metadata()`;
- `_repo()`;
- `prepare()` / `prepare_with_modules()`;
- `_export_snapshot()`;
- Git fetch/clone/select;
- fallback to `refs/agora/selected` or the current upstream revision.

## Layering decision

The public lookup belongs on `ContextFabricResolver`, backed by strict `GitStore.cache_entries()` and `acquire_cache_lease()` primitives.

Reasoning:

- `GitStore` knows managed object identity and eviction mechanics, but intentionally does not own Text-Fabric dataset-version semantics.
- `ContextFabricResolver` already owns canonical catalog resource-kind validation plus `dataset_version(relative_path)`.
- Keeping the public API on the resolver prevents callers from supplying an arbitrary filesystem path and asserting that it is a canonical corpus.
- The low-level materializer host remains provider-neutral and does not import Context-Fabric.

## Exact lookup contract

Add a provider-side immutable descriptor, conceptually:

```python
@dataclass(frozen=True)
class CachedCorpusSnapshot:
    resource_id: str
    version: str
    source_revision: str
    relative_path: str
    path: Path
    # private resolver/store reference for revalidation + lease acquisition
```

A resolver method such as:

```python
resolve_cached_corpus(
    resource_id: str,
    *,
    version: str,
    source_revision: str,
) -> CachedCorpusSnapshot
```

must:

1. resolve `resource_id` through the canonical catalog and require `kind == "corpus"`;
2. require non-empty exact version and a 40/64-hex immutable source revision;
3. inspect only strict sidecar-backed `store.cache_entries(resource_id)`;
4. filter to `kind == "corpus-snapshot"`, exact resource ID, exact normalized revision, and `dataset_version(relative_path) == version`;
5. if the catalog pins `tf_path`, additionally require that exact normalized relative path;
6. require exactly one candidate; zero is an actionable cache miss and multiple candidates fail closed as ambiguous rather than applying repository-selection heuristics to an incomplete cache view;
7. return the provider-created descriptor; no public raw-path constructor/API is authoritative.

CUC is currently an unpinned canonical corpus (`DT-UCPH/cuc`). Its normal reviewed 0.2.8 cache object has one `tf/0.2.8` sidecar-backed corpus snapshot, so the exact `(cuc, 0.2.8, revision)` lookup is unambiguous without upstream access.

## Lease factory contract

The descriptor should expose a zero-argument context-manager factory suitable for #135, e.g. `snapshot.lease()` / `snapshot.acquire_lease()`.

On each acquisition it must re-run strict exact lookup for its stored `(resource_id, version, source_revision)` and require the resolved path/relative path to equal the descriptor. Only then should it call `store.acquire_cache_lease(path)`. Thus:

- a snapshot pruned before execution fails closed;
- a deleted/tampered/stale sidecar fails closed;
- a replacement candidate with a different path cannot silently substitute;
- once the generic cache lease is entered, ordinary Agora prune cannot detach the snapshot until the caller exits;
- release on success and exception comes from the existing `CacheLease` context manager.

This revalidation closes the practical Agora-managed TOCTOU window without changing generic cache lease behavior. The local cache is not treated as a hostile-filesystem security boundary; concurrent arbitrary external filesystem mutation remains outside this ticket's threat model.

## Version and ambiguity semantics

`dataset_version(relative_path)` is the existing canonical function used by normal resolver selection. Version strings remain opaque and are compared exactly; no SemVer interpretation belongs here.

For unpinned resources, do **not** call `select_dataset_root()` over whatever subset happens to be cached when multiple same-version roots exist. That could make an incomplete cache view stand in for full repository discovery. Multiple exact-version sidecars therefore fail closed. A future need for such resources should add stronger cached selection provenance rather than guess.

For resources with `upstream.tf_path`, the cached candidate must exactly match the configured normalized path as well as version/revision.

## Failure behavior

Failures should be actionable and side-effect free:

- unknown resource: existing catalog error;
- non-corpus resource: `ValueError` identifying the kind mismatch;
- malformed/non-immutable revision: `ValueError` before cache inspection;
- empty version: `ValueError`;
- zero exact candidates: cache-only miss explaining that the caller must acquire/prepare the parent explicitly before materializer execution;
- >1 candidate: ambiguity error listing only logical relative paths, not encouraging arbitrary host-path selection;
- stale/tampered sidecar: absent from strict discovery and therefore a cache miss/revalidation failure;
- feature-module snapshot or overlay: filtered/rejected by exact kind;
- lease-time disappearance/replacement: fail closed before converter execution.

No failure path may call upstream acquisition or mutate a canonical resource selection.

## Existing behavior to preserve

- normal `prepare()` and `prepare_with_modules()` remain acquisition-capable as today;
- explicit offline user-facing resolution remains unchanged;
- `GitStore.acquire_cache_lease(path)` remains the generic lifecycle primitive;
- conservative sidecar discovery remains unchanged;
- collections and feature modules are not broadened into this exact corpus-parent API;
- no materializer or core package imports Context-Fabric provider code.

## TDD boundaries

Before production changes, preserve focused RED tests proving:

1. an exact sidecar-backed corpus snapshot resolves by resource/version/revision;
2. wrong resource, version or revision fails closed;
3. malformed revision fails before store lookup;
4. missing snapshot performs no `ensure_metadata`, `_export_snapshot`, `_select`, `_repo`, or ordinary `prepare` acquisition;
5. no current-selected-revision fallback occurs;
6. feature-module snapshots and overlays cannot satisfy corpus lookup;
7. pinned `tf_path` must match exactly;
8. multiple same-version candidates fail closed rather than being ranked heuristically;
9. deleted/tampered/stale sidecar fails on initial lookup and on descriptor lease revalidation;
10. the descriptor's lease prevents concurrent cache removal, and release occurs on normal/exceptional context exit;
11. normal acquisition-capable prepare behavior is unchanged.

Use only synthetic Text-Fabric fixtures; no Burns-derived data belongs in Agora tests.

## Downstream integration

#146 should stop at the provider-side exact cached descriptor + lease factory. The later higher-level materializer orchestration layer can translate the descriptor's immutable identity/path into #135's provider-neutral `ParentResourceBinding` and pass its zero-argument lease factory to the registered runner. This keeps cache/provider policy out of the core materializer host and gives Burns a safe route to reviewed CUC without implicit network access.
