# Context-Fabric offline source resolution — research and design for #44

## Status

Research/design gate for issue #44. Production code changes are intentionally excluded from this gate.

The implementation may begin only after this design has passed exact-head CI and independent skeptical review.

## Problem statement

A Context-Fabric resource that has already been prepared or loaded can still become unusable when the network is unavailable. The current metadata path unconditionally refreshes upstream Git state before normal resolution, even when `refs/agora/selected` and an immutable published source snapshot already exist locally.

The defect is in Agora's acquisition/cache orchestration. Context-Fabric corpus semantics are not involved.

The required behavior is:

1. a sufficiently cached resource remains usable without network access;
2. provenance distinguishes a remotely refreshed resolution from one served from local state;
3. an uncached or partially evicted resource fails with an actionable cache/network error instead of a raw Git exception;
4. callers can explicitly force offline behavior or require a fresh remote resolution.

## Ownership and governing architecture

Agora owns resource selection, acquisition, revision-addressed materialization, local cache residency, provenance, and load orchestration under:

- `CONTRIBUTING.md` and `AGENTS.md`;
- `wiki/architecture/ref-plugin-boundary.md`;
- `wiki/architecture/ref-context-fabric-snapshot-cache.md`;
- `wiki/architecture/ref-context-fabric-cache-lifecycle.md`.

No part of this design changes Text-Fabric parsing, compilation, querying, morphology, or scholarly results.

## Current implementation evidence

### Metadata resolution always contacts the remote

`GitStore.ensure_metadata()` acquires the repository lock, clones the metadata repository when absent, and always calls `_select()`.

`_select()` always executes `git fetch` for either the configured ref or remote `HEAD`, resolves `FETCH_HEAD`, then writes the commit to `refs/agora/selected`.

The local recovery primitive already exists: `selected_revision()` resolves `refs/agora/selected`, and `_treeish()` prefers that ref before falling back to `HEAD`. The missing piece is policy deciding when that previous selection may be reused.

### Cached Git metadata does not imply offline-ready corpus bytes

Published source snapshots are revision-addressed under:

```text
snapshots/<resource>/<revision>/corpora/<relative-path>
snapshots/<resource>/<revision>/feature-modules/<relative-path>
```

`_materialize_snapshot()` first reuses a valid published destination. If the destination is absent, it calls `_export_snapshot()`.

`_export_snapshot()` creates a disposable repository and performs a fresh `git fetch ... origin <revision>` before `git archive`. The metadata and export repositories are partial clones; knowing the commit/tree locally does not prove corpus blobs are locally available.

Therefore **the published revision-addressed snapshot is the offline residency boundary**. A known revision with an evicted snapshot is an offline cache miss.

### Collection indexes can hide another lazy network path

`CollectionIndexManager.resolve()` is network-free when either:

- the installed committed member index matches the exact collection revision; or
- a previously generated local collection index matches that revision.

If neither exists, it scans the Git tree and reads `_book.tf` / `otext.tf` headers from the partial repository. Those blob reads can invoke Git's promisor remote.

Offline collection discovery/prepare must therefore require a matching installed/cached index rather than regenerating one opportunistically.

### Explicit immutable collection revisions are already fail-closed

When a caller supplies `source_revision`, `_collection_repo()` validates the immutable SHA and resolves it from the cached metadata repository without substituting current upstream state. This invariant remains.

## Git failure-classification constraint

Git does not expose a portable structured subprocess status meaning "network unavailable". Fetch failures use non-zero exit status plus transport-specific stderr. Authentication failure, repository deletion, missing refs, DNS/proxy failure, refused connections, and timeouts can all surface as `CalledProcessError`.

References:

- <https://git-scm.com/docs/git-fetch>
- <https://git-scm.com/book/en/v2/Git-Internals-Environment-Variables>

It is unsafe to interpret every failed refresh as permission to serve stale state. Automatic fallback must be narrow; unknown failures fail closed.

## Public source-resolution policy

Expose one mutually exclusive mode:

```text
source_mode = "prefer-fresh" | "offline" | "require-fresh"
```

The default is `prefer-fresh`.

### `prefer-fresh`

1. If no metadata repository exists, clone/fetch normally.
2. If metadata exists, attempt normal remote refresh.
3. On success, update `refs/agora/selected`; report remote resolution with freshness verified.
4. On a conservatively recognized connectivity failure only, reuse the previous selected commit.
5. The downstream operation may use that fallback only if every artifact it needs is already resident; it must not quietly start a second network path.
6. Authentication, authorization, repository-not-found, ref-not-found, malformed remote, or unclassified failures remain errors.
7. A missing required snapshot/index after metadata fallback is an actionable cached-residency error.

### `offline`

1. Perform no clone, fetch, lazy blob retrieval, or disposable export fetch.
2. Require an existing metadata repository with a valid `refs/agora/selected`, unless the caller supplied an explicit immutable collection revision already present locally.
3. Require exact published corpus and feature-module snapshots needed by prepare/load.
4. Require a matching installed/cached member index for collection discovery/selection.
5. An overlay may be reused or composed locally only when all source snapshots are resident.
6. Missing state fails immediately with an actionable offline cache-miss error.

