# Design Context-Fabric Git metadata maintenance (#45)

## Objective

Make persistent Context-Fabric Git metadata debt observable and explicitly reclaimable without changing snapshot/overlay LRU semantics, adding surprise prepare/load latency, or racing promisor-object acquisition.

Research: [`P1-research-context-fabric-git-maintenance-45.md`](P1-research-context-fabric-git-maintenance-45.md).

## Ownership boundary

Agora owns its local Git metadata cache, source selection, acquisition coordination, cache status, and explicit prune behavior. This design does not alter upstream history, Text-Fabric data, Context-Fabric query semantics, or scholarly output.

## Current-state constraints

1. Persistent `repositories/` entries are non-checkout partial clones used as Git metadata/promisor stores.
2. Served corpus/module bytes live in revision snapshots; overlays are Agora-derived cache objects.
3. Disposable snapshot-export repositories are removed after materialization and are not maintenance targets.
4. Persistent `git show` may lazily fetch blobs and mutate the object database despite looking read-only.
5. Existing snapshot/overlay `cache_bytes` and `snapshot_soft_limit_bytes` semantics must not change silently.
6. `prune_corpus_cache` is already the explicit housekeeping operation; ordinary prepare/load stays free of unconditional maintenance sweeps.
7. Bounded latency is a whole-operation property, not a per-repository timeout multiplied by repository count.
8. Best-effort status must never turn a partial repository scan into an exact-looking aggregate.

## Public behavior

### Cache status

Keep existing logical cache fields unchanged. Add a separate metadata-repository section with at least:

```text
repository_cache_bytes
repository_cache_bytes_complete
repository_cache_gb
repository_git_metrics_complete
repository_pack_count
repository_garbage_entries
repository_garbage_bytes
repository_garbage_gb
repository_inspection_budget_seconds
repository_inspection_budget_exhausted
repositories: [...]
```

Each repository row identifies the cache key/path and, when inspection succeeds:

```text
size_bytes
size_complete
packs
garbage_entries
garbage_bytes
maintenance_needed
busy
inspection_status
```

`inspection_status` is one of `ok`, `busy`, `budget-exhausted`, or `error`.

The **entire new repository-inspection phase** shares one monotonic deadline: `DEFAULT_GIT_STATUS_BUDGET_SECONDS = 2`. That deadline covers:

- repository lock acquisition;
- `git count-objects -v` subprocess execution;
- recursive filesystem-size measurement for repository rows;
- iteration over all persistent repositories.

Every blocking operation receives at most the remaining whole-operation budget. `git count-objects -v` therefore runs with a subprocess timeout derived from the remaining deadline; a lock timeout alone is insufficient. Recursive directory-size helpers must check the same deadline while walking and stop when it expires.

If a live acquisition keeps a repository busy, report `busy: true` rather than waiting beyond the remaining budget. Once the deadline expires, remaining rows report `inspection_status: budget-exhausted` without further Git inspection or recursive size walks.

Never publish a partial byte count as exact. If a repository size walk is interrupted, that row uses `size_bytes: null`, `size_complete: false`. If any repository size is incomplete, aggregate `repository_cache_bytes`/`repository_cache_gb` are `null` and `repository_cache_bytes_complete: false` rather than a deceptively low partial total.

Apply the same truthfulness rule independently to Git object metrics. Per-repository `packs`, `garbage_entries`, and `garbage_bytes` are populated only after that repository's `git count-objects -v` succeeds. If **any** persistent repository is `busy`, `budget-exhausted`, or `error` before a successful count-objects result, aggregate `repository_pack_count`, `repository_garbage_entries`, `repository_garbage_bytes`, and `repository_garbage_gb` are `null` and `repository_git_metrics_complete: false`. Successfully inspected row metrics remain visible; they are not promoted into a misleading partial aggregate. Only when every persistent repository has a successful count-objects result is `repository_git_metrics_complete: true` and are those aggregate values exact.

