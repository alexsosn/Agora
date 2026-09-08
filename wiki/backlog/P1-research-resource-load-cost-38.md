# Research: resource load-cost metadata (#38)

## Status

Research gate complete against `main` at `807db7dcdf09f1aaaae04a7a6a19f193d22af4b9`. This ticket is Agora-owned metadata/discovery work: it should help a user decide whether to prepare/load a registered Context-Fabric resource without changing Text-Fabric compilation behavior or adding corpus-specific loader logic.

## User problem

`ContextFabricService._resource_dict()` exposes identity, languages/disciplines, source, licence, verification, collection semantics, and modules, but no expected acquisition/compile/load cost. `ResourceSpec` likewise has no cost field, and `registry/schema/resources.schema.json` rejects unknown top-level properties.

That makes small and very large resources look operationally equivalent before loading. The existing controlled measurements in #38 show that assumption is unsafe:

- `cuc`: about 3.1 MB TF source, 20 MB compiled cache, 24 MB total cache, 288 MB peak RSS, roughly 0.5 min first load, 1.5 s warm load;
- `bhsa`: about 165 MB source, 866 MB compiled cache, 1.1 GB total cache, 2.58 GB peak RSS, roughly 10.5 min first load, 7.7 s warm load;
- `TLHdig-TF`: about 388 MB source, 4.6 GB compiled cache, 5.1 GB total cache, about 2.1 GB observed peak RSS, roughly 29 min first load;
- `greek_literature`: collection discovery is cheap (about 5.2 s / 1.7 MB) while individual members are typically around 10 MB and 20–33 s to load.

The compiled/source amplification varies materially (roughly 5–12x in the measured corpus examples), so Agora must not infer compiled cost from source bytes with a fixed multiplier.

## Existing architecture

The metadata path is already thin and lossless:

1. `registry/resources.yaml` is validated by `registry/schema/resources.schema.json`.
2. `Catalog._resources_from_document()` projects registry entries into frozen `ResourceSpec` objects.
3. `ContextFabricService._resource_dict()` projects those specs to `list_available_corpora` / `describe_available_corpus` responses.
4. `generate_context_fabric_catalog.py` copies canonical resource metadata into the bundled Context-Fabric catalog; existing packaging tests require that projection to remain lossless.

Therefore load-cost disclosure should follow this path. No resolver, GitStore, Text-Fabric loader, cache lifecycle, or corpus-specific branch is required.

## Boundary with runtime safety

Recent load-safety work already owns hard runtime protections such as compile budgets, free-space checks, timeouts, progress/cancellation state, and cache lifecycle. This ticket should not turn historical measurements into admission-control thresholds. A laptop differing from the measurement host may legitimately use more/less time, RAM, or disk.

`load_cost` is advisory empirical metadata. Runtime guards remain authoritative for whether the current machine can proceed.

## Measurement semantics

The values are observations, not portable guarantees. The schema should therefore require measurement provenance whenever cost metadata is present.

Recommended v1 shape:

```yaml
load_cost:
  scope: resource
  source_size_mb: 165
  compiled_size_mb: 866
  total_cache_mb: 1100
  peak_rss_mb: 2580
  cold_prepare_seconds: 141
  cold_load_seconds: 485
  warm_load_seconds: 7.7
  measurement:
    checked_at: '2026-09-04'
    environment: macOS 24.6.0 x86_64; Python 3.13; cfabric-mcp 0.1.7; context-fabric 0.5.7
  notes: Optional human-readable caveat.
```

For a collection, whole-collection load numbers are misleading because members are lazy and independently materialized. Use a different scope and member/discovery fields:

```yaml
load_cost:
  scope: collection-member
  typical_member_cache_mb: 10
  typical_member_load_seconds:
    min: 20
    max: 33
  discovery_seconds: 5.2
  discovery_cache_mb: 1.7
  measurement:
    checked_at: '2026-09-04'
    environment: ...
```

The schema should not require every numeric observation. Partial measurements are better than invented values, but it must require at least one observation plus provenance. Numeric sizes/times are non-negative finite JSON numbers. Ranges require `min <= max` via semantic validation because JSON Schema alone cannot compare sibling values portably.

## Scope rules

- `kind: corpus`: `load_cost.scope` must be `resource`.
- `kind: collection`: `load_cost.scope` must be `collection-member`.
- v1 does not attach standalone load cost to `feature-module`; module combinations have separate combinatorial/overlay semantics tracked in #46.
- absence of `load_cost` remains valid for backward compatibility. This lets measurements be added incrementally rather than fabricating estimates for the entire catalog.

## Initial seed data

Seed only measurements with existing controlled evidence in #38:

- `cuc`;
- `bhsa`;
- `TLHdig-TF`;
- `greek_literature` with collection-member scope.

Do not populate other resources by extrapolation.

The `TLHdig-TF` peak RSS figure was carried from a separate run according to the issue evidence, so its notes should say that. The collection member figures are typical-range observations rather than per-member guarantees.

## Presentation contract

The runtime should return `load_cost` unchanged (or `null`/absent consistently when unknown) from resource descriptions. The field must remain visibly advisory: names such as `measurement`, `typical_*`, and explicit scope prevent callers from treating a historical measurement as a current-machine quota.

For a corpus with optional modules, parent `load_cost` describes the parent-only load. The response should not pretend it predicts an unseen module combination. #46 owns overlay-combination cost; a short `notes` caveat on BHSA is appropriate until that work lands.

## Alternatives rejected

- **Fixed source→compiled multiplier:** contradicted by measured 5–12x amplification.
- **Dynamic probing during `describe_available_corpus`:** would make discovery expensive and side-effectful, defeating the purpose of pre-load metadata.
- **One flat shape for corpora and collections:** collection-level numbers would imply loading all lazy members together.
- **Make measurements hard load limits:** environment-specific observations are not safe admission-control policy.
- **Require measurements for every resource immediately:** would incentivize guessed data and block unrelated registry maintenance.
- **Put corpus-specific size logic in the MCP service:** violates Agora's thin generic registry boundary.

## Research conclusion

Add optional, schema-validated, provenance-bearing `load_cost` metadata with separate corpus and collection-member scopes; project it losslessly through `ResourceSpec` and resource descriptions; seed only the four measured resources; keep runtime safety and module-overlay costs separate. Implementation must proceed through a design gate and committed RED tests before schema/runtime changes.
