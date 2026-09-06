# Research: Context-Fabric offline cache reuse

Issue: #44

## Scope and ownership

The defect is in Agora-owned source acquisition and resource resolution. `ContextFabricResolver` currently calls `GitStore.ensure_metadata()` for ordinary corpus resolution, and `ensure_metadata()` unconditionally performs a Git fetch before a cached source snapshot can be reused. A corpus that is already materialized in Agora's cache therefore becomes unavailable when its remote cannot be reached.

This work does not alter Text-Fabric/cfabric parsing, loading, query semantics, feature semantics, or scholarly data. It is within the repository boundary in `AGENTS.md` and `CONTRIBUTING.md`: Agora owns resource selection, acquisition, cache behavior, provenance, and marketplace UX.

## Current implementation on main

Current `main` has moved beyond the implementation against which #44 was filed:

- persistent Git repositories under `repositories/` contain metadata, not the user-facing corpus tree;
- exact corpus and feature-module bytes are exported into revision-addressed snapshots under `snapshots/`;
- collection discovery is commit-bound through `CollectionIndexManager`;
- explicit collection `source_revision` requests already resolve cached exact commits without falling back to current upstream state;
- prepared snapshots and overlays participate in the cache lifecycle, sidecar indexing, LRU eviction, and process-backed leases;
- snapshot export creates a temporary Git repository and performs a fetch for the exact revision, so merely recovering repository metadata offline is insufficient: offline reuse must select an already materialized snapshot rather than call the normal exporter.

Consequently the earlier PR #51 implementation cannot be merged by restoring its old resolver shape. The offline policy must be integrated into the current collection-index, snapshot, overlay, and lease design.

## Observable failure

For a normal corpus with a complete cached repository and materialized snapshot:

1. `prepare_corpus` or `load_corpus` resolves the resource;
2. resolver calls `GitStore.ensure_metadata()`;
3. `ensure_metadata()` calls `_select()`;
4. `_select()` performs `git fetch` even when `refs/agora/selected` and an exact source snapshot already exist;
5. a connectivity failure raises `subprocess.CalledProcessError` before the cache can be served.

A retry repeats the same remote operation. The local snapshot is not treated as a valid degraded-mode source.

## Required behavioral model

### Network modes

Expose three request-scoped modes:

- `auto` (default): try the configured remote; only a connectivity failure may fall back to a compatible complete cached snapshot;
- `offline`: perform no remote Git operation at all; resolve only from compatible local state and fail immediately if required metadata or bytes are missing;
- `require-fresh`: require the normal remote resolution path and never degrade to cached state after a failed refresh.

An environment default is useful for long offline sessions, but an MCP tool argument must be able to override it per call. Request scoping must be concurrency-safe; a process-global mutable mode would allow one MCP request to affect another.

### Error classes

Do not treat every Git failure as an offline event. At minimum distinguish:

- connectivity failures: DNS resolution, refused/unreachable connection, proxy/network timeout, transport reset;
- remote/configuration failures: authentication/authorization failure, repository missing, configured ref missing, malformed repository, protocol errors unrelated to connectivity.

Only the first class is eligible for `auto` fallback. `offline` cache misses and `require-fresh` connectivity failures should produce actionable Agora errors rather than exposing raw Git argv/`CalledProcessError` output.

The connectivity classifier is necessarily conservative because Git reports transport failures via process stderr. Unknown failures must not be swallowed into stale-cache fallback.

## Cache identity and provenance

Offline fallback is safe only when Agora can establish that the cached repository selection belongs to the current resource configuration.

The stable facts available today are:

- resource id determines the repository cache key;
- repository `origin` can be compared with the currently configured repository;
- `refs/agora/selected` records the selected commit;
- revision-addressed source snapshots identify exact commit + relative path;
- current resources may use a floating default branch (`ref: null`), a mutable branch/tag-like ref, or an immutable 40/64-hex commit.

A new successful online resolution should persist a small selection record binding:

- repository identity;
- configured ref, including explicit `null`;
- selected revision.

When that record exists, all three fields must match. In particular, a cache selected under `ref: some-branch` must not become valid for a later `ref: null` configuration merely because the repository URL is unchanged.

### Legacy caches created before the selection record

Pre-#44 caches already have `refs/agora/selected` but no selection record. Migration must be conservative:

- immutable configured commit: the selected revision itself proves compatibility when it equals the configured commit;
- floating `ref: null`: repository identity + selected revision can be reused in degraded mode, but freshness is unverified;
- mutable non-SHA configured ref: accepting only the selected revision is unsafe because the current configured ref may differ from the ref that originally produced it.