Filesystem-size completeness and Git-metrics completeness are independent. A repository may have complete `git count-objects` metrics but an interrupted recursive size walk; in that case Git aggregates may remain complete while repository byte aggregates are null/incomplete. Conversely, no partial Git aggregate is inferred from filesystem size.

The same truthfulness rule applies to the requested whole-cache filesystem count: expose it only when its deadline-aware traversal completes; otherwise expose an explicit incomplete/null result. Existing logical `cache_bytes` remains exact within its current scope and is not redefined.

### Explicit prune

`prune_corpus_cache` gains a bounded Git-maintenance phase before ordinary logical LRU eviction.

The whole Git-maintenance phase has one monotonic deadline: `DEFAULT_GIT_MAINTENANCE_BUDGET_SECONDS = 30`. Per-GC ceiling remains `DEFAULT_GIT_MAINTENANCE_TIMEOUT_SECONDS = 15`, but **every** repository lock wait and Git subprocess, including both pre/post `git count-objects -v`, receives at most the remaining whole-operation budget. The budget never resets per repository.

Iterate persistent repositories in deterministic cache-key order:

1. if no maintenance budget remains, mark this and all remaining repositories skipped with reason `budget-exhausted`, then proceed immediately to logical LRU pruning;
2. acquire the repository-use lock exclusively, bounded by the smaller of caller lock policy and remaining maintenance budget;
3. run `git count-objects -v` with timeout bounded by remaining budget and parse deterministic fields;
4. run maintenance only when Git reports garbage or pack count exceeds `DEFAULT_GIT_MAINTENANCE_PACK_LIMIT = 16`;
5. invoke `git gc --prune=now` with timeout `min(DEFAULT_GIT_MAINTENANCE_TIMEOUT_SECONDS, remaining_budget)`;
6. re-read Git status after success only if enough budget remains, again using the remaining deadline;
7. release the repository lock;
8. continue to other repositories and then logical LRU pruning even when maintenance fails, times out, or the global budget expires.

The 16-pack trigger is operational policy. It catches the original measured 20–21-pack fragmentation without repacking healthy stores. Partial-clone promisor packs are Git-managed separately, so tests require real consolidation/reduction of a fragmented fixture, not an implementation-specific claim that every repository ends with exactly one pack.

Prune results include aggregate and per-repository outcomes such as:

```text
repository_maintenance_budget_seconds
repository_maintenance_budget_exhausted
repository_maintenance_attempted
repository_maintenance_succeeded
repository_maintenance_failed
repository_maintenance_timed_out
repository_maintenance_skipped_budget
repository_bytes_reclaimed
repository_garbage_entries_removed
repository_packs_before
repository_packs_after
```

Maintenance failure or budget exhaustion is a visible housekeeping result, never a corpus-resolution failure and never a reason to suppress successful snapshot/overlay reclamation.

#### Maintenance outcome and measurement completeness

A successful `git gc --prune=now` exit proves that Git completed the requested maintenance command. It does not prove exact bytes reclaimed, garbage entries removed, or final pack count unless those values were actually observed before the same whole-operation deadline expired.

Per-repository maintenance rows must expose, or be semantically equivalent to:

```text
maintenance_attempted: bool
maintenance_status: skipped | success | failed | timed-out | budget-exhausted
before_measurement_complete: bool
after_measurement_complete: bool
bytes_before: int | null
bytes_after: int | null
bytes_reclaimed: int | null
garbage_entries_before: int | null
garbage_entries_after: int | null
garbage_entries_removed: int | null
packs_before: int | null
packs_after: int | null
```

Exact field names may follow existing style, but these semantics are normative:

1. every filesystem-size walk and every pre/post `git count-objects -v` observation consumes the original whole-operation maintenance deadline;
2. `maintenance_status: success` may be reported from GC exit status even when the post-maintenance measurement is incomplete;
3. `bytes_reclaimed` is non-null only when exact before and after filesystem measurements completed;
4. `garbage_entries_removed` and pack deltas are non-null only when both relevant Git-status observations completed;
5. missing post-observation due to exhausted budget yields null/incomplete metrics, never zero or an inferred healthy state;
6. an observed negative byte delta must not be clamped to zero: report the actual signed delta, or exact before/after values from which it is derived;
7. aggregate reclaimed/debt metrics are exact only when every contributing measurement is complete; otherwise their aggregate is null with explicit incomplete state instead of a partial sum;
8. logical snapshot/overlay LRU results remain independent and are still returned when repository-maintenance measurement is incomplete.

