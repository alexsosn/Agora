# Design review amendment: truthful post-maintenance accounting (#45)

## Independent review finding

The parent design correctly gives the whole Git-maintenance phase one 30-second deadline and bounds pre/post `git count-objects` calls by the remaining time. One result-shape ambiguity remains: `git gc --prune=now` can complete successfully near the deadline while there is insufficient time to perform a trustworthy post-GC status/filesystem measurement.

A successful GC process exit proves that Git completed the requested maintenance command. It does **not** prove exact bytes reclaimed, garbage entries removed, or final pack count if those values were not observed afterwards.

The implementation must therefore separate **maintenance outcome** from **measurement completeness**.

## Required result semantics

Per-repository maintenance rows should expose, or be semantically equivalent to:

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

Exact field names may follow existing style, but the semantics are normative.

Rules:

1. every filesystem-size walk and every pre/post `git count-objects -v` observation consumes the same whole-operation maintenance deadline;
2. `maintenance_status: success` may be reported from the GC exit status even when `after_measurement_complete` is false;
3. `bytes_reclaimed` is non-null only when both exact before and exact after filesystem byte measurements completed;
4. `garbage_entries_removed` and before/after pack deltas are non-null only when both relevant Git-status observations completed;
5. a missing post-observation due to exhausted budget yields null/incomplete metrics, never zero and never an inferred healthy state;
6. do not clamp a negative observed byte delta to zero: if another permitted Git behavior or filesystem effect makes the repository larger after successful maintenance, report the actual signed delta or use explicit before/after fields and let callers derive it consistently;
7. aggregate reclaimed/debt metrics are exact only when every contributing measurement is complete; otherwise expose aggregate completeness=false/null rather than summing a misleading subset;
8. logical snapshot/overlay LRU results remain independent and must still be returned even when repository-maintenance measurement is incomplete.

## RED additions

Before implementation, tests must freeze at least:

- successful GC with global budget exhausted before post-status -> success + `after_measurement_complete=false` + null delta metrics;
- successful GC with post `count-objects` available but post filesystem size walk timing out -> Git debt deltas may be exact while byte reclamation remains null/incomplete;
- failed/timed-out GC does not synthesize post-success zero deltas;
- aggregate repository reclamation becomes incomplete/null when any attempted row lacks the needed before/after measurements;
- a measured post-GC repository larger than before is represented truthfully rather than clamped to zero;
- all additional observations obey the same original whole-operation deadline and cannot extend prune latency after GC.

## Review consequence

Final implementation review must distinguish three questions independently:

1. Was maintenance attempted/completed?
2. Were before/after observations completed?
3. What exact change was measured?

No result field may answer (2) or (3) by inference from (1).
