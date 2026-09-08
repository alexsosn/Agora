# Research Context-Fabric Git metadata maintenance (#45)

## Question

Which parts of issue #45 still apply after Agora moved Context-Fabric corpus bytes into immutable revision snapshots, and what is the smallest Agora-owned maintenance contract that can safely reclaim persistent Git metadata debt without adding latency or risking concurrent acquisition?

## Baseline inspected

Agora `main` at `94bcddb45c9e1e7a1bcb766ce82a820f8be4209c`.

Relevant current implementation:

- `plugins/context-fabric/src/agora_context_fabric/gitstore/_core.py`
- `tests/test_context_fabric_cache_lifecycle.py`
- `tests/test_context_fabric_cache_discovery.py`
- `wiki/architecture/ref-context-fabric-cache-lifecycle.md`

Issue #45 was filed against `bf5fb91`, before immutable source snapshots, cross-process cache leases/eviction, and offline source-resolution work landed.

## Findings

### 1. Persistent repositories are now metadata stores, not corpus working trees

`GitStore` explicitly describes `repositories/` as metadata-only. `ensure_metadata()` still creates a partial non-checkout clone and refreshes a selected commit, but corpus/module bytes are no longer checked out there.

Materialization now creates exact revision-addressed source snapshots under `snapshots/`. `_export_snapshot()` uses a **disposable** partial Git repository under `tmp/`, streams `git archive`, then removes the whole temporary repository. Garbage or pack fragmentation inside that disposable export repository therefore does not persist after the operation.

This makes the original claim that a cache repository is also the mutable served corpus tree obsolete.

### 2. The old `git status` symptom remains observable but has different meaning

A non-bare `git clone --no-checkout` can report every tracked path as a staged deletion even when Agora has never checked out corpus data. A minimal Git experiment against the current clone shape reproduces that behavior.

That output is now an implementation artifact of a metadata-only non-checkout clone, not evidence that an Agora source snapshot is dirty or incomplete. No current load path consumes the persistent repository working tree.

Changing the persistent cache to a bare-repository layout would make this representation cleaner, but it would introduce a repository-layout migration and backward-compatibility problem unrelated to garbage collection. It is not required to fix the remaining storage debt.

For #45, `corpus_cache_status` should become the supported inspection surface for repository maintenance health. Documentation should state that `repositories/` are internal metadata stores and `git status` is not a source-snapshot integrity signal.

### 3. Persistent repositories can still accumulate packs and interrupted-fetch garbage

The persistent metadata repository still uses:

- filtered shallow clone;
- filtered shallow fetch on source selection;
- `git show` in `tf_header_metadata()` and `_git_show_lines()`.

With a promisor remote, `git show <commit>:<blob>` may lazily fetch missing blobs. Those fetched blobs remain in the persistent repository and can produce additional packs. An interrupted selection or lazy fetch can leave Git-recognized `tmp_pack_*` / `tmp_obj_*` garbage in that same repository.

A code search of the current Context-Fabric implementation finds no `git gc`, `git repack`, `git prune`, `git prune-packed`, or equivalent repository maintenance operation.

A local Git experiment also confirms that `git gc --prune=now` removes a planted `objects/pack/tmp_pack_*` file that `git count-objects -v` reports as garbage.

Therefore the core storage-health finding in #45 still applies to **persistent Git metadata repositories**, although the original explanation based on path checkout no longer does.

### 4. Current cache accounting excludes metadata repositories entirely

`_cache_tree_bytes()` counts only:

- `snapshots/`
- `overlays/`

`cache_status()` and `prune()` therefore describe the logical materialized-object cache, not the complete on-disk `AGORA_CORPUS_CACHE` tree. Bytes under `repositories/` are not `unindexed_cache_bytes`; they are outside the measured logical cache altogether.

This is safer than the issue's original assumption but still leaves an observability gap: a user can see a healthy snapshot/overlay cache while metadata repositories contain avoidable pack/garbage debt.

The logical snapshot/overlay soft limit should keep its existing meaning. Repository bytes and garbage should be reported as a separate cache component rather than silently folded into LRU semantics.

### 5. The existing repository lock is insufficient for safe `gc --prune=now`

`ensure_metadata()` holds `_repository_lock()` while cloning/fetching/selecting.

However `tf_header_metadata()` and `_git_show_lines()` execute `git show` outside that lock. In a partial clone, those apparently read-only commands can trigger a promisor-object fetch and mutate `.git/objects`.

