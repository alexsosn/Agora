# Agora

**Agora is a cross-platform plugin marketplace for philology and related disciplines.**

The project aims to make scholarly corpora, textual databases, lexica, manuscript resources, search services, and other research tools easy to install and use from AI agents.

Agora is not tied to a single corpus format or backend. The first implementation combines a large local corpus family exposed through Context-Fabric MCP with independent scholarly MCP services.

## First implementation

Agora v0.1 has a fixed initial resource scope:

- **Context-Fabric** — the complete current Context-Fabric corpus catalog (**35 listed corpora**) plus **`alexsosn/TLHdig-TF`**, for **36 Context-Fabric corpus resources** in total.
- **Perseus** — `tonyjurg/Perseus-mcp`, providing access to Perseus/Scaife resources.
- **Sefaria** — independent Sefaria MCP integration.
- **SEDRA** — independent Beth Mardutho / SEDRA integration.

The detailed corpus list is maintained in [wiki/v0.1-scope.md](wiki/v0.1-scope.md).

Inclusion in the first implementation does not imply that every underlying dataset is already Verified. Agora distinguishes plugin/runtime verification from resource-level data status. For example, TLHdig-TF is included from the start but currently remains **Experimental** because its upstream `0.1.0` conversion is explicitly described as an integration prototype rather than research-ready data.

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

**Phase 0 — project foundation — is implemented.** Agora has an intentional marketplace-first repository layout, project licensing and contribution rules, a policy for generated artifacts, and a minimal CI foundation check.

The next milestone is **Phase 1: define the canonical marketplace and resource data model** for the fixed v0.1 scope: the Context-Fabric provider with all 36 initial corpus resources, plus Perseus, Sefaria, and SEDRA.

No plugin integrations are considered implemented or verified yet.

## Repository layout

- `registry/` — canonical marketplace, plugin, provider, and resource metadata and schemas.
- `plugins/` — plugin integrations and scholarly skills.
- `profiles/` — optional curated bundles.
- `scripts/` — generators, validators, and repository tooling.
- `tests/` — unit and integration tests.
- `generated/` — generated artifacts intentionally committed to the repository.
- `wiki/` — design research and implementation plans.

## Documentation

- [v0.1 implementation scope](wiki/v0.1-scope.md)
- [Research and architecture](wiki/research.md)
- [Implementation plan](wiki/plan.md)
- [Contributing](CONTRIBUTING.md)

## Contributing

The intended contribution model is lightweight: adding a straightforward third-party philological MCP server should eventually require a plugin definition, scholarly metadata/instructions, and smoke tests rather than changes throughout the core repository.

See [CONTRIBUTING.md](CONTRIBUTING.md) for repository conventions and the clean-slate policy.
