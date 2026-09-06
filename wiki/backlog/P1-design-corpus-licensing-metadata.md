# P1 — Corpus licensing evidence metadata design

Tracks [#17](https://github.com/alexsosn/Agora/issues/17) and follows the completed research in [`P1-research-corpus-licensing-audit.md`](P1-research-corpus-licensing-audit.md).

Status: **design complete; implementation not started in this PR**.

## Problem

`registry/resources.yaml` currently records only:

```yaml
licenses:
  data: unknown
  redistribution: unknown
  notes: ...
```

That representation has two failures:

1. an `unknown` value does not distinguish “researched and unresolved” from “never checked”;
2. a repository/software licence can be mistaken for the licence governing corpus data.

The research audit also found two cases that cannot be represented truthfully by one bare licence scalar: component-specific corpora and member-specific collections.

## Design decision

Keep the existing user-facing licence fields and redistribution vocabulary. Add a required evidence block to every canonical `corpus` and `collection` resource:

```yaml
licenses:
  data: CC-BY-NC-4.0
  redistribution: restricted
  notes: >-
    Attribution and non-commercial conditions apply.
  evidence:
    status: resolved
    checked_at: "2026-09-06"
    sources:
      - https://github.com/ETCBC/bhsa/blob/master/README.md
```

The evidence block records the state of the research, not a legal conclusion beyond what upstream evidence supports.

### Evidence statuses

Add a controlled vocabulary `license_evidence_statuses`:

- `resolved` — upstream evidence supplies a defensible top-level data licence/redistribution conclusion;
- `component-specific` — materially different embedded components have different terms;
- `member-specific` — a collection carries rights metadata at member/file level;
- `unresolved` — authoritative sources were checked but no defensible top-level data/redistribution terms could be established.

### Existing redistribution vocabulary remains unchanged

Keep:

- `permitted` — redistribution is allowed by the recorded terms; attribution obligations may still apply;
- `restricted` — redistribution/use is allowed only within a material restriction such as non-commercial or no-derivatives/source-specific conditions;
- `unknown` — research did not establish a defensible redistribution conclusion, or a heterogeneous resource cannot be summarized safely.

Do not add licence-specific redistribution enum values.

## Representation rules

### Resolved resources

A `resolved` evidence status requires both `licenses.data` and `licenses.redistribution` to be non-`unknown`.

Examples:

```yaml
licenses:
  data: CC-BY-4.0
  redistribution: permitted
  evidence: {status: resolved, checked_at: "2026-09-06", sources: [...]}
```

```yaml
licenses:
  data: CC-BY-NC-4.0
  redistribution: restricted
  evidence: {status: resolved, checked_at: "2026-09-06", sources: [...]}
```

### Researched unresolved resources

Use the existing scalar `unknown`, but require reproducible evidence and an explanation of what remains unknown:

```yaml
licenses:
  data: unknown
  redistribution: unknown
  notes: Repository MIT licence covers software; corpus-data terms were not stated.
  evidence:
    status: unresolved
    checked_at: "2026-09-06"
    sources:
      - https://github.com/example/corpus/blob/main/README.md
      - https://github.com/example/corpus/blob/main/LICENSE
```

An unresolved value without evidence or explanatory notes is invalid.

### Component-specific resources

When upstream states a defensible top-level licence but preserves stricter component terms (for example `quran`), record the top-level licence and use `component-specific` evidence plus notes:

```yaml
licenses:
  data: CC-BY-4.0
  redistribution: restricted
  notes: Source components include no-change/BY-ND conditions; see evidence.
  evidence: {status: component-specific, checked_at: "2026-09-06", sources: [...]}
```

When no safe top-level licence exists (for example composite Greek corpora), use:

```yaml
licenses:
  data: component-specific
  redistribution: unknown
  notes: Text, morphology, syntax, and lexical features come from differently licensed sources; see evidence.
  evidence: {status: component-specific, checked_at: "2026-09-06", sources: [...]}
```

`component-specific` is a descriptive registry value, not a licence identifier. Component-specific records require non-empty `licenses.notes` explaining the split at a level useful to a caller; a status plus source URLs alone is not sufficient.

### Member-specific collections

For a collection such as `greek_literature` whose own upstream metadata delegates rights to members/files:

```yaml
licenses:
  data: member-specific
  redistribution: unknown
  notes: Individual TF files carry original TEI availability/licence metadata.
  evidence: {status: member-specific, checked_at: "2026-09-06", sources: [...]}
```

`member-specific` is valid only for `kind: collection` and requires non-empty `licenses.notes` stating where member-level rights information lives.

This issue does not require Agora to ingest or normalize every member licence into the collection index. It records the collection-level truth without inventing one uniform licence.

## Schema

Extend `registry/schema/resources.schema.json`:

```json
"evidence": {
  "type": "object",
  "additionalProperties": false,
  "required": ["status", "checked_at", "sources"],
  "properties": {
    "status": {"type": "string"},
    "checked_at": {"type": "string", "format": "date"},
    "sources": {
      "type": "array",
      "minItems": 1,
      "uniqueItems": true,
      "items": {"type": "string", "format": "uri"}
    }
  }
}
```

Require `licenses.evidence` for `kind: corpus` and `kind: collection`. Do not require it from existing `feature-module` resources in this migration; modules whose licensing materially differs from their parent should receive evidence in a later focused audit rather than blocking #17.

## Validator invariants

`validate_registry.py` must enforce semantic rules that JSON Schema alone should not obscure:

1. `licenses.evidence.status` is in `license_evidence_statuses`.
2. `resolved` requires `data != unknown` and `redistribution != unknown`.
3. If `data == unknown` or `redistribution == unknown`, evidence status may not be `resolved`.
4. `data == component-specific` requires `status == component-specific`.
5. `data == member-specific` requires `status == member-specific` and `kind == collection`.
6. `status == member-specific` requires `data == member-specific` and `kind == collection`.
7. `component-specific`, `member-specific`, and `unresolved` require non-empty `licenses.notes` explaining the condition or uncertainty.
8. Every canonical corpus/collection has at least one evidence source and a valid check date through schema validation.

Evidence-source quality is a contributor/reviewer requirement, not a string-level validator rule. Review must reject records whose `sources` merely point back to Agora's catalog snapshot or to irrelevant software metadata when the claim concerns corpus data; the validator cannot reliably determine semantic relevance from a URL.

## TDD gate

Implementation starts with focused failing tests in `tests/test_resource_license_evidence.py`. Before schema/validator/registry changes, the following contracts must be encoded and observed failing against current `main`:

- [ ] corpus without `licenses.evidence` is rejected;
- [ ] collection without `licenses.evidence` is rejected;
- [ ] feature module without licence evidence remains valid for this migration;
- [ ] `resolved` + `data: unknown` is rejected;
- [ ] `resolved` + `redistribution: unknown` is rejected;
- [ ] `unresolved` with `unknown` values, explanation, date, and primary source URLs is accepted;
- [ ] unresolved/component/member-specific evidence without explanatory `licenses.notes` is rejected;
- [ ] `component-specific` top-level licence (Quran shape) is accepted;
- [ ] `data: component-specific` requires component-specific evidence;
- [ ] `member-specific` is rejected on a corpus;
- [ ] a member-specific collection with notes is accepted;
- [ ] empty/malformed evidence source lists and invalid dates are rejected;
- [ ] the installed Context-Fabric catalog is a lossless projection of the canonical licence evidence;
- [ ] `describe_available_corpus` exposes nested `licenses.evidence` unchanged for a representative resource.

The RED commit should contain only the tests (plus test fixtures/helpers if needed). A CI failure caused by these new expectations is expected and should be recorded before implementation proceeds.

## Implementation plan

After the RED gate:

1. extend the resource schema with `licenses.evidence`;
2. add `license_evidence_statuses` to `registry/vocabularies.yaml`;
3. implement the semantic invariants in `scripts/validate_registry.py`;
4. populate all 37 corpus/collection records from the completed audit;
5. update `registry/README.md` to explain data licence vs software licence, redistribution, evidence statuses, and researched `unknown`;
6. update the Context-Fabric catalog model annotation from `dict[str, str]` to a nested-value-safe type (`dict[str, Any]`) so the new evidence shape is represented accurately;
7. regenerate the self-contained Context-Fabric runtime catalog with `python scripts/generate_context_fabric_catalog.py`; the generator is intentionally lossless, so nested evidence must survive unchanged;
8. verify `describe_available_corpus` exposes the complete `licenses` object; its current shallow dict copy preserves nested evidence, so no behavior change should be needed beyond accurate model typing unless the RED test proves otherwise;
9. do not change corpus acquisition or third-party corpus behavior.

## Test gate

The implementation PR is green only when all of these pass:

```bash
pytest -q tests/test_resource_license_evidence.py
python scripts/validate_registry.py
python scripts/generate_context_fabric_catalog.py --check
python scripts/generate_marketplaces.py --check
pytest -q
```

The runtime catalog is a committed generated artifact and must be regenerated from the canonical registry rather than hand-edited.

## Independent review gate

Before merge, perform a logically independent adversarial review against the implementation diff and primary evidence. The review must sample at least:

- one direct `CC-BY-NC` corpus (`bhsa` or `cuc`);
- one component-specific corpus (`quran` or `SBLGNT`);
- one member-specific collection (`greek_literature`);
- one unresolved modern/copyright-sensitive corpus (`banks` or a DBNL/Huygens-derived corpus);
- one cuneiform corpus (`TLHdig-TF`, CDLI-derived corpus, or `ninmed`).

The reviewer should actively look for accidental software→data licence copying, over-permissive redistribution values, missing component restrictions, unsupported public-domain assumptions, evidence URLs that do not actually support the recorded claim, and stale generated runtime metadata.

## Non-goals

- legal advice or re-licensing upstream data;
- copying full licence texts into Agora;
- normalizing every licence to SPDX when upstream does not use an SPDX identifier;
- harvesting every `greek_literature` member licence into the collection index;
- changing third-party corpus contents or licensing;
- auditing feature modules whose licensing is inherited and not currently known to differ from their parent corpus.
