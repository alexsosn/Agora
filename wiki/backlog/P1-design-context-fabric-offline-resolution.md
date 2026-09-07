# Context-Fabric offline source resolution — research and design for #44

## Status

Research/design gate for issue #44. This document defines the Agora-owned source-selection, freshness, and cache-residency contract required before implementation begins.

Production code changes are intentionally excluded from this gate.

## Problem statement

A Context-Fabric resource that has already been prepared or loaded can still become unusable when the network is unavailable. The current metadata path unconditionally refreshes the upstream Git repository before every normal resolution, even when `refs/agora/selected` and an immutable published source snapshot are already present locally.

The defect is in Agora's acquisition/cache orchestration. Context-Fabric corpus semantics are not involved.

The desired behavior has four properties:

1. a sufficiently cached resource remains usable without network access;
2. provenance distinguishes a remotely refreshed resolution from one served from local state;
3. an uncached or partially evicted resource fails with an actionable cache/network error instead of a raw Git exception;
4. callers can explicitly choose offline or require-fresh behavior instead of depending only on ambient connectivity.

## Governing architecture and ownership

Agora owns resource selection, acquisition, revision-addressed materialization, local cache residency, provenance, and load orchestration. This follows:

- `CONTRIBUTING.md` and `AGENTS.md`;
- `wiki/architecture/ref-plugin-boundary.md`;
- `wiki/architecture/ref-context-fabric-snapshot-cache.md`;
- `wiki/architecture/ref-context-fabric-cache-lifecycle.md`.

No part of this design changes Text-Fabric parsing, compilation, querying, morphology, or scholarly results. It only selects which already-known upstream revision Agora is allowed to serve and whether network-backed acquisition is permitted.

## Current implementation evidence

### Metadata resolution always contacts the remote

`GitStore.ensure_metadata()` currently acquires the repository lock, clones the metadata repository when absent, and then always calls `_select()`.

`_select()` always executes `git fetch` for either the configured ref or remote `HEAD`, resolves `FETCH_HEAD`, then writes the commit to `refs/agora/selected`.

The local recovery primitive therefore already exists: `selected_revision()` resolves `refs/agora/selected`, and `_treeish()` already prefers that ref before falling back to `HEAD`. The missing piece is a policy deciding when a previously selected revision may be reused.

### Metadata presence does not imply source bytes are offline-ready

Published source snapshots are revision-addressed under:

```text
snapshots/<resource>/<revision>/corpora/<relative-path>
snapshots/<resource>/<revision>/feature-modules/<relative-path>
```

`_materialize_snapshot()` first reuses a valid published destination. If that destination is absent, it calls `_export_snapshot()`.

`_export_snapshot()` creates a disposable repository and performs a fresh `git fetch ... origin <revision>` before `git archive`. Because the metadata repository and export repository are partial clones, knowing the commit/tree locally does not prove the corpus blobs are locally available.

Therefore **offline mode must not call ordinary export/materialization when the exact published snapshot is absent**. A known revision with an evicted snapshot is an offline cache miss, not an offline hit.

### Collection indexes can have the same hidden network dependency

`CollectionIndexManager.resolve()` is network-free when either:

- the installed committed member index matches the exact collection revision; or
- a previously generated local collection index matches that revision.

If neither exists, it scans the Git tree and reads `_book.tf` / `otext.tf` headers from the partial repository. Those blob reads can cause Git's promisor remote machinery to contact the network.

Offline collection discovery/prepare must therefore require a matching installed/cached index rather than regenerating one opportunistically.

### Existing explicit immutable collection revisions are already fail-closed

When a caller supplies `source_revision` for a collection, `_collection_repo()` validates the immutable SHA and resolves it from the cached metadata repository without falling back to current upstream state. This behavior must remain intact.

## Git failure-classification constraint

Git does not expose a portable structured subprocess status that means "network unavailable". Fetch failures use a non-zero process exit status and transport-specific human-readable stderr. Authentication failure, repository deletion, missing refs, DNS failure, proxy failure, refused connections, and timeouts can all surface through the same `CalledProcessError` type.

References:

- Git fetch: <https://git-scm.com/docs/git-fetch>
- Git environment variables (`GIT_TERMINAL_PROMPT`): <https://git-scm.com/book/en/v2/Git-Internals-Environment-Variables>

It would be unsafe to interpret every failed refresh as permission to serve stale state. Automatic fallback must be deliberately narrow and unknown failures must fail closed.

## Resolution policy

Expose one mutually exclusive source-resolution mode rather than interacting booleans:

```text
source_mode = "prefer-fresh" | "offline" | "require-fresh"
```

`prefer-fresh` is the default and preserves current online behavior when the remote is reachable.

### `prefer-fresh`

1. If no metadata repository exists, clone/fetch normally.
2. If metadata exists, attempt the normal remote refresh.
3. On success, update `refs/agora/selected` and mark the result `remote` / freshness verified.
4. On a conservatively recognized connectivity failure only, reuse the previously selected commit **if** the exact downstream artifacts needed by the operation are already resident.
5. On authentication, authorization, repository-not-found, ref-not-found, malformed remote, or any unclassified fetch failure, fail; do not silently reuse cached state.
6. If metadata can fall back but the required source snapshot/index is absent, return an actionable cache-miss error rather than starting another network operation under the guise of cached fallback.

### `offline`

1. Perform no clone, fetch, lazy blob retrieval, or disposable export fetch.
2. Require an existing metadata repository with a valid `refs/agora/selected`, unless the caller supplied an explicit immutable collection revision already present locally.
3. Require the exact published corpus/feature-module snapshot needed by prepare/load.
4. For collection discovery/selection, require a matching installed or cached member index.
5. Reuse an existing composed overlay where valid; composing a new overlay is allowed only when all required source snapshots are already resident because composition itself is local.
6. Fail immediately with an actionable offline cache-miss error if any required object is missing.

### `require-fresh`

1. Require the normal remote metadata refresh.
2. Any refresh failure is an error; never fall back to `refs/agora/selected`.
3. Subsequent materialization may use an existing immutable snapshot for the freshly resolved revision or acquire it normally.

## Stable compatibility surface

`GitStore.ensure_metadata()` is an established low-level API used by tests and repository code. Do not change its return type from `Path`.

Add a richer selection primitive, conceptually:

```python
@dataclass(frozen=True)
class MetadataSelection:
    repo: Path
    revision: str
    source_resolution: Literal["remote", "cached", "explicit-revision"]
    source_revision_verified: bool

GitStore.select_metadata(..., source_mode="prefer-fresh") -> MetadataSelection
```

`ensure_metadata()` remains a compatibility wrapper for the historical fresh/default behavior and returns `selection.repo`.

Resolver paths that need provenance use `select_metadata()` directly.

The exact names may be adjusted during implementation if tests reveal a clearer API, but the semantic distinction must remain explicit.

## Response provenance

Prepared/loaded results must expose both revision identity and how it was selected.

Required fields:

```text
source_revision: <immutable commit SHA>
source_resolution: remote | cached | explicit-revision
source_revision_verified: true | false
```

Semantics:

- `remote` + `true`: this operation successfully refreshed the configured upstream selection before resolving the revision;
- `cached` + `false`: remote freshness was not established for this operation and the previous local selection was used;
- `explicit-revision` + `false`: the caller explicitly requested an immutable cached revision. `false` means "not remotely freshness-checked", not "revision identity is uncertain".

The immutable SHA remains the provenance anchor in every case.

Feature-module provenance should carry the same per-module resolution metadata because a parent loaded offline while a selected module refreshes online would violate the caller's `offline` contract.

## Connectivity-failure classification

Automatic `prefer-fresh` fallback needs a small, testable classifier at the Git boundary.

Requirements:

- force Git diagnostic locale to a stable locale (for example `LC_ALL=C`) for the refresh subprocesses whose stderr is classified;
- inspect the failed command and stderr, not only the exit code;
- recognize only a narrow list of transport failures such as DNS resolution failure, proxy resolution failure, network unreachable, connection refused, and connection timeout;
- do not classify authentication failure, permission failure, repository-not-found, missing ref, or unknown stderr as connectivity fallback;
- retain the original Git stderr as the cause/debug detail while exposing a concise user-facing error.