For the mutable-ref legacy case, Git's persisted `FETCH_HEAD` is the remaining local evidence produced by the old `_select()` path. A migration fallback may accept it only when the first mergeable `FETCH_HEAD` record binds the selected revision to the same configured branch/tag name in an unambiguous recognized Git format. Otherwise fail closed and require one online refresh to establish the new selection record. This preserves already prepared branch/tag caches where identity can still be proved without making a ref change invisible.

The migration fallback must never rewrite the selection record merely because an offline legacy inference succeeded; the result remains cached/unverified. A later successful online refresh may create the durable record.

## Freshness semantics

Public results need to state how the source revision was resolved.

Use:

- `resolution: fresh` when the configured remote was successfully consulted for this resolution;
- `resolution: cached` when a prior compatible local selection/snapshot was used without successful current remote verification;
- exact caller-supplied collection `source_revision` remains an exact commit-bound request and should preserve the current no-fallback behavior rather than being silently re-resolved to a different commit.

Expose `source_revision_verified` as the freshness/selection-verification indicator. It is `false` for floating/mutable cached fallback. A configured immutable commit may be `true` offline when the selected revision exactly equals the configured commit because no moving ref must be refreshed.

Do not imply that `source_revision_verified=true` means scholarly data quality or semantic verification.

## Collection behavior

The current `CollectionIndexManager` contract must be preserved.

- A collection request without `source_revision` follows normal current-state resolution and therefore participates in `auto`/`offline`/`require-fresh` policy.
- `list_collection_members` returns an immutable `source_revision`.
- A later `prepare_corpus`/`load_corpus` with that exact `source_revision` must use that cached commit and must never silently substitute current upstream state.
- Offline success for an exact collection member additionally requires the member snapshot to exist locally; metadata/index presence alone is not enough.
- A missing exact commit or missing member snapshot produces a local cache miss, not a remote refresh under explicit `offline` mode.

## Feature modules and overlays

A corpus prepared with modules has multiple independently acquired source identities. Offline reuse must therefore resolve each feature-module repository under the same network-mode policy and require the exact module snapshot to exist.

A composed overlay can be reused if its parent/module identities match the prepared inputs. This change must not bypass cache lifecycle bookkeeping or active leases.

## Hidden network operations

Explicit `offline` mode must avoid all Git operations capable of reaching a remote, including the temporary-repository fetch used by snapshot export. It is insufficient to skip only `ensure_metadata()` fetches.

Offline materialization should locate an existing indexed cache object with matching:

- kind (`corpus-snapshot` / `feature-module-snapshot`);
- resource id;
- revision;
- relative path.

Then validate/touch it through the existing cache APIs. If it is absent, fail without attempting export.

## TDD / adversarial cases

The RED suite must cover at least:

1. cached floating corpus + connectivity failure -> exact snapshot reused, `resolution=cached`, freshness false;
2. uncached resource + explicit offline -> actionable cache miss and zero remote attempts;
3. explicit offline on a cached corpus -> zero fetch/export network operations;
4. `require-fresh` + connectivity failure -> fail, never stale fallback;
5. authentication/missing-ref/remote-repository failure -> no `auto` fallback;
6. repository URL change -> cached selection rejected;
7. persisted selection `mutable-ref -> null`, `null -> mutable-ref`, and mutable-ref change -> rejected;
8. configured immutable commit -> reusable offline when selected commit matches;
9. legacy pre-record floating cache -> usable conservatively with freshness false;
10. legacy pre-record mutable ref -> usable only when `FETCH_HEAD` unambiguously proves the same ref/revision; changed/ambiguous ref -> rejected;
11. current commit-bound collection index/listing behavior survives the change;
12. collection member prepare/load with an exact `source_revision` works from complete cached state offline and never falls back to another revision;
13. metadata/index-only collection cache with missing member bytes fails offline without hidden fetch;
14. feature-module snapshot reuse follows the same mode and provenance rules;
15. tool-level `network_mode` overrides are request-scoped and do not leak to subsequent/concurrent calls.

Tests should use local temporary Git repositories/`git daemon` or mocked Git process boundaries. They should test Agora resource resolution, not Text-Fabric scholarly semantics.

## Research conclusion

The appropriate implementation is a thin source-resolution policy layer around the existing `GitStore`/resolver, not a replacement cache or a cfabric shim. The critical constraints are fail-closed cache identity, zero hidden network in explicit offline mode, preservation of commit-bound collection semantics, and explicit provenance when stale local state is served.