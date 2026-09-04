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
- [`architecture/ref-context-fabric-snapshot-cache.md`](architecture/ref-context-fabric-snapshot-cache.md) — immutable revision-addressed corpus and feature-module materialization, exact-byte export, and retention boundary.
- [`architecture/ref-local-materialization.md`](architecture/ref-local-materialization.md) — experimental source → trusted materializer → transactional local artifact boundary, sandbox model, and reproducibility provenance.
- [`architecture/ref-implementation-details.md`](architecture/ref-implementation-details.md) — marketplace generation, integration plumbing, verification details, scholarly skills, repository layout, and phase status moved out of the user-facing README.

When older planning/research language is broader than the plugin boundary, `ref-plugin-boundary.md` controls. In particular, a backlog item or review finding about a third-party plugin does not authorize Agora to fix the plugin's own semantics.

### Releases

- [`releases/v0.1-scope-frozen.md`](releases/v0.1-scope-frozen.md) — fixed v0.1 plugin/resource scope.
- [`releases/v0.1-plan-active.md`](releases/v0.1-plan-active.md) — current implementation plan and phase status.

### Guides

- [`guides/installation.md`](guides/installation.md) — Claude Code and ChatGPT/Codex installation flows.

### Backlog

- [`backlog/P0-research-ecosystem-expansion.md`](backlog/P0-research-ecosystem-expansion.md) — cross-domain post-v0.1 candidate survey.
- [`backlog/P0-research-egyptology.md`](backlog/P0-research-egyptology.md) — Egyptology-specific integration research.
- [`backlog/P0-research-germanic-philology.md`](backlog/P0-research-germanic-philology.md) — Old Norse/Icelandic/Gothic integration research.
- [`backlog/P1-design-local-materialization-composition.md`](backlog/P1-design-local-materialization-composition.md) — bind the exercised materialization primitive to installation approval, resources, artifact caching, and consumers.

The three P0 research files are research backlogs, not promises that every candidate inside them is P0 implementation work. Candidate-level priorities remain documented inside each survey until the backlog is normalized into structured candidate records.

### Reviews

- [`reviews/2026-08-29-review-architecture-code.md`](reviews/2026-08-29-review-architecture-code.md) — first independent architecture/code review, against pre-#4 main.
- [`reviews/2026-08-29-review-pr1-pr4.md`](reviews/2026-08-29-review-pr1-pr4.md) — independent critical review of the two latest merged PRs (#1 and #4), including new cache/provenance findings.

## Current P0 engineering findings

The latest review identifies these as the immediate engineering priorities:

1. make Context-Fabric corpus materialization immutable and SHA-addressed so the reported source revision identifies the exact bytes loaded;
2. carry a collection snapshot/revision through `list → prepare → load`;
3. wire representative BHSA/CUC/Iliad load checks into CI and verify actual corpus features/content;
4. reconcile user-facing README verification claims with canonical per-client registry status;
5. require CI/branch protection before merge;
6. make verification evidence executable/traceable rather than descriptive strings.

These priorities remain subject to the plugin ownership boundary. Work on Agora-owned acquisition, provenance, registry, launch, and verification plumbing is in scope; fixing third-party algorithms or adding missing upstream capabilities is not.

See [`reviews/2026-08-29-review-pr1-pr4.md`](reviews/2026-08-29-review-pr1-pr4.md) for evidence and lower-priority findings.

## Maintenance rule

Do not add new Markdown files directly under `wiki/` except this index. Put new material in the appropriate category and use the convention above. If a document becomes active tracked work, encode its priority/state in the filename; if it is a durable reference, do not give it a fake priority.
