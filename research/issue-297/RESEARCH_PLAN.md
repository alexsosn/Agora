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

## Adversarial CI finding and preserved RED (2026-11-15)
- The exact-head Foundation run 43105850639 executed 1,136 tests and found a single failure in existing `tests/test_pr_workflow_concurrency.py` (issue #201). Its legacy exclusion tuple still names the collection-index workflow as intentionally unconstrained, although index generation is a **read-only** Git metadata / local index verification and CI artifact upload workflow.
- Do **not** simply ignore the failing test: keep the explicit #201 guard for `materializer-release-updates.yml` (noncancelling) and `external-mcp-smoke.yml` (no concurrency). Update only the now-obsolete exclusion of the collection index, and retain the new #297 positive test requiring the exact Foundation PR-only grouping.
- Frozen RED evidence: Foundation job 130808922451 / run 43105850639, failure solely `test_live_external_mutation_and_release_automation_are_unmodified` for this filename. GREEN commit `e80331ce` narrows legacy exclusion. Full exact-head CI still required on retargeted main before merge.