### `require-fresh`

1. Require normal remote metadata refresh.
2. Any refresh failure is an error; never fall back to `refs/agora/selected`.
3. Materialization may reuse an immutable snapshot for the freshly selected revision or acquire it normally.

## Interaction with explicit `source_revision`

An explicit immutable collection `source_revision` already fixes source identity, so "current upstream freshness" is not meaningful for that operation.

Define the combinations explicitly:

- `source_revision` + omitted/`prefer-fresh`: resolve exactly that revision; do not refresh `HEAD`. Network remains allowed only if materializing missing bytes is necessary.
- `source_revision` + `offline`: resolve exactly that cached revision and permit no network path; required index/snapshot state must already be resident.
- `source_revision` + `require-fresh`: **invalid combination**. Reject it before repository/cache mutation because one argument pins historical identity while the other asks Agora to resolve current upstream state. A caller wanting current state must omit `source_revision`.

No implementation may silently ignore either explicit argument.

## Compatibility-preserving metadata selection

`GitStore.ensure_metadata()` is an established low-level API returning `Path`. Do not change that return type.

Add a richer primitive, conceptually:

```python
@dataclass(frozen=True)
class MetadataSelection:
    repo: Path
    revision: str
    source_resolution: Literal["remote", "cached", "explicit-revision"]
    source_revision_verified: bool

GitStore.select_metadata(..., source_mode="prefer-fresh") -> MetadataSelection
```

`ensure_metadata()` remains a compatibility wrapper for historical fresh/default behavior and returns `selection.repo`.

Resolver paths needing provenance use the richer primitive directly.

Exact names may be refined during implementation, but the semantic distinction must remain explicit.

## Response provenance

Prepared/loaded results expose:

```text
source_revision: <immutable commit SHA>
source_resolution: remote | cached | explicit-revision
source_revision_verified: true | false
```

Semantics:

- `remote` + `true`: this operation successfully refreshed the configured upstream selection;
- `cached` + `false`: remote freshness was not established for this operation and prior local selection was used;
- `explicit-revision` + `false`: the caller requested an exact immutable revision; `false` means no current-upstream freshness check, not uncertain revision identity.

The immutable SHA remains the provenance anchor in every case.

Feature-module provenance carries the same per-module resolution metadata. An offline parent may not refresh a module independently.

## Connectivity-failure classification

Automatic `prefer-fresh` fallback needs a deliberately small classifier at the Git boundary.

Requirements:

- force diagnostics used for classification to a stable locale such as `LC_ALL=C`;
- disable interactive credential prompting for these refresh operations (`GIT_TERMINAL_PROMPT=0`);
- inspect failed command + stderr, not exit code alone;
- recognize only narrow transport cases such as DNS/proxy resolution failure, network unreachable, connection refused, and connection timeout;
- do not classify authentication/permission failures, repository-not-found, missing ref, or unknown stderr as connectivity;
- preserve the original Git exception/stderr as the cause while surfacing a concise Agora error.

This classifier is a conservative usability fallback. Explicit `offline` is the deterministic zero-network control.

## Error model

Use Agora-owned errors with actionable primary messages.

### Network required / offline cache miss

Examples:

- no metadata repository/selected ref exists;
- selected revision exists but required corpus snapshot was evicted;
- selected revision exists but a feature-module snapshot is absent;
- collection revision exists but no matching installed/cached member index is available.

The message names the resource/object and says that one network-enabled prepare/load is required before offline use.

### Refresh failure

Used by `require-fresh` and unclassified/non-connectivity failures in `prefer-fresh`.

The message says upstream refresh failed and preserves the underlying Git exception. Auth/ref/repository errors must never become cached success.

## Resolver propagation

Propagate source mode through every acquisition-bearing route:

- corpus version resolution where it touches source state;
- `list_collection_members`;
- `prepare_corpus`;
- `load_corpus`;
- collection member selection;
- parent corpus resolution;
- every selected feature module.

Omitting `source_mode` preserves existing delegation shape where exact kwargs are tested; wrappers forward it only when explicitly supplied.

## Materialization contract

The materialization layer needs an explicit cached-only guard, for example:

```text
materialize(..., allow_network=False)
materialize_feature_module(..., allow_network=False)
```

or an equivalent method.

Cached-only behavior:

1. resolve the commit locally;
2. compute exact revision-addressed destination;
3. validate existing destination;
4. touch/index and return when valid;
5. otherwise raise offline cache miss **before** `_export_snapshot()`.

Do not infer that Git object presence makes export network-free.

## Overlay contract

Overlays are Agora-derived and may be built locally from existing source snapshots. Offline mode may reuse a valid overlay or compose one from resident parent/module snapshots. It must not fetch any missing input.

Existing cache-transition and lease ordering remains unchanged.

## Collection contract

### Discovery without explicit revision

- `prefer-fresh`: refresh normally, or use selected cached revision after recognized connectivity failure only when a matching installed/cached index exists;
- `offline`: use selected cached revision and require matching installed/cached index;
- `require-fresh`: refresh and resolve the refreshed revision normally.

