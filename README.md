# Agora

**Agora is a cross-platform plugin marketplace for philology and related disciplines.**

The project aims to make scholarly corpora, textual databases, lexica, manuscript resources, search services, and other research tools easy to install and use from AI agents.

Agora is not tied to a single corpus format or backend. Text-Fabric is one important provider family, but the marketplace is designed to integrate heterogeneous resources: local MCP servers, hosted MCP endpoints, APIs exposed through MCP, locally cached corpora, and plugins that add domain-specific research skills around external tools.

## Planned scope

Initial integrations are planned around:

- Text-Fabric / ContextFabric corpora
- Perseus / Scaife via `tonyjurg/Perseus-mcp`
- Sefaria
- Beth Mardutho / SEDRA
- additional MCP servers and research services for Classics, Ancient Near Eastern studies, Biblical studies, Judaica, Syriac studies, papyrology, epigraphy, manuscript studies, lexicography, historical linguistics, and related fields

The long-term goal is a curated marketplace where each plugin can bundle not only MCP access, but also the scholarly instructions needed to use the underlying resource correctly.

## Design principles

- **Cross-platform:** target ChatGPT/Codex, Claude Code, and Google Antigravity where practical.
- **Provider-neutral:** support Text-Fabric, remote APIs, hosted MCPs, local databases, and other scholarly backends.
- **Upstream-first:** integrate third-party projects without unnecessarily vendoring or forking them.
- **Research-aware:** plugins should include corpus/service-specific guidance, conventions, limitations, and useful query patterns.
- **License-aware:** distinguish software licenses from dataset/content licenses and service terms.
- **Verified where possible:** test real scholarly operations, not only MCP startup.
- **Scalable:** large corpus families should be represented through provider registries rather than one marketplace entry per individual text.
- **Clean-slate:** Agora has no compatibility obligation to `mcp-demo`. Earlier code and research may be reused where useful, but Agora's architecture is defined independently.

## Status

**Phase 0 — project foundation — is implemented.** Agora now has an intentional marketplace-first repository layout, project licensing and contribution rules, a policy for generated artifacts, and a minimal CI foundation check.

The next milestone is **Phase 1: define the canonical marketplace data model and registry schema** for the initial Text-Fabric, Perseus, Sefaria, and SEDRA integrations.

No plugin integrations are considered implemented or verified yet.

## Repository layout

- `registry/` — canonical marketplace metadata and schemas.
- `plugins/` — plugin integrations and scholarly skills.
- `profiles/` — optional curated bundles.
- `scripts/` — generators, validators, and repository tooling.
- `tests/` — unit and integration tests.
- `generated/` — generated artifacts intentionally committed to the repository.
- `wiki/` — design research and implementation plans.

## Documentation

- [Research and architecture](wiki/research.md)
- [Implementation plan](wiki/plan.md)
- [Contributing](CONTRIBUTING.md)

## Contributing

The intended contribution model is lightweight: adding a straightforward third-party philological MCP server should eventually require a plugin definition, scholarly metadata/instructions, and smoke tests rather than changes throughout the core repository.

See [CONTRIBUTING.md](CONTRIBUTING.md) for repository conventions and the clean-slate policy.
