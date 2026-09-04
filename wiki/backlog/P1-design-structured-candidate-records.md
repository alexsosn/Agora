# Design: structured candidate research records

## Goal

Implement issue #15 without turning research candidates into supported marketplace entries or duplicating the canonical registry. The design introduces a validated research namespace, deterministic query tooling, and a promotion boundary.

## Files and responsibilities

### `research/candidates.yaml`

Machine-readable candidate records. Each record has a stable `id` and contains:

- `name`, `candidate_kind`, `priority`;
- `sources` linking to narrative backlog sections and upstreams;
- `assessment` with independent dimensions for scholarly value, technical readiness, provenance authority, legal clarity, maintenance health, overlap, implementation effort, and strategic importance;
- `legal` separating software license, data/content license, redistribution, authentication, and service terms;
- `annotation_maturity`;
- `taxonomy` mapping canonical capabilities/disciplines/resource kinds separately from free-form research tags;
- `evidence` snapshots with dates, revision/release, license sources, observed tools, install/connect outcome, live-smoke outcome, and provenance/data links;
- `promotion` metadata that never implies release support by default.

### `research/schema/candidates.schema.json`

Draft 2020-12 JSON Schema. It validates field presence, stable-ID shape, enum values, date/URI formats, evidence result shapes, and uniqueness-compatible record structure.

Cross-record uniqueness and canonical-vocabulary references remain Python checks because they depend on `registry/vocabularies.yaml`.

### `research/README.md`

Documents:

- research vs release boundary;
- field semantics;
- taxonomy mapping;
- evidence update policy;
- promotion workflow and independent verification requirement;
- examples of supported queries.

### `scripts/validate_registry.py`

Extend the existing Foundation metadata gate to validate `research/candidates.yaml`. The command name remains unchanged so there is one authoritative validation path.

Additional checks:

- duplicate candidate IDs;
- canonical taxonomy values must exist in `registry/vocabularies.yaml`;
- each `sources[].notes` path must exist in the repository;
- evidence snapshots are newest-last and cannot duplicate `checked_at` within one candidate;
- `promotion.status=promoted` requires a non-empty target and is not used by the initial migration.

### `scripts/query_candidates.py`

Read-only deterministic query CLI. Initial filters:

- `--priority`;
- `--data-license-status`;
- `--authentication`;
- `--live-smoke`;
- `--technical-readiness`;
- `--annotation-maturity`.

Output is JSON by default so agents and CI can consume it. `--ids-only` emits one stable ID per line for shell use.

### Tests

Add focused unit tests for schema/validator behavior and query semantics. Existing Foundation remains the final integration gate.

## TDD sequence

1. **RED — candidate validation contract**
   - add tests expecting `validate_registry()` to accept a minimal valid research candidate file;
   - assert duplicate candidate IDs fail;
   - assert unknown canonical capability/discipline/resource-kind values fail;
   - assert missing narrative source paths fail.

2. **GREEN — schema and validator integration**
   - add the research schema and extend `validate_registry.py` only enough to satisfy the tests.

3. **RED — query contract**
   - add tests for `P0 + unknown data license` and `live-smoke=success` filters;
   - verify combined filters are conjunctive and `ids-only` is stable/sorted.

4. **GREEN — query CLI**
   - implement a small pure filtering function plus CLI wrapper.

5. **Migration**
   - seed records from ecosystem, Egyptology, and Germanic research;
   - retain original prose unchanged and link every migrated record to its source section;
   - use explicit `unknown` rather than infer unsupported facts.

6. **Test gate**
   - `python scripts/validate_registry.py`;
   - `python scripts/query_candidates.py --priority P0 --data-license-status unknown --ids-only`;
   - `python scripts/query_candidates.py --live-smoke success --ids-only`;
   - `python -m unittest discover -s tests -v`;
   - generated artifact freshness checks already required by Foundation.

7. **PR + independent review loop**
   - open PR only after local/static test expectations are represented in CI;
   - run Foundation on the exact PR head;
   - perform a fresh independent skeptical review against issue #15, `CONTRIBUTING.md`, and repository architecture;
   - if review finds a defect, record changes required, add a regression first where applicable, fix, rerun CI, and perform another fresh review of the new final head;
   - merge only the reviewed green SHA.

## Acceptance-criterion mapping

| Issue #15 criterion | Design coverage |
| --- | --- |
| Stable IDs + documented schema | `research/candidates.yaml`, JSON Schema, README |
| Separate assessment dimensions | `assessment` object |
| Separate software/data/redistribution/service/auth | `legal` object |
| Strategic importance != readiness | independent assessment fields |
| Annotation maturity states | controlled `annotation_maturity` enum |
| Timestamped evidence snapshots | `evidence[]` object |
| Taxonomy mapping | canonical taxonomy fields + `research_tags`, documented in README |
| Mechanical representative queries | query CLI + tests |
| Promotion requires independent verification | README + `promotion` field semantics |
| Existing research migrated/linked without loss | seed records link to unchanged narrative source documents |

## Non-goals

- no candidate is promoted into the marketplace by this ticket;
- no third-party project is installed or repaired as part of this metadata-normalization change;
- no release vocabulary is expanded merely to accommodate research-only terminology;
- no generated prose replacement for the existing backlog is required in the first iteration.