### Explicit revision

Never substitute current state. The exact commit must be locally resolvable for offline use, and zero-network discovery/prepare also requires matching resident index/snapshot state.

## Pinned versus floating resources

A configured `ref` does not eliminate freshness semantics unless registry policy guarantees it is immutable.

- online/default resolution may fetch the configured ref to confirm the commit it denotes;
- offline resolution reuses locally selected immutable commit and reports freshness unverified for this operation;
- once the exact published snapshot exists, the pinned resource can be used offline;
- if the snapshot was evicted, offline fails instead of assuming the partial repository contains every blob.

## Locking and state safety

Reuse existing repository locks, cache-transition lock, and object leases.

A failed refresh must not overwrite `refs/agora/selected`. Cached fallback is eligible only after the failed refresh is classified as connectivity-related.

No new create/delete sentinel or distributed lock is introduced.

## MCP/API contract

Add optional `source_mode` to acquisition tools:

```text
list_collection_members(..., source_mode=None)
prepare_corpus(..., source_mode=None)
load_corpus(..., source_mode=None)
```

`None` means default `prefer-fresh` while preserving historical call shape.

Validate the mode and incompatible argument combinations before any network/cache mutation.

An environment variable is not required because #44 accepts an env var **and/or** a tool argument. Per-call control is explicit and reproducible.

## RED test gate before production code

Implementation starts with failing tests committed separately.

### Git selection

1. cached metadata + recognized DNS/connection failure in `prefer-fresh` returns previous selected commit and cached/unverified provenance;
2. authentication failure does not fall back;
3. repository-not-found/ref-not-found does not fall back;
4. unknown Git failure does not fall back;
5. `offline` never invokes clone/fetch;
6. `require-fresh` never falls back;
7. failed refresh leaves previous `refs/agora/selected` unchanged;
8. uncached `offline` returns actionable network-required error;
9. classified refresh operations run with stable diagnostic locale and no interactive prompt.

### Materialization and overlays

10. valid published corpus snapshot is reusable with network disabled;
11. selected revision without published snapshot fails before `_export_snapshot()`;
12. same contract for feature-module snapshots;
13. locally composable overlay succeeds offline with all inputs resident;
14. missing parent/module snapshot fails without network call.

### Resolver/service/MCP

15. prepared/loaded responses expose revision, resolution, and verification fields;
16. module metadata records its own source resolution;
17. `prepare_corpus` and `load_corpus` succeed for a fully cached local fixture in `offline` mode;
18. `list_collection_members` uses matching installed/cached index offline and never regenerates it from potentially missing blobs;
19. collection offline cache miss is actionable;
20. explicit immutable `source_revision` is never replaced with current state;
21. explicit `source_revision` + `require-fresh` is rejected before acquisition;
22. explicit `source_revision` + `offline` never contacts network;
23. omitted `source_mode` preserves existing compatibility/delegation behavior;
24. invalid `source_mode` fails before acquisition.

Use temporary local Git repositories and explicit subprocess/network spies for deterministic tests. CI must not depend on a real outage.

## Documentation gate

Update `wiki/guides/context-fabric-cache.md` and any relevant usage documentation with:

- default `prefer-fresh` behavior;
- deterministic `offline` behavior;
- `require-fresh` behavior;
- explicit-revision interaction;
- meaning of `source_resolution` and `source_revision_verified`;
- metadata-vs-snapshot residency distinction;
- recovery after eviction: reconnect and prepare/load once;
- collection-index and feature-module offline requirements.

## Rejected alternatives

### Fall back after every `git fetch` failure

Rejected: Git does not provide a portable connectivity-only subprocess error class, so auth/ref/repository failures could be masked.

### Treat a cached commit as sufficient for offline materialization

Rejected: `_export_snapshot()` performs a fresh fetch in a disposable partial repository.

### Serve the mutable metadata repository working tree

Rejected by the revision-snapshot architecture; published bytes must retain immutable source identity.

### Make offline server-global only

Rejected for #44. Per-operation policy gives explicit provenance and supports mixed workflows.

### Change Context-Fabric loader semantics

Rejected as out of scope. The prepared path handed upstream remains semantically unchanged.

## Implementation sequence after this gate merges

1. commit RED tests for selection modes, classification, residency, provenance, collection/module behavior, argument conflicts, and MCP compatibility;
2. implement richer metadata selection + conservative refresh classifier while preserving `ensure_metadata()` compatibility;
3. implement cached-only snapshot/index resolution;
4. propagate source policy/provenance resolver → service → MCP;
5. update documentation;
6. run Foundation and relevant cross-platform cache-lifecycle gates;
7. run logically independent adversarial review on exact implementation head;
8. fix findings with regression tests and repeat gates before merge.

## Out of scope

- Context-Fabric data/query/compiler semantics;
- availability after explicit pruning/eviction of required snapshots;
- prefetching all registered resources;
- generic Git repository housekeeping (#45);
- load-cost metadata (#38);
- MCP progress/timing telemetry (#27).
