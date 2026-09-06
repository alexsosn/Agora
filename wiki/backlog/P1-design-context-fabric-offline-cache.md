# Design: Context-Fabric offline resolution policy

Issue: #44
Research: `wiki/backlog/P1-research-context-fabric-offline-cache.md`

## Goal

Allow already materialized Context-Fabric resources to remain usable when the network is unavailable, without weakening source identity, commit-bound collection semantics, cache lifecycle safety, or error transparency.

## Non-goals

- changing cfabric/Text-Fabric loading or query semantics;
- adding a background downloader or retry daemon;
- making arbitrary remote Git failures look like offline conditions;
- serving metadata-only cache state as though corpus bytes were available;
- changing collection-member identity/index semantics;
- making cache objects immortal or bypassing leases/LRU bookkeeping.

## Public modes

`network_mode` is one of:

- `auto` — attempt remote resolution; on recognized connectivity failure only, fall back to compatible complete cached state;
- `offline` — never invoke a remote-capable Git path; require complete compatible local state;
- `require-fresh` — remote resolution must succeed; never use a stale fallback.

Default mode is `auto`. `AGORA_CORPUS_NETWORK_MODE` sets the process default. A tool-call argument overrides it for the dynamic scope of that request.

Use `ContextVar`, not a mutable module global, so concurrent MCP requests do not leak mode into one another.

## New resolution model

Add a small `network.py` module owning only source-acquisition policy and errors.

```python
@dataclass(frozen=True)
class RepositoryResolution:
    path: Path
    revision: str
    source_revision_verified: bool
    resolution: Literal["fresh", "cached"]
    allow_network: bool
```

The resolver asks this layer to resolve a repository. Fresh resolution uses the existing `GitStore` repository lock and Git selection primitives, but it keeps clone/fetch/select, exact revision capture, and selection-provenance persistence in one cross-process critical section. This is stronger than calling `GitStore.ensure_metadata()` followed by `selected_revision()`, because that historical API releases the repository lock before a caller can bind provenance to the selected ref. Cached resolution reads the selected ref and persisted provenance under the same repository lock, then uses only local Git state and existing cache-object metadata.

### Errors

- `NetworkUnavailableError`: network connectivity prevented a required fresh operation;
- `OfflineCacheMissError`: explicit/degraded offline resolution cannot satisfy the request from compatible complete local state;
- `RemoteResolutionError`: Git failed for a non-connectivity remote/configuration reason and stale fallback is forbidden.

Unknown Git failures become `RemoteResolutionError`.

## Persisted selection record

After each successful online repository selection, atomically write:

```json
{
  "repository": "<configured repository string>",
  "configured_ref": null,
  "revision": "<full commit>"
}
```

at `.git/agora-selection.json`.

The record is Agora metadata, not upstream repository state.

The selected Git ref, captured commit id, and record write are one repository transaction. Another process may select a different ref only after that transaction releases the repository lock. A request therefore never labels another process's selected commit as its own fresh result. Cached readers take the same lock while reading `refs/agora/selected` plus the record so they cannot observe a half-transition.

### Matching rules

Before cached fallback:

1. verify the cached repository's `origin` is equivalent to the current configured repository after `GitStore.repository_url()` normalization;
2. read `refs/agora/selected` and resolve it to an exact commit;
3. when a selection record exists, require exact equality of repository, configured ref (including `null`), and revision;
4. when no record exists:
   - immutable configured SHA: require SHA == selected revision;
   - floating `ref=None`: allow repository + selected revision as legacy degraded state, freshness false;
   - mutable non-SHA ref: require legacy `FETCH_HEAD` evidence binding the selected revision to that exact configured ref; otherwise fail closed.

A malformed record is not treated as “record absent”; it is incompatible state and fails closed. This prevents corruption from silently re-enabling broad legacy fallback.

### Legacy `FETCH_HEAD` inference

Parse only Git's tab-separated `FETCH_HEAD` records. Accept a record when:

- commit field equals the selected revision;
- it is the mergeable selected record;
- its description has one of the recognized forms for the exact configured ref (branch or tag) and repository;
- exactly one record satisfies the condition.

