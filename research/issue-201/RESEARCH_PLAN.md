# Issue #201 — Superseded PR workflow cancellation

## Research (2026-10-10)

Observed while closing #135 parent-composition gates: multiple outdated RED/GREEN pull-request commits each consume the complete Foundation matrix, materializer installation smokes, sandbox E2E, and pinned Coptic sparse-Git acquisition, delaying the exact-head merge gate. Workflow configurations were audited against `.github/workflows/` on main.

| Workflow | PR triggered | External/shared effects | Decision |
| --- | --- | --- | --- |
| `foundation.yml` | all PRs | local tests, runner-local temp/cache only | PR-scoped cancellation |
| `materialization-sandbox.yml` | paths | local OS sandbox tests, read-only upstream fetches, no published external state | PR-scoped cancellation |
| `materializer-install.yml` | paths | downloads/install into runner temp; registered smoke reads source; no GitHub writes | PR-scoped cancellation |
| `materialization-sparse-coptic.yml` | paths | read-only pinned TT fetch and runner-local checkout, no shared mutation | PR-scoped cancellation |
| `context-fabric-load-smoke.yml` | paths | already declares concurrency and cancellation | unchanged (separate investigation for schedule semantics) |
| `context-fabric-audit.yml` | paths | already declares concurrency and cancellation | unchanged |
| `materializer-release-updates.yml` | schedule/manual | opens/updates GitHub PRs; already serialized and `cancel-in-progress: false` | **never cancel** |
| `external-mcp-smoke.yml` | push/schedule/manual | touches live external MCP providers; PR event absent | unchanged |
| `context-fabric-collection-index-generation.yml` | paths/manual | uploads generated artifacts; cancellation/cleanup semantics not yet proven | defer pending explicit evidence |
| `materializer-execution-identity-research.yml` | paths | platform inventory; duration bounded and low frequency | defer |

## Plan and contracts

1. Preserve `on:` filters and all job definitions; change only top-level `concurrency` in the four read-only/local-only workflows.
2. Use exact PR number in a **workflow-qualified** group for `pull_request`: all new pushes to a PR cancel its predecessor *for the same workflow*, but do not collide with other PRs/workflows.
3. For `push`, `workflow_dispatch`, `schedule` or reruns of non-PR events, include **run ID and attempt** in the group: no cancellation *and no queued-run coalescing* for unrelated main/manual/scheduled runs.
4. Apply `cancel-in-progress` only to `github.event_name == 'pull_request'`, not to main, manual or scheduled runs.
5. Commit RED workflow contract tests; then GREEN workflow configurations. Require CI on final head, plus logically independent skeptical review comparing actual YAML, scheduler expressions, retained event filters and external effects.
6. Verify the **two-push PR scenario** by observing GitHub Actions jobs from successive commits: older PR-head jobs must cancel, newest head must remain running/completing. Avoid re-running a failed workflow against a stale commit; that can intentionally cancel latest-head PR jobs.
7. Mark issue done only with concrete scheduler evidence; if GitHub queueing prevents observation, leave PR/issue open rather than claiming proof.

## Not in scope

No workflow's commands, runner permissions, event triggers, cache paths or release automation are changed. No cancellation for job families that publish artifacts, mutate external state or have unknown cleanup behavior without further evidence.
