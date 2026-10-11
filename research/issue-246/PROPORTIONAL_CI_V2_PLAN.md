# #246 research: proportional CI without changing required check identities

2026-10-11 evidence, 15 merged PRs. Source of truth: exact GitHub PR changed-filename lists (#242, #243, #244, #245, #247, #248, #249, #253, #254, #255, #256, #257, #259, #260, #261). Docs generator/guide/test PRs #242-245 and #247 repeatedly launched Foundation's 7-job matrix although they never touched runtime plugins, registries or lockfiles. The current fail-closed `scripts/ci_change_scope.py` recognizes Markdown-only changes, but classifies all five historical docs PRs as `full` because they touched docs generators and assertions. Runtime/trust PRs #249, #253, #254, #256, #257, #259-261 correctly must remain full. Research PR #255 and CI classifier PR #248 are executable/workflow changes and remain full.

Source inspection: `.github/workflows/foundation.yml` has a bare `pull_request` trigger; a single Ubuntu job runs all repo unit tests plus three OS cache-lifecycle jobs and three OS materializer-lock jobs. Docs only still pay heavy execution. `.github/workflows/external-mcp-smoke.yml` currently has only push/schedule/dispatch (no PR trigger): docs compatibility files can trigger the heavy live matrix *after merging to main*, not directly on the PR. Branch-protection endpoint is 403 for this installation; required-status-check contexts cannot be independently audited. Therefore **do not change the job check names or remove workflow triggers**, and do not claim a required-check policy is known.

## Plan, gates, and negative cases

1. RED classification fixtures from the actual 15 PR file lists, including docs generator/test PRs #242-245/#247. Allow only a specifically enumerated set of documentation-only generator scripts/tests, `wiki/guides/**/*.md`, root README/CONTRIBUTING and issue research docs. Every unknown executable, runtime, registry, installer, lockfile, workflow or mixed change stays full; symlinks, file-mode changes, renames, absent/unsafe diff and non-PR dispatch stay full. Do not infer safety from `docs/` or arbitrary `test_*.py` names.
2. Extend `ci_change_scope` to report one of `docs`/`full` (or audited descriptive subcategories) and emit a workflow step output from the **complete NUL-delimited first-parent PR merge diff**. The existing raw-diff parser is fail closed; retain it.
3. Foundation runs one cheap scope job in every PR. Preserve all 7 existing check names and all `main`/release validation. Only docs-selected PRs skip cross-OS cache/lock jobs and use reduced Foundation tests; retain generator freshness `--check` runs, syntax checks, registry verification, documentation/link/first-contact tests.
4. The existing `foundation` job and matrix names must remain discoverable as stable check contexts; skipped jobs should be explicitly reported with reason. If branch protection unexpectedly treats skips as blocking, revert selection or use constant-name success gates rather than weakening protection.
5. Adversarial independent review: verify a mixed PR changes `plugins/context-fabric/src/**` plus `wiki/guides/**` still runs full; changing an MCP manifest, install claim canonical source, registry metadata, source trust policy, Git hooks or unknown path must always run full. Check historical real PR changed-file sets and make sure #262, #260 and #254 remain full.
6. Compare GitHub Action runner-minutes for >=15 historical PRs versus simulated path decisions, separately counting queue time and post-merge `external-mcp-smoke`; report medians/p95 when logs complete. Do not claim realized savings before a real docs PR runs on the new gate.

Initial failure-mode budget: 0 full-runtime false negatives in supplied test fixtures; no changes to source trust, Context-Fabric load, Pseudepigrapha or ORACC runtime workflows.

## Current state

Research only; branch-protection permissions unavailable. Start RED tests before changing policy; no CI workflow or skip semantics have yet been modified by this note.


## Measured historical Foundation wall-time baseline (15 PRs)

GitHub Actions exact reviewed-head successful Foundation workflow `run_started_at` →
`updated_at`, in minutes. This is *wall-clock workflow elapsed time*, **not**
sum of runner billed minutes, and it excludes earlier cancelled/superseded
attempts. Queuing must not be confused with execution.

| PR | Risk classifier candidate | Workflow elapsed (minutes) |
| --- | --- | ---: |
| #242 | docs | 11.0 |
| #243 | docs | 12.2 |
| #244 | docs | 7.2 |
| #245 | docs | 12.4 |
| #247 | docs | 12.0 |
| #248 | full | 14.2 |
| #249 | full | 12.8 |
| #253 | full | 12.1 |
| #254 | full | 16.0 |
| #255 | full | 13.7 |
| #256 | full | 12.9 |
| #257 | full | 6.7 |
| #259 | full | 17.4 |
| #260 | full | 27.7 |
| #261 | full | 12.4 |

Docs baseline median **12.0 minutes**, empirical nearest-rank p95 **12.4**;
full baseline median **13.3 minutes**, empirical nearest-rank p95 **27.7**.
These data show opportunity, **not** realized savings; the actual fast-path
needs a fresh docs-only PR and observed runner start/end times. This API
exposure does not provide per-job `started_at`/`completed_at` in the
connected job view, so aggregate paid runner minutes are unverified.


## Adversarial acceptance finding: GitHub matrix check identities (2026-10-12)

Real successful [#264 Foundation run 38172436189](https://github.com/alexsosn/Agora/actions/runs/38172436189)
ran the full scope and emitted all six original OS-specific check names.
The separately stacked docs-only [#265 Foundation run 38172482376](https://github.com/alexsosn/Agora/actions/runs/38172482376)
correctly printed `Foundation validation scope: docs`, ran generated-guide and
first-contact checks, and skipped the full unit suite, **but a job-level
`if: ... == 'full'` prevented matrix expansion**. GitHub returned only two
generic skipped jobs with literal `(${{ matrix.os }})` in their names.
This was an independent-review blocker: individual OS-specific required status
contexts, if configured, might stay pending even when the workflow is green.

TDD fix: `tests/test_ci_matrix_contexts_246.py` was added as RED before
the workflow change. It requires matrix expansion for both job families and
checks each costly OS step has an exact full-scope guard. The revised workflow
always instantiates the 3x2 matrix jobs, executes a tiny docs-only stub,
and skips checkout, Python/tool setup, dependency installation, and runtime
regressions for docs scope. Full-scope steps and check names stay intact;
new exact-head Foundation and real #265 docs-only acceptance checks are
required before merging. This trades six minimal runner startups for preserved
existing required-status identities. The branch-protection 403 persists; this
is not evidence that any required-check policy was independently read.
