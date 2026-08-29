# Agora

**Agora is a cross-platform plugin marketplace for philology and related disciplines.**

The project aims to make scholarly corpora, textual databases, lexica, manuscript resources, search services, and other research tools easy to install and use from AI agents.

Agora is not tied to a single corpus format or backend. Text-Fabric is one important provider family, but the marketplace is designed to integrate heterogeneous resources: local MCP servers, hosted MCP endpoints, APIs exposed through MCP, locally cached corpora, and plugins that add domain-specific research skills around external tools.

## Planned scope

Initial integrations include or are planned around:

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

## Status

Agora is currently in the architecture and migration stage. The first milestone is to turn the existing `mcp-demo` work into independently usable integrations for:

1. Text-Fabric / ContextFabric
2. Perseus
3. Sefaria
4. SEDRA

The existing summer-school setup will remain reproducible as a profile of the broader marketplace.

## Documentation

- [Research and architecture](wiki/research.md)
- [Implementation plan](wiki/plan.md)

## Contributing

The intended contribution model is lightweight: adding a straightforward third-party philological MCP server should eventually require a plugin definition, scholarly metadata/instructions, and smoke tests rather than changes throughout the core repository.

More contributor documentation will be added as the marketplace schema stabilizes.