Do not accept substring matches, abbreviated commit ids, or an unknown description form. This is a migration bridge, not a general parser. Tests must construct the legacy cache through the pre-record Git selection sequence so the evidence represents real Git output on CI platforms. A real transport-failure regression also removes the new selection record from a mutable-ref cache before breaking the remote, so default `auto` migration is exercised against Git's actual `FETCH_HEAD` behavior rather than only mocked failures.

## Resolver integration

Extend `PreparedCorpus` and `PreparedFeatureModule` with:

- `source_revision_verified: bool = True`;
- `resolution: str = "fresh"`.

Defaults preserve existing call sites/tests that construct these dataclasses directly.

### Ordinary corpora

`ContextFabricResolver._repo(resource)` calls `resolve_repository(...)` and returns the `RepositoryResolution` rather than a bare `(repo, revision)` pair. Dataset-root inspection uses the returned exact revision.

Materialization uses a policy helper:

- when `allow_network=True`, call existing `GitStore.materialize*()`;
- when `allow_network=False`, locate the exact indexed existing cache object and touch/validate it without calling snapshot export.

Propagate resolution/freshness fields into prepared results.

### Collections

Preserve current `CollectionIndexManager` behavior.

For `source_revision is None`, resolve the collection repository through the normal network-mode policy and build/resolve the index for that exact resolved commit.

For explicit immutable `source_revision`:

- keep current local cached-repository lookup;
- verify the commit exists locally;
- do not call current-state remote resolution;
- prepare the exact member from that commit-bound index;
- in explicit `offline` mode, require the member snapshot already exists instead of exporting/fetching it.

The caller-selected exact revision is not substituted on cache miss.

### Feature modules

Resolve each module repository through the same network mode. Parent and module provenance are kept independently. An offline module cache miss fails the whole module-enabled prepare rather than silently dropping the module.

### Overlays

Do not change overlay identity or composition. Existing overlay reuse remains valid when all prepared source inputs resolve to the same exact identities. Composition still occurs locally and uses current cache lifecycle bookkeeping.

## Service / MCP surface

Integrate provenance into `ContextFabricService._prepared_dict()` directly; avoid a permanent service subclass whose only purpose is rendering two fields.

Prepared/load results include:

```json
{
  "source_revision": "...",
  "source_revision_verified": false,
  "resolution": "cached"
}
```

Each selected feature module exposes the same fields.

Add optional `network_mode` to:

- `prepare_corpus`;
- `load_corpus`;
- collection discovery/listing tools that resolve current upstream state;
- version/default-version helpers if they are public and currently perform remote resolution.

At minimum all user-facing code paths that can invoke `_repo()` must have a well-defined mode. Tool wrappers enter `use_network_mode(network_mode)` only for the duration of the service call. Omitting the argument uses the environment/default mode.

Explicit `source_revision` collection requests remain exact and should not need remote freshness; `network_mode=offline` still prevents any missing-byte acquisition.

## Connectivity classification

`GitStore._run()` currently preserves stderr on `CalledProcessError`. `network.py` classifies only a bounded set of connectivity phrases covering Git/curl/SSH DNS, refused/unreachable, timeout, proxy, reset, and TLS-connectivity failures observed in supported environments.

The classifier is conservative:

- auth denied -> remote error;
- repository not found -> remote error;
- ref not found -> remote error;
- unknown stderr -> remote error.

Tests exercise representative connectivity and non-connectivity messages.

## Cache lookup

Use current `GitStore.cache_entries(resource_id)` and exact identity sidecars. Cached object lookup requires exact:

- resource id;
- kind;
- revision;
- relative path.

After locating a candidate, call existing validation/touch logic. Never infer an evictable snapshot by directory-tree heuristics.

This preserves the safety rule introduced by the cache lifecycle work: pre-index nested directories are not guessed to be independent cache objects.

## TDD sequence

### RED 1 — mode and provenance contract

Add tests importing the not-yet-existing network policy and asserting:

- mode validation/request scoping;
- public prepared result provenance;
- cached floating fallback and require-fresh behavior;
- non-connectivity errors never fall back.