Git documentation warns that immediate pruning is unsafe when another Git process may write objects. Adding `git gc --prune=now` under the current selection lock alone would therefore leave a race with lazy blob acquisition.

Before maintenance can be safe, all persistent-repository operations that can trigger lazy object acquisition must participate in the same repository-use lock domain. The maintenance path then takes that lock exclusively.

### 6. Maintenance should be explicit housekeeping, not prepare/load latency

The current cache architecture deliberately keeps startup/prepare/load free of unconditional full-cache housekeeping. #45 should preserve that property.

Running `git gc` after every `ensure_metadata()` would:

- put maintenance latency on interactive acquisition;
- run even when there is no garbage or meaningful pack fragmentation;
- still need the lazy-fetch concurrency fix above.

The existing explicit `prune_corpus_cache` path is the natural maintenance trigger. Before deleting logical source/overlay objects, it can inspect cached metadata repositories and run bounded best-effort Git maintenance only where debt crosses a documented trigger.

### 7. `git gc --prune=now` is a suitable bounded primitive if guarded

For an explicit housekeeping operation, `git gc --prune=now` has useful properties:

- removes Git-recognized temporary garbage in local experiments;
- consolidates packs rather than requiring Agora to manipulate pack files itself;
- respects Git's object/promisor semantics better than manually deleting `tmp_*` paths;
- works on the existing non-bare metadata repository layout.

But it must be:

- executed under the repository's exclusive mutation/use lock;
- protected by a subprocess timeout;
- best effort and non-fatal to ordinary corpus usability;
- skipped when repository status shows neither garbage nor excessive pack fragmentation.

A conservative initial pack trigger should be encoded as a named constant and tested, not inferred from repository size. The exact threshold is an operational policy rather than scholarly behavior.

## Rescoped user requirements

### UR1 — Persistent Git debt is observable

Users can see metadata-repository bytes, pack counts, and Git-recognized garbage separately from logical snapshot/overlay cache residency.

### UR2 — Explicit prune can reclaim repository debt

`prune_corpus_cache` performs bounded best-effort maintenance for cached metadata repositories whose garbage or fragmentation crosses the configured trigger.

### UR3 — Maintenance cannot race lazy acquisition

Source selection and persistent-repo blob reads that may trigger promisor fetches participate in one lock domain; Git maintenance takes it exclusively.

### UR4 — Interactive acquisition stays predictable

Normal startup, describe, prepare, and load do not run unconditional `git gc`/repack sweeps.

### UR5 — Existing cache semantics remain compatible

The existing snapshot/overlay soft limit and object LRU semantics do not silently change. Repository debt is a separately reported/reclaimable component.

### UR6 — Metadata repositories are inspectable through Agora

Documentation tells users that `repositories/` are internal metadata-only non-checkout stores and that `git status` is not a source-snapshot integrity check. Agora exposes the meaningful repository-health metrics instead.

## Rejected directions

### Run `git gc` after every prepare/fetch

Rejected because it adds surprise latency to user-facing acquisition and runs without evidence of maintenance debt.

### Delete `tmp_pack_*` / `tmp_obj_*` directly

Rejected because Git should own object-database cleanup. Manual filename deletion risks treating implementation details as a stable contract.

### Convert every existing metadata cache to a bare repository in this ticket

Rejected because it is a layout migration with downgrade/legacy-cache implications. It is unnecessary for reclaiming garbage or bounding fragmentation.

### Fold repository bytes into `snapshot_soft_limit_bytes`

Rejected because that would silently change the meaning of the existing logical source/overlay LRU target and could evict corpus snapshots because of independently managed Git metadata.

## Implementation direction

1. Extend the repository lock helper so persistent repository reads that may lazy-fetch blobs can participate in the same lock domain as selection/maintenance.
2. Add deterministic repository-status parsing based on `git count-objects -v` plus actual repository-directory bytes.
3. Add separately named repository-cache metrics to `cache_status()`.
4. Add explicit-prune maintenance with debt triggers, an execution timeout, and per-repository success/failure reporting.
5. Keep maintenance failures non-fatal and continue ordinary logical LRU pruning.
6. Document the metadata-only repository model and the supported inspection/maintenance path.
7. Add cross-platform deterministic regressions for garbage cleanup, fragmentation trigger behavior, lock exclusion, timeout/failure behavior, and status accounting.

## Scope boundary

This is Agora-owned acquisition/cache housekeeping and observability. It does not change Text-Fabric data, Context-Fabric parsing/query semantics, corpus contents, upstream Git history, or scholarly results.
