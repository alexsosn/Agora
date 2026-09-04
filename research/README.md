# Candidate research registry

`research/` stores structured investigation records for projects that are **not yet supported Agora marketplace entries**. Canonical release state continues to live under `registry/`.

Candidate records are intentionally allowed to describe blocked, incomplete, unlicensed, superseded, experimental, or merely wanted integrations. A research priority therefore must not be interpreted as implementation readiness or as evidence that an agent-facing integration already exists.

## Files

- `candidates.yaml` — candidate identities, assessments, legal/access evidence, taxonomy mapping, and dated observations.
- `schema/candidates.schema.json` — Draft 2020-12 schema validated by `python scripts/validate_registry.py`.

The original narrative research remains under `wiki/backlog/`. Candidate `sources` point back to those documents and sections so rationale and caveats are preserved instead of flattened into YAML.

## Priority and integration status

`priority` and `integration_status` are deliberately separate dimensions.

- `priority`: `P0`, `P1`, `P2`, or `unranked`. `unranked` is used only when the source research did not assign a P-level.
- `integration_status`: `existing`, `wanted`, `not-applicable`, or `unknown`. `wanted` means the source identifies a useful integration target but no suitable agent-facing integration has been established in the research record.

Thus a source heading such as **P0 wanted integrations** remains `priority: P0` and `integration_status: wanted`; querying P0 candidates does not lose strategically important gaps.

## Assessment dimensions

Each candidate records these independently:

- `scholarly_value` — usefulness for scholarship;
- `technical_readiness` — whether a practical integration path is ready, promising, blocked, or unknown;
- `provenance_authority` — strength/clarity of scholarly or institutional provenance;
- `legal_clarity` — whether licensing/access conditions are clear;
- `maintenance_health` — observed maintenance state;
- `overlap` — redundancy with existing or competing integrations;
- `implementation_effort` — expected engineering effort;
- `strategic_importance` — value of filling the marketplace capability gap.

A P0 candidate can be technically blocked, and a low-effort candidate can remain strategically low priority.

## Legal and access model

Do not collapse legal evidence into one `license` field. Records keep separate:

- software/code license;
- content/data license;
- redistribution rights;
- authentication requirements;
- remote-service terms.

Use `unknown` when the research did not establish a fact. Do not infer redistribution permission from public web access or infer data licensing from a repository's software license. A license marked `known` must name an expression and must have at least one upstream license-source URL in the candidate's evidence snapshots.

## Annotation maturity

`annotation_maturity` is one of:

- `generated` — automatic/generated annotation is the relevant observed layer;
- `manually-reviewed` — editorial/gold/manual review is the relevant observed layer;
- `mixed` — both reviewed and generated layers materially coexist;
- `snapshot-wip` — the observed data are explicitly provisional/snapshot/WIP;
- `unknown` — research has not established the state;
- `not-applicable` — the candidate is not meaningfully an annotation-bearing data resource.

This describes evidence already present upstream; it does not make Agora responsible for upstream scholarly semantics.

## Taxonomy mapping

Candidate taxonomy is split between canonical release dimensions and research-only tags:

- `taxonomy.capabilities` must use values from `registry/vocabularies.yaml:capabilities`;
- `taxonomy.disciplines` must use values from `registry/vocabularies.yaml:disciplines`;
- `taxonomy.resource_kinds` must use values from `registry/vocabularies.yaml:resource_kinds`;
- `taxonomy.research_tags` carries language stages, scripts, prospective categories, infrastructure families, and other research descriptors that do not yet justify a release-vocabulary change.

A research tag becoming common is a reason to consider a separate vocabulary change; it is not automatically promoted into the canonical registry.

## Evidence snapshots

Every candidate has at least one dated `evidence` snapshot. Snapshots are append-only observations ordered from oldest to newest and may include:

- upstream commit/tag/release;
- license-source URLs;
- observed MCP/tool names;
- install/connect result;
- representative live-smoke result;
- provenance/data evidence links.

A missing test is `not-tested`, not `success`. New research should append a newer snapshot rather than rewriting old observations when historical evidence matters.

## Querying

Examples:

```bash
python scripts/query_candidates.py --priority P0 --data-license-status unknown --ids-only
python scripts/query_candidates.py --priority P0 --integration-status wanted --ids-only
python scripts/query_candidates.py --live-smoke success --ids-only
python scripts/query_candidates.py --authentication required
python scripts/query_candidates.py --technical-readiness blocked --ids-only
```

Filters are conjunctive. The latest evidence snapshot supplies mutable result fields such as `live_smoke`.

## Promotion into the marketplace

`promotion.status=ready-for-verification` means only that candidate research is mature enough to start an independent release-integration review. It is not support status.

Promotion into `registry/plugins.yaml`, `registry/providers.yaml`, or `registry/resources.yaml` requires a separate change that independently verifies current upstream identity, licensing/access conditions, installation/connection behavior, tool/resource surface, and representative integration behavior. Do not copy an old candidate snapshot into release metadata as if it were current verification.

`promotion.status=promoted` must name one or more canonical registry targets. Initial issue #15 records remain `candidate` or `ready-for-verification` and do not expand release scope.
