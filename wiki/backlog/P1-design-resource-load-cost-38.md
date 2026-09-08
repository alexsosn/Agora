# Design: resource load-cost metadata (#38)

## Gate

This plan follows `P1-research-resource-load-cost-38.md`. Production schema/runtime/registry changes begin only after the RED contract below is committed and observed failing for the intended missing behavior.

## Acceptance contract

V1 adds optional empirical `load_cost` metadata for Context-Fabric corpus and collection resources and exposes it through the existing resource-description path. It is advisory metadata, not a runtime limit or estimate engine.

Backward compatibility:

- resources without `load_cost` remain valid and return no cost claim;
- no existing resource is required to invent measurements;
- feature modules do not gain standalone `load_cost` in v1;
- resolver/materializer/cache behavior is unchanged.

## Schema

Extend `registry/schema/resources.schema.json` with reusable definitions for measurement provenance and non-negative ranges, then add optional `load_cost` to resource records.

### Corpus scope

```yaml
load_cost:
  scope: resource
  source_size_mb: 165
  compiled_size_mb: 866
  total_cache_mb: 1100
  peak_rss_mb: 2580
  first_load_seconds: 630
  warm_load_seconds: 7.7
  measurement:
    checked_at: '2026-09-04'
    agora_revision: bf5fb918d513fcf859bc925a10922e841b777b98
    environment: macOS 24.6.0 x86_64; Python 3.13; cfabric-mcp 0.1.7; context-fabric 0.5.7
    evidence: https://github.com/alexsosn/Agora/issues/38#issuecomment-5536924435
  notes: Historical observation; actual current-machine cost may differ.
```

Allowed corpus observations:

- `source_size_mb`
- `compiled_size_mb`
- `total_cache_mb`
- `peak_rss_mb`
- `first_load_seconds`
- `warm_load_seconds`

At least one observation is required. All are non-negative JSON numbers. `measurement` is required and carries `checked_at` (date), full 40-hex `agora_revision`, non-empty `environment`, and HTTP(S) `evidence` URI.

`first_load_seconds` is intentionally end-to-end historical first-use cost from the controlled measurement, including preparation/acquisition when present. V1 does not pretend every old measurement has a reliable prepare/load split.

### Collection-member scope

```yaml
load_cost:
  scope: collection-member
  typical_member_cache_mb: 10
  typical_member_first_load_seconds: {min: 20, max: 33}
  discovery_seconds: 5.2
  discovery_cache_mb: 1.7
  measurement: ...
```

Allowed collection observations:

- `typical_member_cache_mb`
- `typical_member_first_load_seconds: {min, max}`
- `discovery_seconds`
- `discovery_cache_mb`

At least one observation is required. Range values are non-negative; semantic validation requires `min <= max`.

### Kind/scope binding

Semantic validation in `scripts/validate_registry.py` enforces:

- corpus → `scope: resource`;
- collection → `scope: collection-member`;
- feature-module → no `load_cost`;
- range order is valid.

The JSON schema branches should already make corpus-only versus collection-only fields mutually exclusive, so semantic validation is a second explicit guard for cross-field/kind invariants rather than the only guard.

## Canonical seed measurements

Seed only the controlled observations already recorded in #38, all tied to Agora revision `bf5fb918d513fcf859bc925a10922e841b777b98` and the measurement comment URL.

### `bhsa`

- source 165 MB
- compiled 866 MB
- total cache 1100 MB
- peak RSS 2580 MB
- first load 630 s
- warm load 7.7 s
- note that parent-only cost excludes module-overlay recompilation tracked by #46

### `cuc`

- source 3.1 MB
- compiled 20 MB
- total cache 24 MB
- peak RSS 288 MB
- first load 30 s
- warm load 1.5 s

### `TLHdig-TF`

- source 388 MB
- compiled 4600 MB
- total cache 5100 MB
- peak RSS 2100 MB
- first load 1740 s
- note that peak RSS came from the related earlier run rather than the final converged compile measurement