Final implementation review must distinguish independently whether maintenance was attempted/completed, whether before/after observations completed, and what exact change was measured. No result field may infer measurement completeness or a delta merely from successful maintenance execution.

## Repository-use lock protocol

Generalize `_repository_lock()` to support shared/exclusive modes while retaining the same stable pathname and finite timeout:

- clone/fetch/source selection: exclusive;
- maintenance: exclusive;
- persistent `git show` operations that may lazy-fetch promisor blobs: shared;
- status `count-objects`: shared, bounded by the status deadline;
- pure in-memory/path logic: no lock;
- disposable export repositories: outside the persistent lock domain.

Shared `git show` sessions may remain concurrent. Maintenance must never overlap such a session or source-selection fetch.

### Generator lifetime

`_git_show_lines()` is a generator. Its shared repository lock remains held for the complete subprocess/iteration lifetime and releases on normal completion, error, generator close, and exception.

`tf_header_metadata()` likewise holds the shared repository-use lock for the complete `git show` subprocess lifetime.

Do not introduce a second maintenance-only lock pathname: selection, lazy blob acquisition, status inspection, and maintenance coordinate through the same repository lock domain.

## Git status parsing

Add one deterministic parser for `git count-objects -v`. Required numeric fields:

- `count`
- `size`
- `in-pack`
- `packs`
- `size-pack`
- `prune-packable`
- `garbage`
- `size-garbage`

Without `-H`, Git reports size fields in KiB; convert explicitly to bytes. Unknown extra keys may be ignored. Missing, duplicate, negative, or malformed required numeric fields make that repository inspection `error`; they never silently become zero.

Filesystem repository bytes come from the recursive filesystem-size primitive, with deadline checks, not by summing Git object statistics.

## Documentation

Extend the cache lifecycle reference and user guide to state:

- `repositories/` are internal metadata/promisor stores;
- their non-checkout `git status` is not source-snapshot integrity evidence;
- served source bytes live under immutable revision snapshots;
- `corpus_cache_status` exposes repository storage/garbage/pack health under a bounded best-effort deadline and reports incomplete measurements honestly;
- aggregate repository byte metrics and aggregate Git pack/garbage metrics each carry independent completeness state and are null when incomplete;
- `prune_corpus_cache` is the explicit bounded maintenance trigger with one whole-operation budget;
- successful maintenance execution and complete before/after measurement are reported independently;
- ordinary prepare/load do not run full Git maintenance.

## TDD implementation gates

### RED 1 — repository status and parser

Before production code, add tests requiring:

1. `git count-objects -v` parsing with KiB→byte conversion;
2. duplicate/missing/malformed/negative required fields fail closed;
3. cache status reports repository bytes separately from logical `cache_bytes`;
4. planted Git garbage appears in status;
5. a busy repository produces bounded `busy: true`;
6. many busy repositories cannot multiply the wait ceiling;
7. a deliberately slow `count-objects` process is terminated by the remaining global status budget;
8. a deliberately slow/large filesystem walk consumes the same status budget and yields `size_bytes: null`, `size_complete: false` rather than a partial exact-looking value;
9. an incomplete repository-size scan makes the aggregate repository/whole-cache byte totals explicitly incomplete/null;
10. one busy/error/budget-exhausted repository makes aggregate pack/garbage metrics explicitly incomplete/null instead of summing only successful rows;
11. successful row-level pack/garbage metrics remain visible even when the aggregate is incomplete;
12. when every repository count-objects inspection succeeds, aggregate pack/garbage metrics equal the exact sum and `repository_git_metrics_complete` is true.

Expected initial failure: no repository-maintenance status surface exists.

### GREEN 1

