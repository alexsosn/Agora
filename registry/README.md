# Registry

This directory contains Agora's canonical machine-readable marketplace metadata and schemas.

Phase 1 is implemented around the fixed v0.1 scope:

- four plugin families: `context-fabric`, `perseus`, `sefaria`, and `sedra`;
- four provider records;
- 35 resources from the Context-Fabric corpus catalog snapshot;
- `alexsosn/TLHdig-TF` as the 36th Context-Fabric resource;
- `ETCBC/targum` as the 37th Context-Fabric resource;
- explicit collection handling for `pthu/bible`, `pthu/patristics`, and `pthu/greek_literature`.

## Canonical files

- `marketplace.yaml` — platform-neutral Agora marketplace/publisher metadata used by Phase 2 generators.
- `plugins.yaml` — installable plugin/integration metadata.
- `providers.yaml` — scholarly/runtime backend metadata.
- `resources.yaml` — corpus and collection resources exposed through providers.
- `vocabularies.yaml` — controlled vocabulary used by the registries.
- `v0.1.yaml` — machine-readable fixed release scope and plugin ordering.
- `schema/` — JSON Schemas for the canonical registry documents.
- `collections/` — member indexes for collection resources.

The collection indexes are intentionally dynamic: their schema and references are stable, while current members are discovered lazily from upstream Git tree metadata.

## Validation

Run:

```bash
python -m pip install -r requirements-dev.txt
python scripts/validate_registry.py
python scripts/generate_marketplaces.py --check
python -m unittest discover -s tests -v
```

Validation checks schema conformance, duplicate IDs, cross-file references, controlled-vocabulary values, collection/index consistency, the exact four-plugin / 37-resource v0.1 contract, and freshness of committed Claude/Codex marketplace artifacts. CI runs the same checks.

Plugin and resource verification describe distinct Agora-owned integration paths. They do not assess upstream scholarly suitability or data quality. Client-specific marketplace manifests are generated projections, not parallel sources of truth.

The human-readable baseline is documented in [`wiki/v0.1-scope.md`](../wiki/v0.1-scope.md).