The classifier is an integration safety mechanism, not a claim that Git offers a universal network error taxonomy. Explicit `offline` remains the deterministic way to guarantee zero network attempts.

## Actionable error model

Introduce Agora-owned errors that can be rendered cleanly by the MCP layer without exposing a raw argv dump as the primary message.

At minimum distinguish:

### Network required / offline cache miss

Examples:

- no metadata repository/selected ref exists;
- selected revision exists but the required published corpus snapshot was evicted;
- selected revision exists but a required feature-module snapshot is absent;
- collection revision exists but no matching installed/cached member index is available.

Message must name the resource/object and state that network-enabled preparation is required before offline use.

### Refresh failure

Used by `require-fresh` and by unclassified/non-connectivity failures in `prefer-fresh`.

Message must say upstream refresh failed and preserve the underlying Git failure as the exception cause. It must not silently turn authentication/ref/repository errors into cached success.

## Resolver propagation

The source mode must be propagated through every acquisition-bearing route:

- corpus version discovery where it causes resource resolution;
- `list_collection_members`;
- `prepare_corpus`;
- `load_corpus`;
- parent corpus resolution;
- every selected feature module;
- collection member selection.

Omitting `source_mode` must preserve the existing public call shape used by compatibility/delegation tests; wrappers should forward it only when explicitly supplied if downstream signatures depend on exact kwargs.

## Materialization changes

The low-level materialization API needs an explicit no-network guard, conceptually:

```text
materialize(..., allow_network=False)
materialize_feature_module(..., allow_network=False)
```

or an equivalent cached-only method.

For cached-only behavior:

1. resolve the commit locally;
2. compute the exact revision-addressed destination;
3. validate the existing destination;
4. touch/index it and return if valid;
5. otherwise raise an offline cache-miss error **before** `_export_snapshot()`.

Do not infer that Git object presence makes export network-free. The published snapshot is the offline residency boundary.

## Overlay behavior

A composed overlay is Agora-derived and can be built locally from existing source snapshots. Offline mode may therefore:

- reuse a valid existing overlay; or
- compose a new overlay when the parent and every selected module snapshot are already resident.

It must not fetch missing module/parent bytes to complete that composition.

The existing cache-transition/lease protocol remains unchanged.

## Collection behavior

### Discovery without an explicit `source_revision`

- `prefer-fresh`: refresh normally, or use the selected cached revision only after a recognized connectivity failure and only when a matching installed/cached index exists;
- `offline`: select the cached revision and require a matching installed/cached index;
- `require-fresh`: refresh and require the refreshed revision's index resolution to proceed normally.

### Explicit immutable `source_revision`

Keep current fail-closed semantics: never substitute current upstream state. The supplied commit must exist in the local metadata repository for offline use. A matching installed/cached index and source snapshot are still required for zero-network prepare/load.

## Pinned versus floating resources

A configured `ref` does not remove the need for explicit freshness semantics:

- online/default resolution may still fetch the configured ref to confirm what commit it denotes;
- offline resolution reuses the locally selected immutable commit and reports `source_revision_verified: false` for this operation;
- once the exact published snapshot exists, pinned resources are fully usable offline;
- if the snapshot was evicted, offline mode fails rather than assuming the partial metadata repo contains every blob.

If future registry policy restricts `ref` to immutable SHAs, that can simplify freshness language later but is not required for #44.

## Locking and concurrency

Reuse existing locks:

- repository lock around metadata selection/refresh;
- cache-transition lock around preparation/materialization/composition and final lease acquisition;
- object leases for loaded cache objects.

A failed online refresh must not overwrite `refs/agora/selected`. The previous selected ref becomes eligible for cached fallback only after the failed refresh is classified as connectivity-related.

No new create/delete sentinel or distributed lock is needed.

## MCP/API contract

Add optional `source_mode` to the Agora-owned acquisition tools:

```text
list_collection_members(..., source_mode=None)
prepare_corpus(..., source_mode=None)
load_corpus(..., source_mode=None)
```

`None` means the default `prefer-fresh` behavior while preserving historical delegation shape where useful.

Document the accepted values and reject unknown values before any network/cache mutation.

