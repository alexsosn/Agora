# Design/plan: exact cached corpus snapshots for materializer parent bindings (#146)

## Preconditions

Research: `wiki/backlog/P1-research-exact-cached-parent-146.md`.

Base at branch creation: `c6c7065bd877e04522f598f3aec21b812ce35ef7`.

This plan adds only the Context-Fabric provider-side exact cached lookup/lease contract. It does not wire a materializer orchestration command and does not alter #135's low-level provider-neutral binding semantics.

## Slice 1 — preserve lookup RED

Add `tests/test_context_fabric_cached_parent.py` before production changes.

Use synthetic corpus/module cache objects and existing `GitStore` helpers. Freeze tests for:

- exact `(resource_id, version, immutable source_revision)` resolves one indexed `corpus-snapshot`;
- result exposes canonical resource ID, opaque exact version, revision, relative TF path and managed path;
- non-corpus catalog resources are rejected;
- empty version and non-40/64-hex revision are rejected before cache discovery;
- wrong resource/version/revision and absent snapshots are cache-only misses;
- no miss invokes `ensure_metadata`, `_export_snapshot`, `_select`, resolver `_repo`, or ordinary `prepare`;
- feature-module snapshots and overlays never satisfy corpus lookup;
- configured `tf_path` must match the cached candidate exactly;
- multiple sidecar-backed same-version candidates fail closed rather than using `select_dataset_root` ranking;
- deleted/tampered/stale sidecar is not trusted.

Expected RED: `ContextFabricResolver.resolve_cached_corpus` / `CachedCorpusSnapshot` do not exist.

Preserve the exact failing head/workflow before GREEN.

## Slice 2 — lookup GREEN

In `plugins/context-fabric/src/agora_context_fabric/resolver.py` only:

1. add immutable `CachedCorpusSnapshot` descriptor fields:
   - `resource_id`;
   - `version`;
   - `source_revision`;
   - `relative_path`;
   - `path`;
   - a private resolver association used only for trusted revalidation/lease acquisition;
2. add `ContextFabricResolver.resolve_cached_corpus(resource_id, *, version, source_revision)`;
3. resolve the canonical catalog resource and require `kind == corpus`;
4. validate non-empty version and immutable 40/64-hex revision;
5. call only `store.cache_entries(resource.id)` for candidate discovery;
6. require `kind == corpus-snapshot`, exact canonical resource ID, normalized exact revision, `dataset_version(relative_path) == version`, and configured `tf_path` equality when applicable;
7. require exactly one match; zero raises an actionable cache-only miss and >1 raises an ambiguity error naming logical relative paths;
8. construct the descriptor only from that strict candidate.

Do not call repository/Git acquisition or dataset-root discovery.

Run focused tests, then the normal Foundation suite as the GREEN checkpoint.

## Slice 3 — preserve lifecycle RED

Extend the focused tests before adding lease behavior:

- descriptor exposes a zero-argument lease/context-manager factory usable by higher-level materializer orchestration;
- lease acquisition re-runs exact strict lookup and rejects descriptor/path/relative-path substitution;
- deleting/tampering the sidecar after lookup but before lease acquisition fails closed;
- deleting the snapshot before lease acquisition fails closed;
- once entered, concurrent `remove_cache_object`/prune observes the object as in-use and cannot detach it;
- lease releases on normal exit;
- lease releases when the caller raises inside the context;
- no lease path calls acquisition-capable resolver methods.

Expected RED: lookup descriptor has no trusted lease method.

Preserve the exact failing head/workflow before GREEN.

## Slice 4 — lifecycle GREEN

Add the smallest descriptor lease method, e.g. `acquire_lease(timeout=30.0)`:

1. call the associated resolver's `resolve_cached_corpus()` again with the descriptor's logical identity;
2. require returned `relative_path` and resolved managed `path` to equal the descriptor exactly;
3. only then return `store.acquire_cache_lease(path, timeout=timeout)`;
4. rely on existing `CacheLease` context management for normal/exception release and cross-process eviction exclusion.

Do not change generic `GitStore.acquire_cache_lease()` semantics in this ticket.

## Slice 5 — regression and provider boundary

Run:

- focused exact-cached-parent tests;
- existing offline-resolution tests;
- Context-Fabric cache lifecycle tests on Linux/macOS/Windows;
- full Foundation workflow;
- representative Context-Fabric load smoke if triggered by resolver changes.

Confirm ordinary `prepare()` remains acquisition-capable and unchanged, and existing explicit offline behavior is unchanged.

No Burns-derived source/TF data may be added; tests use synthetic fixtures only.

## Independent adversarial review

Freeze the exact final head and review it independently from the implementation sequence. Challenge at least:

- cache-directory scanning or path heuristics bypassing identity sidecars;
- arbitrary host path accepted as canonical identity;
- resource kind confusion (feature-module/overlay/collection as corpus);
- version ranking from an incomplete cached subset;
- current-selected-revision or upstream fallback;
- hidden calls to `ensure_metadata`, `prepare`, export/fetch/clone;
- malformed or case-confused revision handling;
- pinned `tf_path` mismatch;
- stale/tampered/deleted sidecar being silently healed by generic lease acquisition;
- path replacement between lookup and lease;
- lease not covering the caller's complete context lifetime;
- prune detaching an active parent;
- lock-order/deadlock regression with existing cache-transition/object locks;
- changes to ordinary Context-Fabric prepare/load behavior;
- leaking provider-specific code into the core materializer host.

Any blocker found in this review becomes a focused RED before its fix. Re-freeze and re-run exact-head CI after every such correction.

## Definition of done

A higher-level Agora orchestrator can request exact reviewed CUC identity, receive only an already-indexed CUC corpus snapshot descriptor, build #135's parent binding from that descriptor, and pass its lazy lease factory into registered materialization. If CUC is missing, ambiguous, stale, tampered, wrong-version or wrong-revision, execution fails without network or fallback. A held lease prevents Agora cache eviction until converter execution/receipt publication releases it.
