# Issue #217 — Context-Fabric manual/scheduled run isolation

## Research (source audit)

The current `.github/workflows/context-fabric-audit.yml` and `.github/workflows/context-fabric-load-smoke.yml` use `group: <workflow>-${{ github.event.pull_request.number || github.ref }}` with unconditional `cancel-in-progress: true`. On push, manual `workflow_dispatch`, and Monday schedule, the fallback is the branch ref (usually main): overlapping, independently requested executions cancel one another.

Inspected **real jobs and effects** before changing cancellation semantics:

- Context-Fabric source audit: read-only upstream inspection; local `$RUNNER_TEMP` audit cache; writes JSON evidence in isolated workspace and uploads per-run immutable Actions artifacts. No repository write permissions (`contents: read`) or external mutation.
- Representative load smoke: read-only corpus fetches, runner-local cold-compile/load/unload/cache pruning; `actions/cache@v4` keyed by corpus and metadata hash. Cache artifact upload semantics are immutable, and parallel writers may race to populate *equivalent* caches, not mutate an existing shared cache. Per-run report artifacts, `contents: read`.
- Both workflows trigger on PR paths, main push paths, `schedule`, and `workflow_dispatch`; preserve all events, filters, crons, permissions and jobs unchanged.

## Plan and RED acceptance

1. Change **only top-level concurrency** for these two read-only workflow files.
2. Use a workflow-qualified `pr-<PR-number>` group and `cancel-in-progress: github.event_name == 'pull_request'`, so new PR heads supersede old heads of the **same PR+workflow**.
3. Use `run-<run_id>-<run_attempt>` for push, manual and schedule so unrelated executions neither cancel nor coalesce while pending. Do not group by `github.ref`.
4. Preserve a RED unit contract loading actual workflow YAML; assert event filters and crons continue to exist, exact expression, main/schedule/manual run-ID isolation and read-only permissions.
5. GREEN update to both YAMLs. Test the PR exact head in Foundation, audit and representative load smoke. Distinct PR pushes should demonstrate superseded-head cancellation; public GH workflow dispatch for independent manual runs is unnecessary without explicit authorization, so document that particular behavior as expression-verified rather than live-verified.
6. Independent logically separate skeptical source review checking no surprise repository/external write effects or permission changes; merge only if full CI passes.

## Boundaries

No changes to release-update jobs, workflows with upload/write cleanup unknown, cache format or upstream corpus pin. Deliberately **does not** force-cancel older main/schedule runs; if congestion results, address runner resource policies separately rather than discarding requested runs.