An environment variable is not required for #44 because the issue accepts an env var **and/or** tool argument. Per-call control is more reproducible and avoids hidden server-global policy.

## RED test gate before production code

Implementation must begin with failing tests committed separately.

### Git selection tests

1. cached metadata + recognized DNS/connection failure in `prefer-fresh` returns the previous selected commit and marks it cached/unverified;
2. authentication failure does not fall back;
3. repository-not-found/ref-not-found does not fall back;
4. unknown Git failure does not fall back;
5. `offline` never invokes clone/fetch;
6. `require-fresh` never falls back;
7. failed refresh leaves the previous `refs/agora/selected` unchanged;
8. uncached `offline` produces an actionable network-required error.

### Snapshot/materialization tests

9. a valid published corpus snapshot is reusable with network disabled;
10. a selected revision with no published snapshot fails before `_export_snapshot()`;
11. same contract for feature-module snapshots;
12. a locally composable overlay succeeds offline when all input snapshots are resident;
13. a missing parent/module snapshot fails without a network call.

### Resolver/service/MCP tests

14. prepared/loaded responses expose revision, resolution, and verification fields;
15. module metadata records its own source resolution;
16. `prepare_corpus` and `load_corpus` succeed on a fully cached local fixture in `offline` mode;
17. `list_collection_members` uses a matching installed/cached index offline and never regenerates it from potentially missing blobs;
18. collection offline cache miss is actionable;
19. explicit immutable `source_revision` is never replaced with current state;
20. omitted `source_mode` preserves existing compatibility/delegation behavior;
21. invalid `source_mode` fails before acquisition.

### Regression realism

Use local temporary Git repositories and explicit subprocess/network spies, not external GitHub availability, for the deterministic unit gate. A small integration smoke may additionally force an unreachable proxy after warming a local fixture if useful, but CI must not depend on an ambient outage.

## Documentation gate

Update `wiki/guides/context-fabric-cache.md` (and installation/usage documentation where appropriate) with:

- default `prefer-fresh` behavior;
- deterministic `offline` behavior;
- `require-fresh` behavior;
- meaning of `source_resolution` / `source_revision_verified`;
- the fact that metadata alone is insufficient after a source snapshot was evicted;
- actionable recovery: reconnect and prepare/load once to republish the required snapshot;
- collection-index and feature-module offline requirements.

## Rejected alternatives

### Fall back after every `git fetch` failure

Rejected because Git does not distinguish connectivity from auth/ref/repository failures through a portable subprocess error type. This could silently serve stale data after a meaningful upstream error.

### Treat a cached commit as sufficient for offline materialization

Rejected because `_export_snapshot()` deliberately performs a fresh fetch in a disposable partial repository. Commit/tree metadata does not guarantee corpus blobs are resident.

### Serve the mutable metadata repository working tree

Rejected by the revision-snapshot architecture. Published source bytes must remain revision-addressed immutable snapshots.

### Make offline a server-global implicit environment mode only

Rejected for #44. It makes per-operation provenance less reproducible and complicates mixed workflows. An explicit tool argument is sufficient; a future server default can be added separately if justified.

### Change Context-Fabric upstream loading behavior

Rejected as out of scope. Once Agora supplies the same prepared path, upstream loading semantics remain unchanged.

## Implementation sequence after this gate merges

1. commit RED tests for selection modes, error classification, snapshot residency, provenance propagation, collection/member/module behavior, and MCP compatibility;
2. implement metadata selection result + conservative refresh classifier while preserving `ensure_metadata()` compatibility;
3. implement cached-only materialization/index resolution paths;
4. propagate source policy/provenance through resolver → service → MCP tools;
5. update documentation;
6. run the full Foundation gate and relevant cross-platform cache lifecycle tests;
7. run logically independent adversarial review against the exact implementation head;
8. fix review findings with regression tests and repeat the gate before merge.

## Out of scope

- changing Context-Fabric data/query/compiler semantics;
- guaranteeing availability after a user explicitly prunes/evicts required source snapshots;
- prefetching every corpus so all registered resources work offline by default;
- generic Git repository housekeeping (#45);
- load-cost metadata (#38);
- true MCP progress/timing telemetry (#27).
