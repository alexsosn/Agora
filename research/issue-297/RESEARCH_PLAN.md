# Issue #297 — cancel superseded collection-index CI runs

## Research (2026-11-11)
- Workflow `.github/workflows/context-fabric-collection-index-generation.yml` has no concurrency group even though `foundation.yml` already uses stable PR-number-scoped cancellation.
- Real workflow runs for consecutive #295 heads (43102520477, 43102885087, 43102936299) overlap in the network-heavy `generate (greek_literature)` step.
- The issue is distinct from #294's data-impact classification and is independent of resource/collection semantics.

## Plan and TDD gates
1. RED: add a source-checked CI workflow contract: `pull_request` runs of the **same PR** share one group with `cancel-in-progress`, unrelated PRs do not, and manual dispatches are unique by run ID/attempt and do not cancel. Avoid branch-wide grouping, and preserve matrix names and scope behavior.
2. GREEN: copy the already established expression pattern from Foundation into collection-index workflow as a minimal `concurrency` block.
3. Focused tests on exact branch content, plus full workflow CI for YAML changes, then empirical overlapping-head test using a disposable PR if necessary.
4. Logically independent adversarial review on frozen head, attention to cross-PR cancellation, manual dispatch cancellation, and whether cancelled superseded checks interfere with merge.

## Integration
Base on #295 branch initially to avoid overlapping direct edits on main. Retarget to main only after #295 is merged. Do not merge #297 first, and do not claim cost savings before actual cancelled-run evidence.
