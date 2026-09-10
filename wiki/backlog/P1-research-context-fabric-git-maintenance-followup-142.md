# Research: Context-Fabric Git maintenance post-merge timeout gaps (#142)

## Scope

Follow-up to merged #45 / #110. This research is limited to Agora's local persistent Git metadata maintenance path. It does not change Text-Fabric data, source selection semantics, snapshot/overlay quotas, or upstream repositories.

## Current implementation inspected

Merged `main` at `9973902324f44eaeea6bd79c91cbd45a88b4519d` adds `_repository_maintenance()` in `agora_context_fabric.gitstore.GitStore` and calls it from `prune()` before the existing logical snapshot/overlay LRU prune.

The authoritative #45 design states that repository-maintenance lock acquisition must be bounded by the smaller of the caller lock policy and the remaining global maintenance budget. The merged implementation calls `_repository_lock(..., timeout=remaining)` and `_repository_maintenance()` receives no caller timeout, so `prune(timeout=...)` is ignored during that maintenance lock wait.

The same design requires the one global maintenance budget to remain truthful across all prescribed pre/post observations. In the merged implementation, a healthy repository is marked `maintenance_status: skipped` after the pre-maintenance Git metrics show no garbage/fragmentation. If the preceding filesystem-size measurement consumes the deadline and returns incomplete, no branch records `budget_exhausted = True` before that healthy skip. The aggregate can therefore claim `repository_maintenance_budget_exhausted: false` after the deadline was actually consumed.

## Interpretation

These are two independent bookkeeping/latency-policy defects:

1. `prune(timeout=...)` remains a lock-wait policy, not a total maintenance deadline. The fix should only bound each repository lock acquisition with `min(caller_timeout, remaining_global_budget)`; the existing 30-second global maintenance budget and 15-second per-GC ceiling continue to govern Git work.
2. A healthy repository still legitimately skips GC. Deadline exhaustion during its required pre-maintenance size observation must nevertheless set the aggregate maintenance-budget exhaustion flag. It must not synthesize a post-maintenance observation or change the row to a failed GC state.

## Non-goals

- no new maintenance trigger;
- no automatic maintenance during load/prepare/startup;
- no change to logical cache LRU or quota semantics;
- no new Git commands;
- no broad refactor of the repository-use lock domain.

## Required evidence

Tests-first regressions must demonstrate both defects on merged `main`, followed by the smallest correction and exact-head Foundation, cross-platform Context-Fabric cache lifecycle, and representative load smoke.