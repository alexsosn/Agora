# Agora

**Agora is a cross-platform plugin marketplace for philology and related disciplines.**

The project aims to make scholarly corpora, textual databases, lexica, manuscript resources, search services, and other research tools easy to install and use from AI agents.

Agora is not tied to a single corpus format or backend. The first implementation combines a large local corpus family exposed through Context-Fabric MCP with independent scholarly MCP services.

## First implementation

Agora v0.1 has a fixed initial resource scope:

- **Context-Fabric** — the complete current Context-Fabric corpus catalog (**35 listed resources**) plus **`alexsosn/TLHdig-TF`**, for **36 Context-Fabric resources** in total.
- **Perseus** — `tonyjurg/Perseus-mcp`, providing access to Perseus/Scaife resources.
- **Sefaria** — independent Sefaria MCP integration.
- **SEDRA** — independent Beth Mardutho / SEDRA integration.

The detailed corpus list is maintained in [wiki/v0.1-scope.md](wiki/v0.1-scope.md).

Inclusion in the first implementation does not imply that every underlying dataset is already Verified. Agora distinguishes plugin/runtime verification from resource-level data status. TLHdig-TF, for example, is included from the start but remains **Experimental** while its upstream conversion still documents unresolved correctness issues.

Large Greek repositories require collection-aware handling. `pthu/bible`, `pthu/patristics`, and `pthu/greek_literature` are registered as collection resources whose individual TF corpora are discovered and loaded separately rather than exposed as thousands of marketplace entries. See [wiki/greek-collections.md](wiki/greek-collections.md).

The long-term goal is a curated marketplace where each plugin can bundle not only MCP access, but also the scholarly instructions needed to use the underlying resource correctly.

## Marketplace formats

Agora currently generates native marketplace/plugin metadata for:

- **Claude Code** — `.claude-plugin/marketplace.json` and per-plugin `.claude-plugin/plugin.json`;
- **ChatGPT/Codex** — `.agents/plugins/marketplace.json` and per-plugin `.codex-plugin/plugin.json`.

These files are deterministic projections of the canonical registry. Regenerate them with:

```bash
python scripts/generate_marketplaces.py
```

or verify freshness without changing files:

```bash
python scripts/generate_marketplaces.py --check
```

Antigravity support is intentionally deferred for now.

## Design principles

- **Cross-platform:** the current native targets are Claude Code and ChatGPT/Codex; additional clients can be added through adapters later.
- **Provider-neutral:** support Context-Fabric, remote APIs, hosted MCPs, local databases, and other scholarly backends.
- **Upstream-first:** integrate third-party projects without unnecessarily vendoring or forking them.
- **Research-aware:** plugins should include corpus/service-specific guidance, conventions, limitations, and useful query patterns.
- **License-aware:** distinguish software licenses from dataset/content licenses and service terms.
- **Resource-aware verification:** verify plugin integration and underlying resource quality separately.
- **Scalable:** large corpus families and collection repositories remain resources within provider plugins rather than one marketplace entry per individual text.
- **Clean-slate:** Agora has no compatibility obligation to `mcp-demo`. Earlier code and research may be reused where useful, but Agora's architecture is defined independently.

## Status

**Phase 0 — project foundation — is implemented.**

**Phase 1 — canonical marketplace and resource data model — is implemented.** Agora has canonical marketplace/plugin/provider/resource metadata, all 36 fixed Context-Fabric resources, collection modeling, controlled vocabularies, release-scope enforcement, and registry validation in CI.

**Phase 2 — deterministic Claude and ChatGPT/Codex marketplace generation — is implemented.** Agora now has:

- platform-neutral `registry/marketplace.yaml` publisher metadata;
- native Claude and Codex marketplace catalogs;
- native per-plugin manifests for all four v0.1 plugin families;
- deterministic serialization and release-derived `0.1.0` plugin versions;
- `scripts/generate_marketplaces.py` with write and `--check` modes;
- generation/order/policy/freshness unit tests;
- CI enforcement that generated artifacts match the canonical registry.

The generated plugin manifests are deliberately metadata-only at this stage. MCP server declarations and scholarly skills are added when their actual integrations are implemented rather than advertised prematurely.

The next milestone is **Phase 3: implement the Context-Fabric provider, corpus resolver/acquisition layer, collection-member handling, and the complete 36-resource baseline**.

No plugin runtime integration is considered Verified yet.

## Repository layout

- `registry/` — canonical marketplace, plugin, provider, resource, collection, and release-scope metadata and schemas.
- `plugins/` — plugin integrations, native client manifests, and scholarly skills.
- `profiles/` — optional curated bundles.
- `scripts/` — generators, validators, and repository tooling.
- `tests/` — unit and integration tests.
- `generated/` — reserved for generated artifacts without client-mandated native paths.
- `wiki/` — design research and implementation plans.

## Documentation

- [v0.1 implementation scope](wiki/v0.1-scope.md)
- [Greek collection handling](wiki/greek-collections.md)
- [Research and architecture](wiki/research.md)
- [Implementation plan](wiki/plan.md)
- [Contributing](CONTRIBUTING.md)

## Contributing

The intended contribution model is lightweight: adding a straightforward third-party philological MCP server should eventually require a plugin definition, scholarly metadata/instructions, and smoke tests rather than changes throughout the core repository.

See [CONTRIBUTING.md](CONTRIBUTING.md) for repository conventions and the clean-slate policy.
