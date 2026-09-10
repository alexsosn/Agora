# Design: Context-Fabric Git maintenance post-merge timeout fixes (#142)

Research: [`P1-research-context-fabric-git-maintenance-followup-142.md`](P1-research-context-fabric-git-maintenance-followup-142.md).

## Contract

Keep the merged #45 maintenance architecture intact and change only two policy edges.

### Caller lock timeout

`GitStore.prune(..., timeout=...)` passes its existing caller lock-wait policy into `_repository_maintenance()`.

For each repository, exclusive maintenance lock acquisition uses:

```text
min(caller_timeout, remaining_global_maintenance_budget)
```

The caller timeout is not reused as a GC/subprocess deadline. Existing `DEFAULT_GIT_MAINTENANCE_BUDGET_SECONDS` and `DEFAULT_GIT_MAINTENANCE_TIMEOUT_SECONDS` continue to bound the maintenance phase and `git gc` work respectively.

### Healthy repository after exhausted pre-measurement

After the pre-maintenance recursive size observation, if the observation is incomplete because the monotonic global deadline has been reached, set aggregate maintenance budget exhaustion true.

If Git metrics show no maintenance trigger, the row remains:

```text
maintenance_attempted: false
maintenance_status: skipped
```

No GC is run and no synthetic post-observation/delta is created.

## TDD gates

### RED

Before production code, add focused tests requiring:

1. a short `prune(timeout=...)` value is propagated as the upper bound for repository-maintenance lock acquisition;
2. a healthy repository whose pre-maintenance size walk consumes the global maintenance deadline reports `repository_maintenance_budget_exhausted: true` while still skipping GC.

Expected initial failure: merged #110 uses the full remaining global budget for repository lock acquisition and does not mark the healthy/incomplete-size path as budget exhausted.

### GREEN

Minimal production change only:

- `_repository_maintenance()` accepts the caller lock timeout;
- lock wait uses `min(caller_timeout, remaining)`;
- `prune()` forwards its existing timeout;
- after an incomplete pre-size observation, reaching the deadline marks the global budget exhausted before the healthy-skip branch.

No schema, MCP surface, Git command, trigger threshold, quota, or source-resolution change.

## Verification

- focused #142 regressions;
- existing #45 status/lock/maintenance tests;
- complete Foundation suite;
- Context-Fabric cache lifecycle on Linux/macOS/Windows;
- representative Context-Fabric load smoke;
- fresh exact-head adversarial review before merge.