Expected RED: import/API failures and current unconditional fetch behavior.

### GREEN 1

Add the policy module, dataclass fields, fresh/cached repository selection, service rendering, and tool mode scoping for ordinary corpora.

### RED 2 — cache identity migration

Add tests for:

- persisted ref transitions (`branch -> None`, `None -> branch`, `branch A -> branch B`);
- legacy floating cache;
- legacy mutable-ref `FETCH_HEAD` inference;
- immutable SHA cache.

Expected RED before implementation: legacy branch cache rejected or mismatched configurations accepted.

### GREEN 2

Implement strict record matching and conservative legacy inference.

### RED 3 — current collection-index and module integration

Add tests on the current resolver shape for:

- offline exact collection `source_revision` + member snapshot;
- missing member snapshot without hidden fetch;
- current-state collection fallback preserving commit-bound index revision;
- feature-module snapshot reuse and provenance.

Expected RED: current resolver bypasses policy or offline path calls export fetch.

### GREEN 3

Thread resolution through current collection and module paths without replacing `CollectionIndexManager` or cache lifecycle behavior.

### RED/GREEN 4 — real Git boundary

Use temporary real repositories / `git daemon` to prove:

- online prepare creates real metadata/snapshot;
- daemon/network loss in `auto` reuses the exact snapshot;
- warm-cache `ContextFabricService.load()` still resolves, leases, loads, reports cached provenance, and unloads after the daemon disappears;
- explicit offline makes no remote attempt;
- uncached/offline and uncached/connectivity errors are actionable;
- a pre-record mutable-ref cache still has sufficient real Git evidence for default `auto` fallback after the transport fails.

### RED/GREEN 5 — adversarial repository-selection atomicity

The first logically independent review found a race between `ensure_metadata()` returning and the caller reading `refs/agora/selected`: another process could select ref B in that gap, causing a request for ref A to return and persist B's commit as fresh A provenance.

Add a deterministic regression whose `GitStore` wrapper performs the competing selection immediately after the repository lock exits. The RED result must show the request returning the competing commit. GREEN keeps clone/fetch/select, exact revision capture, and selection-record persistence under one repository lock and also locks the cached selected-ref/record read. Run this regression on Ubuntu, macOS, and Windows.

## Test gates

Focused tests must pass before repository-wide tests:

```bash
python -m unittest tests.test_context_fabric_offline -v
python -m unittest tests.test_context_fabric_offline_integration -v
python -m unittest tests.test_context_fabric_resolution_service -v
python -m unittest tests.test_context_fabric_selection_atomicity -v
```

Then run all existing Context-Fabric resolver/service/cache tests and the Foundation workflow. Because mode scoping and filesystem/Git behavior are cross-platform concerns, the final relevant test set must run on Ubuntu, macOS, and Windows or be covered by an existing cross-platform Foundation matrix.

## Documentation

Update the installation/usage guide with:

- default `auto` behavior;
- explicit `offline` and `require-fresh` modes;
- `AGORA_CORPUS_NETWORK_MODE`;
- meaning of `resolution` and `source_revision_verified`;
- offline success requires previously materialized bytes, not merely Git metadata;
- stale fallback is never used for auth/ref/repository errors.

## Independent review checklist

The final review must re-derive the behavior from current `main` and check:

1. no obsolete pre-collection-index resolver code was restored;
2. no cfabric/Text-Fabric semantic behavior changed;
3. `offline` has no hidden fetch path, including snapshot export;
4. stale fallback cannot cross repository/ref identity changes;
5. malformed selection metadata fails closed;
6. legacy mutable refs are accepted only with unambiguous local evidence;
7. exact collection `source_revision` is never substituted;
8. module and collection source provenance remains independent and honest;
9. cache-object lookup respects current sidecar/lease/eviction rules;
10. `ContextVar` mode scoping cannot leak across requests;
11. errors distinguish network loss from remote/configuration failures;
12. fresh selection plus provenance persistence is atomic across competing processes and cached readers cannot observe a half-transition;
13. CI is green on the exact final head.
