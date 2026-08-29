# Agora

**Agora is a cross-platform plugin marketplace for philology and related disciplines.**

Agora makes scholarly corpora, textual databases, lexica, search services, and other research tools installable as AI-agent capabilities without forcing them into one corpus format or backend.

The v0.1 implementation combines a large local Text-Fabric/Context-Fabric resource family with independent remote and local MCP integrations. Plugin verification and scholarly-data verification are deliberately separate: a working MCP integration does not imply that every underlying corpus is research-grade.

## v0.1 integrations

All four v0.1 plugin integrations are currently **Verified** by CI:

- **Context-Fabric** — discovery and lazy acquisition for the fixed **36-resource** Text-Fabric/Context-Fabric baseline, including collection-aware handling for repositories containing many independent corpora.
- **Perseus** — pinned upstream `tonyjurg/Perseus-mcp` integration for Perseus/Scaife discovery, CTS navigation, passage retrieval, and search.
- **Sefaria** — the official hosted Sefaria Texts MCP, with client-specific transport adaptation where required.
- **SEDRA** — a small read-only Agora MCP adapter over Beth Mardutho's public SEDRA IV word and lexeme JSON endpoints.

The fixed resource scope is documented in [wiki/v0.1-scope.md](wiki/v0.1-scope.md).

### What “Verified” means here

For a plugin integration, Agora's verification bar includes:

1. generated client launch metadata;
2. MCP server startup or endpoint connection;
3. MCP initialization;
4. expected-tool discovery;
5. at least one representative real operation;
6. deterministic unit/packaging tests.

The scheduled **Agora MCP live smoke** workflow applies that contract to all four v0.1 plugins. Context-Fabric additionally has a scheduled metadata audit over all **36** registered upstream resources; the current audit resolves **36/36** successfully.

Resource-level status remains independent. A corpus may still be `experimental` even when the Context-Fabric plugin itself is `verified`. TLHdig-TF, for example, remains resource-level Experimental while its upstream conversion documents unresolved correctness issues.

## Context-Fabric resource model

Agora does not expose every Text-Fabric dataset as a separate marketplace plugin. Context-Fabric is one provider plugin with a resource catalog and lazy resolver.

Large repositories remain collection resources. In particular, `pthu/bible`, `pthu/patristics`, `pthu/greek_literature`, and `HuygensING/translatin-manif` contain many independently loadable TF datasets and are discovered at member level rather than flattened into hundreds or thousands of marketplace entries.

For example, the current source audit finds **1,779** TF dataset roots in `pthu/greek_literature`; using one work does not require registering 1,779 plugins. See [wiki/greek-collections.md](wiki/greek-collections.md).

## Marketplace formats

Agora generates native marketplace/plugin metadata for:

- **Claude Code** — `.claude-plugin/marketplace.json`, per-plugin `.claude-plugin/plugin.json`, and MCP declarations;
- **ChatGPT/Codex** — `.agents/plugins/marketplace.json`, per-plugin `.codex-plugin/plugin.json`, and MCP declarations.

These files are deterministic projections of the canonical registry. Regenerate them with:

```bash
python scripts/generate_marketplaces.py
```

or verify freshness without modifying files:

```bash
python scripts/generate_marketplaces.py --check
```

The Claude marketplace intentionally uses Claude's strict marketplace schema; Codex-only fields such as `displayName` are emitted only into Codex artifacts.

Antigravity support is intentionally deferred until the core marketplace and scholarly guidance are stable.

## Integration details

### Context-Fabric

The Agora runtime exposes resource discovery, collection-member discovery, preparation/acquisition, and loading tools. Corpus data is not bundled into Agora and is materialized lazily from its registered upstream source.

The fixed source catalog is generated from canonical registry data and audited against actual upstream Git trees. No machine-specific absolute paths are stored in the registry.

### Perseus

Agora launches the published upstream `perseus-mcp==1.0.2` package directly through `uvx`; it does not vendor or fork Perseus-MCP. The live verification performs a real Homer author-discovery query.

### Sefaria

Claude can connect directly to the official hosted Sefaria SSE endpoint. Current Codex plugin MCP configuration uses a stdio bridge through `mcp-proxy==0.12.0`. Because that proxy currently resolves an incompatible MCP SDK 2.x unless constrained, Agora explicitly pins the proxy environment to `mcp>=1.17,<2`. The live verification retrieves Genesis 1:1 from Sefaria.

### SEDRA

Agora ships only the adapter code, not SEDRA data. The adapter exposes Beth Mardutho's public SEDRA IV word and lexeme endpoints as read-only MCP tools and preserves the upstream response rather than inventing linguistic interpretation. The live verification executes a real Syriac word lookup.

## Design principles

- **Cross-platform:** keep scholarly identity and metadata client-neutral; generate client adapters from one registry.
- **Provider-neutral:** support Context-Fabric, hosted MCPs, remote APIs, local databases, and other scholarly backends.
- **Upstream-first:** integrate third-party projects without unnecessary vendoring or forks.
- **Research-aware:** plugins should bundle source-specific instructions, conventions, limitations, and useful query patterns rather than exposing raw tools without scholarly context.
- **License-aware:** software licenses, dataset/content licenses, redistribution status, and service terms are separate metadata.
- **Resource-aware verification:** plugin integration status and underlying scholarly-data status are separate claims.
- **Scalable:** corpus families and collection repositories remain resources within provider plugins rather than one marketplace entry per text.
- **Clean-slate:** Agora has no compatibility obligation to `mcp-demo`; earlier code and research are prior art, not architectural constraints.

## Current status

- **Phase 0 — foundation:** implemented.
- **Phase 1 — canonical marketplace/resource model:** implemented.
- **Phase 2 — deterministic Claude + Codex generation:** implemented.
- **Phase 3 — Context-Fabric runtime and 36-resource baseline:** implemented at the resolver/provider layer; all 36 upstreams currently pass the source audit, with resource-level scholarly verification remaining separate.
- **Phase 4 — Perseus, Sefaria, and SEDRA:** implemented and live-verified.
- **Phase 6 — verification/trust:** plugin-level live verification is implemented; deeper resource/member verification remains ongoing.

The next major implementation milestone is **Phase 5: scholarly skills and source-specific instructions**—the layer that teaches an agent how to use each verified integration correctly rather than merely proving that the tools respond.

## Repository layout

- `registry/` — canonical marketplace, plugin, provider, resource, collection, release-scope, licensing, and verification metadata.
- `plugins/` — client packages, MCP integrations, and scholarly skills.
- `profiles/` — optional curated bundles.
- `scripts/` — generators, validators, audits, live-smoke tooling, and repository utilities.
- `tests/` — deterministic unit, packaging, registry, and integration-contract tests.
- `generated/` — generated artifacts that do not have client-mandated native paths.
- `wiki/` — architecture, implementation plans, and resource documentation.

## Documentation

- [v0.1 implementation scope](wiki/v0.1-scope.md)
- [Greek collection handling](wiki/greek-collections.md)
- [Research and architecture](wiki/research.md)
- [Implementation plan](wiki/plan.md)
- [Contributing](CONTRIBUTING.md)

## Contributing

The intended contribution path is lightweight: a straightforward third-party philological MCP should normally require canonical metadata, a client launch adapter, scholarly guidance, and smoke tests—not changes throughout the core marketplace.

See [CONTRIBUTING.md](CONTRIBUTING.md) for repository conventions and the clean-slate policy.
