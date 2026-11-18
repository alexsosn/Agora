# Autonomous development policy — Agora

This document operationalizes [PRODUCT_GOALS.md](../PRODUCT_GOALS.md) for autonomous coding sessions. It supplements, and does not replace, the non-negotiable security, rights, repository, source-integrity and review requirements in [AGENTS.md](../AGENTS.md) and [CONTRIBUTING.md](../CONTRIBUTING.md).

## 1. Begin with the researcher's job

At the start of a cycle, inspect current main, active PRs, recent issue/release states and the real supported client paths. State the highest-impact unmet journey in PRODUCT_GOALS.md and what prevents a researcher from completing it. The backlog is evidence and work coordination, not the objective function.

For the chosen task, identify:
- **Outcome:** the researcher capability gained or observed failure removed.
- **Evidence:** real code, source/registry data, a recent reproducible failure or a documented first-user blocker.
- **Reuse:** the smallest existing mechanism that may solve it, and why a new component is unavoidable if proposed.
- **Acceptance:** the public user path and actual data by which an independent reviewer can verify success.

Do not select a ticket simply because it is easiest, most formally testable or already marked high priority. Check active issue/PR ownership first and avoid duplicate agent implementation branches.

## 2. Prefer the smallest useful slice

Prefer: broken core research paths and misleading output; source/data correctness; plugin discovery/install/search UX; real runtime/release blockers; measured performance/stability defects; user documentation; optional infrastructure.

An observed security, privacy, source-integrity or licence violation may override that order. Don't downgrade real safety requirements as 'overengineering'. Speculative cryptography, certification, protocol design, adapters, generalized registries and licensing machinery require a concrete threat, requirement or reproduced release blocker and a comparison with existing mechanisms.

Agora integrates existing providers upstream-first. If the same scholarly bug exists when a plugin runs without Agora, fix/report upstream and keep Agora's action to truthful capability metadata, version constraints and supported integration glue.

Do not create one issue, PR, CI workflow or validator per plugin endpoint, corpus item, document, page or mapping row. Batch compatible data changes, reuse existing pipelines and keep source-specific regression tests when they prove different semantics.

## 3. Proportional research → plan → TDD → test

Research existing code/behavior and relevant original sources first. Plan the minimal implementation with a bounded scope and stopping condition. For behavioral changes, reproduce the observed failure and write a focused failing test before fixing it where applicable; do not commit permanently failing CI to 'prove RED'. Run directly relevant tests, installed/public-interface smokes and existing release gates according to risk.

For pure docs and metadata, check authoritative links, actual version and client support, generated outputs, links, example commands, and affected contracts. A standalone plan document, extra issue, new workflow or unrelated live matrix is not needed for small documentation updates.

Be explicit when a supposedly completed work item has only a successful internal unit test, rather than a researcher-visible success.

## 4. Independent, adversarial PR review

Every finalized PR receives logically independent failure-seeking review, including if performed in the same agent session/context. Review the final diff against PRODUCT_GOALS.md, the user-facing contract, original registry/source data and public API, without relying on the implementation author's claims. Seek incorrect provenance, silent data loss, stale version claims, unbounded work, unsafe trust changes, regressions, redundant infrastructure and simpler working alternatives.

Fix material findings, rerun relevant gates and re-review changed code at the final head. Do not expand current scope for optional improvements unrelated to the acceptance criterion. Never call a review independent merely because tests were rerun.

## 5. Validate the first user's complete journey

For relevant changes, check the path **question → discover capability → install/open → make first operation → inspect original evidence → cite/recover**. Use real resource or external-provider data where permitted; distinguish a transport smoke from proof of source scholarship. Test actual supported host integration at major milestones and near release, with no hidden developer-only inputs. A generated manifest or Python-only smoke is insufficient evidence of host usability.

Record exact observable results, versions, compatibility limitations, resource costs and clear failure states. Do not claim a public release, plugin support, asset download or host success based only on a merged PR.

## 6. Stop unproductive loops and finish

Focus one active implementation workstream per session. If two consecutive cycles fail to improve the chosen researcher journey or remove a proven blocker, reconsider the approach. Negative results, blocked permissions and upstream incompatibility should trigger honest documentation, a pivot, or a bounded pause—not another general-purpose framework.

When the scoped acceptance passes, complete adversarial review, verify final-head CI, integrate the PR and publish via existing authorized procedures if possible. If only an owner can tag, approve or publish, report the exact handoff without constructing alternative release governance.

At the end, report: **researcher outcome**, **observed evidence**, **PR/CI/review/merge/publish status**, **limitations**, and **single highest-value next action**. If the product already meets the scoped goal and no justified next improvement exists, stop. Closed issues and numerous green tests are not substitutes for an actual research result.
