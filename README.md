# Agora

**Agora is a cross-platform plugin marketplace for philology and related disciplines.**

The project aims to make scholarly corpora, textual databases, lexica, manuscript resources, search services, and other research tools easy to install and use from AI agents.

Agora is not tied to a single corpus format or backend. The first implementation combines a large local corpus family exposed through Context-Fabric MCP with independent scholarly MCP services.

## First implementation

Agora v0.1 has a fixed initial resource scope:

- **Context-Fabric** — the complete current Context-Fabric corpus catalog (**35 listed corpora**) plus **`alexsosn/TLHdig-TF`**, for **36 Context-Fabric resources** in total.
- **Perseus** — `tonyjurg/Perseus-mcp`, providing access to Perseus/Scaife resources.
- **Sefaria** — independent Sefaria MCP integration.
- **SEDRA** — independent Beth Mardutho / SEDRA integration.

The detailed corpus list is maintained in [wiki/v0.1-scope.md](wiki/v0.1-scope.md).

Inclusion in the first implementation does not imply that every underlying dataset is already Verified. Agora distinguishes plugin/runtime verification from resource-level data status. TLHdig-TF, for example, is included from the start but remains **Experimental** while its upstream conversion still documents unresolved correctness issues.

Large Greek repositories require collection-aware handling. `pthu/bible`, `pthu/patristics`, and `pthu/greek_literature` are registered as collection resources whose individual TF corpora are discovered and loaded separately rather than exposed as thousands of marketplace entries. See [wiki/greek-collections.md](wiki/greek-collections.md).

The long-term goal is a curated marketplace where each plugin can bundle not only MCP access, but also the scholarly instructions needed to use the underlying resource correctly.

## Design principles

- **Cross-platform:** target ChatGPT/Codex, Claude Code, and Google Antigravity where practical.
- **Provider-neutral:** support Context-Fabric, remote APIs, hosted MCPs, local databases, and other scholarly backends.
- **Upstream-first:** integrate third-party projects without unnecessarily vendoring or forking them.
- **Research-aware:** plugins should include corpus/service-specific guidance, conventions, limitations, and useful query patterns.
- **License-aware:** distinguish software licenses from dataset/content licenses and service terms.
- **Resource-aware verification:** verify plugin integration and underlying resource quality separately.
- **Scalable:** large corpus families and collection repositories remain resources within provider plugins rather than one marketplace entry per individual text.
- **Clean-slate:** Agora has no compatibility obligation to `mcp-demo`. Earlier code and research may be reused where useful, but Agora's architecture is defined independently.

## Status

**Phase 0 — project foundation — is implemented.**

**Phase 1 — canonical marketplace and resource data model — is implemented.** Agora now has:

- canonical plugin, provider, resource, collection-index, and release-scope schemas;
- registries for the four v0.1 plugin/provider families;
- all 36 fixed Context-Fabric resources in `registry/resources.yaml`;
- explicit collection modeling for the PTHU Greek collection repositories;
- controlled vocabularies and separate integration/resource verification states;
- an enforceable `registry/v0.1.yaml` release contract;
- registry validation and negative tests in CI.

Collection member indexes currently establish the schema/contract but remain intentionally unpopulated until the Context-Fabric implementation phase.

The next milestone is **Phase 2: generate client marketplace manifests deterministically from the canonical registry**.

No plugin runtime integration is considered implemented or Verified yet.

## Repository layout

- `registry/` — canonical marketplace, plugin, provider, resource, collection, and release-scope metadata and schemas.
- `plugins/` — plugin integrations and scholarly skills.
- `profiles/` — optional curated bundles.
- `scripts/` — generators, validators, and repository tooling.
- `tests/` — unit and integration tests.
- `generated/` — generated artifacts intentionally committed to the repository.
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
