# Registry

This directory contains Agora's canonical machine-readable marketplace metadata and schemas.

Phase 1 is implemented around the fixed v0.1 scope:

- four plugin families: `context-fabric`, `perseus`, `sefaria`, and `sedra`;
- four provider records;
- 35 resources from the Context-Fabric corpus catalog snapshot;
- `alexsosn/TLHdig-TF` as the 36th Context-Fabric resource;
- explicit collection handling for `pthu/bible`, `pthu/patristics`, and `pthu/greek_literature`.

## Canonical files

- `plugins.yaml` — installable plugin/integration metadata.
- `providers.yaml` — scholarly/runtime backend metadata.
- `resources.yaml` — corpus and collection resources exposed through providers.
- `vocabularies.yaml` — controlled vocabulary used by the registries.
- `v0.1.yaml` — machine-readable fixed release scope.
- `schema/` — JSON Schemas for the canonical registry documents.
- `collections/` — member indexes for collection resources.

The collection indexes are intentionally `pending` in Phase 1: their schema and references are now stable, while actual member enumeration/discovery belongs to the Context-Fabric implementation phase.

## Validation

Run:

```bash
python -m pip install -r requirements-dev.txt
python scripts/validate_registry.py
python -m unittest discover -s tests -v
```

Validation checks schema conformance, duplicate IDs, cross-file references, controlled-vocabulary values, collection/index consistency, and the exact four-plugin / 36-resource v0.1 contract. CI runs the same checks.

Plugin/integration verification is distinct from resource/data verification. Client-specific marketplace manifests must be generated from this canonical data rather than maintained as parallel sources of truth.

The human-readable baseline is documented in [`wiki/v0.1-scope.md`](../wiki/v0.1-scope.md).
