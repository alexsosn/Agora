# Agora Wiki

This directory is the durable project knowledge base. It is intentionally organized by document role rather than by date of creation.

## Directory map

| Directory | Purpose | Naming convention |
|---|---|---|
| `architecture/` | Stable architecture and design references | `ref-<topic>.md` |
| `releases/` | Release scope and active implementation plans | `v<version>-<document>-<state>.md` |
| `guides/` | End-user and contributor-facing procedures | `<topic>.md` |
| `backlog/` | Prioritized research/integration work | `P0|P1|P2-<state>-<topic>.md` |
| `reviews/` | Immutable independent reviews and audits | `YYYY-MM-DD-review-<topic>.md` |

## Priority and state convention

Backlog filenames are sortable work identifiers:

- `P0` — address/investigate next; blocks trustworthy progress or is the next expansion batch.
- `P1` — important follow-up; should be scheduled after current P0 work.
- `P2` — useful but non-urgent, experimental, narrow, or dependent on earlier work.

Allowed backlog state words used in filenames:

- `research` — evidence gathering / feasibility work;
- `design` — architectural decision needed;
- `implement` — ready for implementation;
- `verify` — implementation exists but evidence is incomplete;
- `blocked` — depends on an external decision/resource.

When priority or state changes, rename the backlog file in the same PR that records the decision. Reviews are never renamed to pretend history changed; later reviews supersede earlier ones explicitly.

Release documents encode lifecycle instead of P-level priority:

- `frozen` — release contract/scope; changes require an explicit scope decision;
- `active` — current implementation plan;
- `complete` — closed historical release plan.

## Current documents

### Architecture

- [`architecture/ref-plugin-boundary.md`](architecture/ref-plugin-boundary.md) — **normative ownership boundary** for a thin marketplace: what Agora may implement, what must remain upstream, permitted adapters, skills, tests, and review rules.
- [`architecture/ref-marketplace-architecture.md`](architecture/ref-marketplace-architecture.md) — clean-slate architecture, provider/resource model, verification model, and design rationale.
- [`architecture/ref-context-fabric-collections.md`](architecture/ref-context-fabric-collections.md) — member-aware handling of large Text-Fabric collection repositories.
- [`architecture/ref-context-fabric-snapshot-cache.md`](architecture/ref-context-fabric-snapshot-cache.md) — revision-addressed corpus/feature-module source materialization, exact-byte export, and source-provenance boundary.
- [`architecture/ref-context-fabric-cache-lifecycle.md`](architecture/ref-context-fabric-cache-lifecycle.md) — cross-process repository locking, cache-object leases, overlay-aware eviction, LRU/status/remove UX, and load/reload lifecycle.
- [`architecture/ref-local-materialization.md`](architecture/ref-local-materialization.md) — experimental source → trusted materializer → transactional local artifact boundary, sandbox model, and reproducibility provenance.
- [`architecture/ref-implementation-details.md`](architecture/ref-implementation-details.md) — marketplace generation, integration plumbing, verification details, scholarly skills, repository layout, and phase status moved out of the user-facing README.

When older planning/research language is broader than the plugin boundary, `ref-plugin-boundary.md` controls. In particular, a backlog item or review finding about a third-party plugin does not authorize Agora to fix the plugin's own semantics.

### Releases

- [`releases/v0.1-scope-frozen.md`](releases/v0.1-scope-frozen.md) — fixed v0.1 plugin/resource scope.
- [`releases/v0.1-plan-active.md`](releases/v0.1-plan-active.md) — current implementation plan and phase status.

### Guides

- [`guides/installation.md`](guides/installation.md) — Claude Code and ChatGPT/Codex installation flows.
- [`guides/context-fabric-cache.md`](guides/context-fabric-cache.md) — Context-Fabric managed cache, cold-compilation guardrails, status, cancellation, and cleanup behavior.

### Backlog

- [`backlog/P0-research-ecosystem-expansion.md`](backlog/P0-research-ecosystem-expansion.md) — cross-domain post-v0.1 candidate survey.
- [`backlog/P0-research-egyptology.md`](backlog/P0-research-egyptology.md) — Egyptology-specific integration research.
- [`backlog/P0-research-germanic-philology.md`](backlog/P0-research-germanic-philology.md) — Old Norse/Icelandic/Gothic integration research.
- [`backlog/P1-design-local-materialization-composition.md`](backlog/P1-design-local-materialization-composition.md) — bind the exercised materialization primitive to installation approval, resources, artifact caching, and consumers.
- [`backlog/P1-research-corpus-licensing-audit.md`](backlog/P1-research-corpus-licensing-audit.md) — completed evidence-first audit of corpus data licences, redistribution terms, component/member-specific restrictions, and provenance for #17.
- [`backlog/P1-design-corpus-licensing-metadata.md`](backlog/P1-design-corpus-licensing-metadata.md) — structured licence-evidence model and TDD implementation gate derived from the #17 audit.
- [`backlog/P1-design-context-fabric-load-safety.md`](backlog/P1-design-context-fabric-load-safety.md) — research-backed process-containment, disk-budget, cancellation, and retry-safety design for #37.
- [`backlog/P1-design-context-fabric-offline-resolution.md`](backlog/P1-design-context-fabric-offline-resolution.md) — cached/offline source selection, freshness provenance, cache-miss behavior, and TDD gate for #44.

The three P0 research files are research backlogs, not promises that every candidate inside them is P0 implementation work. Candidate-level priorities remain documented inside each survey until the backlog is normalized into structured candidate records.

### Reviews

- [`reviews/2026-08-29-review-architecture-code.md`](reviews/2026-08-29-review-architecture-code.md) — first independent architecture/code review, against pre-#4 main.
- [`reviews/2026-08-29-review-pr1-pr4.md`](reviews/2026-08-29-review-pr1-pr4.md) — independent critical review of the two latest merged PRs (#1 and #4), including the findings that drove later cache/provenance work.

## Live work tracking

Dated reviews are historical evidence, not a live priority queue. Several engineering findings in the August reviews—immutable Context-Fabric snapshots, collection-revision propagation, representative corpus loads, verification-claim reconciliation, and executable verification evidence—have since been implemented.

Use current GitHub issues together with `backlog/` documents for active work. Repository branch protection remains a separate open governance/administration task (#9); it should not make the already-completed engineering findings look current again.

The plugin ownership boundary continues to apply to every live ticket: Agora-owned acquisition, provenance, registry, launch, verification, installation, and marketplace plumbing are in scope; third-party domain algorithms and missing scholarly capabilities remain upstream-owned unless an explicit architecture decision says otherwise.

Historical evidence and lower-priority findings remain available in [`reviews/2026-08-29-review-pr1-pr4.md`](reviews/2026-08-29-review-pr1-pr4.md) and later dated reviews.

## Maintenance rule

Do not add new Markdown files directly under `wiki/` except this index. Put new material in the appropriate category and use the convention above. If a document becomes active tracked work, encode its priority/state in the filename; if it is a durable reference, do not give it a fake priority.