### `greek_literature`

- collection-member scope
- typical member cache 10 MB
- typical first-load range 20–33 s
- discovery 5.2 s
- discovery cache 1.7 MB

Do not infer or seed values for other resources.

## Runtime projection

Extend `ResourceSpec` with `load_cost: dict[str, Any] = field(default_factory=dict)`.

`Catalog._resources_from_document()` copies `item.get("load_cost")` losslessly into the spec.

`ContextFabricService._resource_dict()` returns:

```python
"load_cost": copy.deepcopy(resource.load_cost) if resource.load_cost else None
```

This keeps the response stable and explicit: unknown means `null`, measured values preserve all registry provenance/notes, and no I/O or computation occurs during description.

Because bundled Context-Fabric resources are generated from canonical registry metadata, the existing generator must preserve `load_cost` unchanged. Add a targeted packaging assertion so later generator changes cannot silently strip it.

## TDD RED contract

Create `tests/test_resource_load_cost.py` before production changes. The tests should fail because schema/catalog/runtime support and seed records do not yet exist, not because fixtures are malformed.

### Schema and semantics

1. existing resource without `load_cost` remains valid;
2. corpus `scope: resource` with one observation + complete measurement provenance is accepted;
3. collection `scope: collection-member` with typical range/discovery observations is accepted;
4. negative size/time values are rejected;
5. missing measurement provenance is rejected;
6. corpus fields are rejected under collection-member scope and vice versa;
7. corpus using collection-member scope is rejected by registry semantic validation;
8. collection using resource scope is rejected;
9. feature-module `load_cost` is rejected;
10. `typical_member_first_load_seconds.min > max` is rejected semantically;
11. provenance-only load-cost blocks with no empirical observation are rejected for both scopes.

### Runtime/catalog projection

12. `Catalog` preserves a corpus `load_cost` mapping losslessly;
13. `_resource_dict` exposes the exact mapping;
14. a resource without measurements reports `load_cost: None` rather than synthesizing estimates;
15. generated/bundled Context-Fabric catalog preserves canonical `load_cost` for seeded resources.

### Canonical seed records

16. `bhsa`, `cuc`, and `TLHdig-TF` carry resource-scoped measured cost with provenance;
17. `greek_literature` carries collection-member scope and a valid 20–33 s range;
18. no unmeasured resources are populated by extrapolation;
19. BHSA notes disclose that module combinations are outside the parent-only measurement.

## Implementation order after RED

1. schema `$defs` and optional property;
2. registry semantic validator for kind/scope/range;
3. `ResourceSpec` + catalog projection;
4. service description projection;
5. four canonical seed records;
6. regenerate Context-Fabric bundled catalog;
7. targeted tests and registry validation;
8. generator freshness checks;
9. full Foundation suite and relevant Context-Fabric packaging/runtime tests;
10. exact-head logically independent adversarial review.

## Review gate

Freeze the exact final head and independently challenge:

- whether measurements can be mistaken for hard limits/current-machine predictions;
- corpus versus collection-member scope leakage;
- stale or unverifiable measurements/provenance;
- invented/extrapolated values;
- unit ambiguity and negative/invalid numbers;
- range-order validation;
- lossless canonical → bundled → runtime projection;
- feature-module/module-combination cost misrepresentation;
- accidental loader/network side effects in description;
- backward compatibility for resources without measurements.

Any blocking review finding receives a new regression RED, minimal fix, full GREEN, and fresh exact-head review before merge.

### Review-harness hygiene

Temporary agent/review workflows may be used only as disposable development scaffolding. They must not remain in the final feature diff, must not become part of Agora's runtime or CI contract, and must not leave write-capable branch-edit orchestration behind after the reviewed change is materialized. The final head must be testable by the repository's ordinary workflows under the normal contributor trust path.
