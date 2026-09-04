# Registry

This directory contains Agora's canonical machine-readable marketplace metadata and schemas.

Phase 1 is implemented around the fixed v0.1 scope:

- four MCP plugin families: `context-fabric`, `perseus`, `sefaria`, and `sedra`;
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
- `materializers.yaml` — immutable third-party materializer-plugin source/install records; currently includes `alexsosn/Pseudepigrapha-TF`.
- `vocabularies.yaml` — controlled vocabulary shared by the registries.
- `v0.1.yaml` — machine-readable fixed release scope and plugin ordering.
- `schema/` — JSON Schemas for canonical registry documents and the upstream materializer contract.
- `collections/` — member indexes for collection resources.

The collection indexes are intentionally dynamic: their schema and references are stable, while current members are discovered lazily from upstream Git tree metadata.

A materializer registry entry pins an immutable repository commit, expected upstream plugin identity/version, manifest path, package type/path, install-time trust class, and the exact materializer IDs expected in that manifest. `scripts/validate_registry.py` validates `materializers.yaml` alongside the other canonical files, including duplicate IDs and shared discipline/verification controlled vocabularies.

Registration supports passive source discovery. It does not mean Agora may automatically execute packaging code: Python materializer installation is an explicit trust action because PEP 517/build backends are executable third-party code. Resource → materializer → consumer composition remains a separate architecture step and must preserve that approval boundary.

## Validation

Run:

```bash
python -m pip install -r requirements-dev.txt
python scripts/validate_registry.py
python scripts/agora_install_materializer.py list
python scripts/generate_marketplaces.py --check
python -m unittest discover -s tests -v
```

Validation checks schema conformance, duplicate IDs, cross-file references, controlled-vocabulary values, collection/index consistency, the exact four-plugin / 37-resource v0.1 contract, materializer registry constraints, and freshness of committed Claude/Codex marketplace artifacts.

CI also performs a live Pseudepigrapha-TF integration smoke in two phases: passive immutable source fetch/manifest validation, then a separately explicit Python installation that records runtime and dependency identity. Materializer registration and verification do not assess upstream scholarly suitability or converter semantics.

The human-readable release baseline is documented under [`../wiki/releases/`](../wiki/releases/).
