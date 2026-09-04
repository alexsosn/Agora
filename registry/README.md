# Registry

This directory contains Agora's canonical machine-readable marketplace metadata and schemas.

Phase 1 is implemented around the fixed v0.1 scope:

- four plugin families: `context-fabric`, `perseus`, `sefaria`, and `sedra`;
- four provider records;
- 35 resources from the Context-Fabric corpus catalog snapshot;
- `alexsosn/TLHdig-TF` as the 36th Context-Fabric resource;
- `ETCBC/targum` as the 37th Context-Fabric resource;
- explicit collection handling for `pthu/bible`, `pthu/patristics`, and `pthu/greek_literature`.

Experimental materializer plugins are registered separately from the frozen v0.1 MCP marketplace scope. This keeps third-party converter installation metadata distinct from MCP plugin/provider metadata and does not imply that a materialized corpus is already wired into a consumer.

## Canonical files

- `marketplace.yaml` — platform-neutral Agora marketplace/publisher metadata used by Phase 2 generators.
- `plugins.yaml` — installable MCP plugin/integration metadata.
- `providers.yaml` — scholarly/runtime backend metadata.
- `resources.yaml` — corpus and collection resources exposed through providers.
- `materializers.yaml` — immutable third-party materializer-plugin download/install records; currently includes `alexsosn/Pseudepigrapha-TF`.
- `vocabularies.yaml` — controlled vocabulary used by the registries.
- `v0.1.yaml` — machine-readable fixed release scope and plugin ordering.
- `schema/` — JSON Schemas for the canonical registry documents and upstream materializer contract.
- `collections/` — member indexes for collection resources.

The collection indexes are intentionally dynamic: their schema and references are stable, while current members are discovered lazily from upstream Git tree metadata.

A materializer registry entry pins an immutable repository commit, expected upstream plugin identity/version, manifest path, package type/path, and the exact materializer IDs expected in that manifest. `scripts/agora_install_materializer.py` validates that binding before installing any package. Materializer registration does not yet create a resource → materializer → consumer composition; that remains a separate architecture step.

## Validation

Run:

```bash
python -m pip install -r requirements-dev.txt
python scripts/validate_registry.py
python scripts/agora_install_materializer.py list
python scripts/generate_marketplaces.py --check
python -m unittest discover -s tests -v
```

Validation checks schema conformance, duplicate IDs, cross-file references, controlled-vocabulary values, collection/index consistency, the exact four-plugin / 37-resource v0.1 contract, freshness of committed Claude/Codex marketplace artifacts, and the materializer registry/install contract. CI also performs a live Pseudepigrapha-TF download/install smoke from the pinned commit.

Plugin, resource, and materializer verification describe distinct Agora-owned integration paths. They do not assess upstream scholarly suitability or data quality. Client-specific marketplace manifests are generated projections, not parallel sources of truth.

The human-readable baseline is documented in [`wiki/v0.1-scope.md`](../wiki/v0.1-scope.md).
