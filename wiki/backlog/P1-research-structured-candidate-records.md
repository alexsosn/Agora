# Structured candidate research

## Problem statement

Issue #15 identifies a modelling problem in Agora's post-v0.1 research backlog: candidate identity, priority, licensing, maintenance, scholarly value, implementation readiness, annotation maturity, and observed integration evidence are currently mixed together in prose. That makes basic research questions impossible to answer mechanically and encourages release-registry records to be copied from narrative claims without an explicit verification step.

The existing release registry already has a strong validation path: canonical YAML records, Draft 2020-12 JSON Schemas, controlled vocabularies, and cross-record validation through `scripts/validate_registry.py`. Candidate research should reuse that validation approach without becoming part of the release registry itself.

## Research findings

### 1. Candidate research is not release metadata

`registry/` represents supported marketplace state. Research candidates include projects that are blocked, unverified, superseded, missing licenses, or merely wanted integrations. Putting them in canonical plugin/provider/resource files would imply support and would blur the boundary between investigation and release state.

The candidate store should therefore live outside `registry/`, under a dedicated `research/` namespace, while being validated by the same Foundation command.

### 2. Priority is not readiness

The current P0/P1/P2 labels express research priority or strategic interest. They do not imply that a candidate is technically ready, legally clear, maintained, or cheap to integrate. A useful record must therefore separate:

- research priority;
- scholarly value;
- strategic importance;
- technical readiness;
- provenance/editorial authority;
- legal/licensing clarity;
- maintenance health;
- overlap with existing integrations;
- implementation effort.

This allows, for example, a P0 wanted integration with strong scholarly authority but blocked API/licensing access to remain P0 without looking "ready to build".

### 3. Legal evidence needs separate layers

Software licensing, content/data licensing, redistribution rights, service terms, and authentication are materially different. A single `license` field cannot represent a hosted MCP whose code is MIT while its distributed corpus is non-commercial, or an open dataset whose API requires credentials.

Candidate records should keep these dimensions separate and permit `unknown` explicitly rather than converting missing evidence into optimistic defaults.

### 4. Annotation maturity is evidence, not a quality slogan

Several backlog candidates mix manually reviewed annotations, generated NLP layers, snapshot/WIP data, and unknown provenance. Candidate research needs a controlled annotation-maturity field that can distinguish:

- `generated`;
- `manually-reviewed`;
- `mixed`;
- `snapshot-wip`;
- `unknown`.

This field describes the observed data layer and does not substitute for upstream documentation.

### 5. Evidence must be timestamped and reproducible

Mutable claims such as tool surfaces, installability, authentication requirements, release versions, and smoke results need evidence snapshots. A snapshot should support:

- `checked_at`;
- upstream commit/tag/release when known;
- license evidence sources;
- observed MCP/tool surface;
- install/connect result;
- representative smoke result;
- provenance and data-evidence links.

Unknown values should remain explicit. A record should not become "verified" merely because its README makes a claim.

### 6. Taxonomy should reuse canonical dimensions where they fit

The backlog proposes many labels such as `egyptology`, `papyrology`, `tei`, `morphology`, `htr-ocr`, and language-specific terms. These should map deliberately:

- capabilities that match a release capability belong in canonical `capabilities`;
- scholarly domains that match the release vocabulary belong in canonical `disciplines`;
- corpus/collection/module shape maps to canonical `resource_kinds` when applicable;
- research-only descriptors, language stages, scripts, implementation families, and prospective taxonomy values belong in free-form `research_tags` until a release vocabulary change is justified.

Candidate research must not silently expand release vocabularies.

### 7. Existing prose should remain available as narrative evidence

The ecosystem, Egyptology, and Germanic backlog documents contain substantial rationale and caveats that should not be flattened into a large YAML blob. Structured records should link back to exact source documents and section anchors. The prose can remain the synthesis layer while machine-readable records carry queryable facts and evidence.

## Recommended data model

Create `research/candidates.yaml` with stable candidate IDs and a schema in `research/schema/candidates.schema.json`. Records should contain:

- stable identity and candidate kind;
- source-document links;
- research priority;
- multidimensional assessment;
- separate legal/access fields;
- annotation maturity;
- taxonomy mapping;
- one or more evidence snapshots;
- optional promotion target/status.

Add `research/README.md` documenting promotion policy and taxonomy mapping. Extend `scripts/validate_registry.py` so Foundation validates candidate research as part of the normal repository metadata gate. Add `scripts/query_candidates.py` for deterministic queries over candidate data.

## Migration scope for issue #15

The first migration should cover the high-value and representative candidates from all three existing research backlogs and link every structured record back to the original prose. The original documents remain unchanged, so no substantive narrative note is lost. Subsequent research can add or deepen records incrementally without changing release scope.

The migration must include enough diversity to prove the model can represent:

- P0/P1/P2 and wanted integrations;
- known and unknown data licenses;
- hosted and local integrations;
- successful, failed, pending, and unknown live-smoke state;
- manually reviewed, generated, mixed, snapshot/WIP, and unknown annotation maturity;
- candidates that are strategically important but technically blocked.

## Promotion rule

Promotion into `registry/plugins.yaml`, `registry/providers.yaml`, or `registry/resources.yaml` is a separate change. It requires independent verification of the candidate's current upstream state, licensing/access evidence, and representative integration behavior. Candidate evidence can inform that review but must not be copied as if it were current release verification.