Implement only status/parser/deadline-aware measurement. No `git gc` yet. Run focused tests plus Foundation.

### RED 2 — safe lock domain

Before maintenance implementation, prove:

1. a long-running/lazily-fetching `git show` holds a shared repository-use lock;
2. exclusive maintenance cannot enter during that session;
3. existing exclusive source selection still blocks maintenance;
4. generator close/error releases the shared lock;
5. normal metadata reads remain concurrent where supported by the portalocker contract;
6. status inspection cannot overlap exclusive repository mutation.

Expected initial failure: persistent `git show` is outside the repository lock domain.

### GREEN 2

Generalize the lock and wrap persistent blob-show/status paths. No maintenance yet. Run Foundation plus Linux/macOS/Windows cache lifecycle lanes.

### RED 3 — explicit maintenance

Before adding GC, require:

1. planted Git-recognized `tmp_pack_*`/garbage triggers maintenance and is removed;
2. a healthy repository below threshold skips explicit GC;
3. a real fragmented multi-pack fixture above threshold materially consolidates after maintenance without assuming all promisor/non-promisor packs become one;
4. GC timeout is reported and logical LRU still runs;
5. nonzero GC failure is reported and ordinary corpus usability remains intact;
6. maintenance runs under the exclusive repository-use lock;
7. repeated prune is idempotent after debt clears;
8. before/after repository bytes/debt are truthful;
9. many slow/busy repositories share one total maintenance deadline and later repositories become budget-skipped while logical LRU still executes;
10. slow pre/post `count-objects` calls consume that same global maintenance deadline rather than escaping it;
11. successful GC with the global budget exhausted before post-status reports success plus incomplete post-measurement and null delta metrics;
12. successful GC with post `count-objects` available but the post filesystem walk incomplete may report exact Git debt deltas while byte reclamation remains null/incomplete;
13. failed or timed-out GC does not synthesize post-success zero deltas;
14. aggregate repository reclamation is null/incomplete when any attempted row lacks the needed before/after measurements;
15. a measured post-GC repository larger than before is represented truthfully rather than clamped to zero;
16. all additional post-maintenance observations obey the same original whole-operation deadline and cannot extend prune latency after GC.

### GREEN 3

Implement trigger-driven `git gc --prune=now` under both per-process ceiling and global deadline.

### RED/GREEN 4 — docs/public projection

If service/MCP serialization requires explicit changes, write the contract test first. Require docs to publish metadata-only, bounded status/prune semantics and reject `git status` as snapshot-health evidence.

## Full test gate

Before final review:

- focused repository-maintenance tests;
- complete Foundation unit suite;
- Context-Fabric cache lifecycle on Ubuntu, macOS, and Windows;
- representative Context-Fabric load smoke;
- source audit / collection-index generation if touched lock paths are used there;
- exact-head runs only.

## Independent adversarial review checklist

Challenge the frozen final diff for:

1. any `git gc --prune=now` overlap with persistent-repo object writers;
2. generator-close/error lock release;
3. Windows shared/exclusive portalocker behavior;
4. per-repository timeouts multiplying beyond a global deadline;
5. count-object or filesystem-size work escaping that deadline;
6. maintenance failure/budget exhaustion suppressing logical LRU results;
7. repository bytes being double-counted or silently redefining quota semantics;
8. malformed Git status becoming false healthy state;
9. partial successful rows becoming false-exact aggregate pack/garbage totals;
10. successful maintenance execution being mistaken for complete post-maintenance measurement;
11. partial before/after measurements becoming inferred zero or false-exact delta aggregates;
12. pack tests that mock strings or assume one final pack rather than exercising real Git behavior;
13. upstream scholarly semantics or a bare-repository migration slipping into scope.

Every blocker gets a focused regression RED first, the minimal fix, exact-head GREEN, and a fresh independent review.

## Explicitly out of scope

- bare-repository migration;
- changing snapshot/overlay soft-limit semantics;
- automatic full Git maintenance on startup/prepare/load;
- upstream Git server maintenance;
- changing corpus data, Context-Fabric compilation, or Text-Fabric semantics.
