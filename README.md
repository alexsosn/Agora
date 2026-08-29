# Agora

**Agora is a cross-platform plugin marketplace for philology and related disciplines.**

Agora makes scholarly corpora, textual databases, lexica, search services, and other research tools installable as AI-agent capabilities without forcing them into one corpus format or backend.

The v0.1 implementation combines a large local Text-Fabric/Context-Fabric resource family with independent remote and local MCP integrations. Plugin verification and scholarly-data verification are deliberately separate: a working MCP integration does not imply that every underlying corpus is research-grade.

## v0.1 integrations

All four v0.1 integrations have live **Codex-path** evidence, while the current aggregate plugin status remains **Community** until equivalent Claude-path live verification exists:

- **Context-Fabric** — discovery and lazy acquisition for the fixed **36-resource** Text-Fabric/Context-Fabric baseline, including collection-aware handling for repositories containing many independent corpora.
- **Perseus** — pinned upstream `tonyjurg/Perseus-mcp` integration for Perseus/Scaife discovery, CTS navigation, passage retrieval, and search.
- **Sefaria** — the official hosted Sefaria Texts MCP, with client-specific transport adaptation where required.
- **SEDRA** — a small read-only Agora MCP adapter over Beth Mardutho's public SEDRA IV word and lexeme JSON endpoints.

The fixed resource scope is documented in [wiki/releases/v0.1-scope-frozen.md](wiki/releases/v0.1-scope-frozen.md).

### What verification means here

Agora records verification per client/transport rather than treating one plugin label as evidence for every launch path. The current live workflow exercises the generated Codex path for all four v0.1 plugins and checks:

1. generated launch metadata;
2. MCP server startup or endpoint connection;
3. MCP initialization;
4. expected-tool discovery;
5. at least one representative real operation;
6. deterministic unit/packaging tests.

Claude launch metadata is tested deterministically but is not currently promoted to live-verified status. Context-Fabric additionally has a scheduled metadata audit over all **36** registered upstream resources; the current audit resolves **36/36** successfully.

Resource-level status remains independent. A corpus may still be `experimental` even when a client integration is operational. TLHdig-TF, for example, remains resource-level Experimental while its upstream conversion documents unresolved correctness issues.

## Scholarly skills

Agora plugins now bundle portable `SKILL.md` research guidance in addition to MCP access. The first Phase 5 layer contains **eight tested skills**:

- **Context-Fabric provider workflow** — discover resources and collection members, load lazily, inspect schema before querying, and keep plugin status separate from resource status;
- **BHSA / ETCBC** — feature semantics including `sp`, `pdp`, `vs`, `vt`, syntax features, counting discipline, and CC BY-NC 4.0 data licensing;
- **CUC / Ugaritic** — `g_cons`, sign/editorial features such as `emen`, `cert`, and `alt`, corpus-coverage cautions, and treatment of uncertain readings;
- **TLHdig-TF / Hittite** — explicit prototype warning, morphology on `analysis` nodes, competing analyses, and the `width>1` damage-range invariant;
- **Greek Text-Fabric collections** — member-first discovery, per-work schema inspection, provenance, and edition identity across the PTHU/Perseus/OpenGreekAndLatin ecosystem;
- **Perseus** — CTS/Scaife discovery, no invented URNs, form versus lemma search, and live-service limitations;
- **Sefaria** — canonical references, source versus translation layers, Hebrew/Aramaic versus English search behavior, links, dictionaries, and manuscript evidence;
- **SEDRA** — word-form versus lexeme semantics, ambiguity preservation, Syriac Unicode input, and limits of lexical evidence.

Skills use the Agent Skills `skills/<name>/SKILL.md` layout and are checked in CI for valid YAML frontmatter, naming/size constraints, references to real plugin tools, source-specific research invariants, and Codex UI metadata.

## Context-Fabric resource model

Agora does not expose every Text-Fabric dataset as a separate marketplace plugin. Context-Fabric is one provider plugin with a resource catalog and lazy resolver.

Large repositories remain collection resources. In particular, `pthu/bible`, `pthu/patristics`, `pthu/greek_literature`, and `HuygensING/translatin-manif` contain many independently loadable TF datasets and are discovered at member level rather than flattened into hundreds or thousands of marketplace entries.

For example, the current source audit finds **1,779** TF dataset roots in `pthu/greek_literature`; using one work does not require registering 1,779 plugins. See [wiki/architecture/ref-context-fabric-collections.md](wiki/architecture/ref-context-fabric-collections.md).

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

Agora launches the published upstream `perseus-mcp==1.0.2` package directly through `uvx`; it does not vendor or fork Perseus-MCP. The current live Codex-path verification performs a real Homer author-discovery query.

### Sefaria

Claude can connect directly to the official hosted Sefaria SSE endpoint. Current Codex plugin MCP configuration uses a stdio bridge through `mcp-proxy==0.12.0`. Because that proxy currently resolves an incompatible MCP SDK 2.x unless constrained, Agora explicitly pins the proxy environment to `mcp>=1.17,<2`. The current live Codex-path verification retrieves Genesis 1:1 from Sefaria.

### SEDRA

Agora ships only the adapter code, not SEDRA data. The adapter exposes Beth Mardutho's public SEDRA IV word and lexeme endpoints as read-only MCP tools and preserves the upstream response rather than inventing linguistic interpretation. The current live Codex-path verification executes a real Syriac word lookup.

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
- **Phase 4 — Perseus, Sefaria, and SEDRA:** implemented; Codex paths are live-verified, while aggregate plugin status remains Community pending equivalent Claude-path evidence.
- **Phase 5 — scholarly skills:** underway; eight provider/corpus-specific skills are implemented and CI-validated, with additional resource-specific guidance still to add.
- **Phase 6 — verification/trust:** client-specific live verification is implemented for Codex paths; deeper resource/member verification remains ongoing.
- **Phase 7 — documentation:** underway; current Claude Code, managed ChatGPT/Codex, and local Codex installation flows are documented.

The next implementation work is tracked in the wiki index and latest independent review, with Context-Fabric snapshot integrity and representative corpus-load evidence now the highest-priority engineering items.

## Repository layout

- `registry/` — canonical marketplace, plugin, provider, resource, collection, release-scope, licensing, and verification metadata.
- `plugins/` — client packages, MCP integrations, and scholarly skills.
- `profiles/` — optional curated bundles.
- `scripts/` — generators, validators, audits, live-smoke tooling, and repository utilities.
- `tests/` — deterministic unit, packaging, registry, skill, and integration-contract tests.
- `generated/` — generated artifacts that do not have client-mandated native paths.
- `wiki/` — categorized architecture, release, guide, backlog, and review documentation; see [wiki/README.md](wiki/README.md).

## Documentation

- [Wiki index and priority convention](wiki/README.md)
- [Installation](wiki/guides/installation.md)
- [v0.1 implementation scope](wiki/releases/v0.1-scope-frozen.md)
- [Greek/Context-Fabric collection handling](wiki/architecture/ref-context-fabric-collections.md)
- [Research and architecture](wiki/architecture/ref-marketplace-architecture.md)
- [Implementation plan](wiki/releases/v0.1-plan-active.md)
- [Latest independent review](wiki/reviews/2026-08-29-review-pr1-pr4.md)
- [Contributing](CONTRIBUTING.md)

## Contributing

The intended contribution path is lightweight: a straightforward third-party philological MCP should normally require canonical metadata, a client launch adapter, scholarly guidance, and smoke tests—not changes throughout the core marketplace.

See [CONTRIBUTING.md](CONTRIBUTING.md) for repository conventions and the clean-slate policy.
