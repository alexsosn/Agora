# Agora implementation details

This document collects technical and release-engineering information that is useful to contributors and reviewers but too detailed for the main project README.

## v0.1 integrations

The v0.1 marketplace contains four integrations:

- **Context-Fabric** — discovery and lazy acquisition for the fixed 36-resource Text-Fabric/Context-Fabric baseline, including collection-aware handling for repositories containing many independent corpora.
- **Perseus** — pinned upstream `tonyjurg/Perseus-mcp` integration for Perseus/Scaife discovery, CTS navigation, passage retrieval, and search.
- **Sefaria** — the official hosted Sefaria Texts MCP, with client-specific transport adaptation where required.
- **SEDRA** — a small read-only Agora MCP adapter over Beth Mardutho's public SEDRA IV word and lexeme JSON endpoints.

The fixed resource scope is documented in [`../releases/v0.1-scope-frozen.md`](../releases/v0.1-scope-frozen.md).

## Verification model

Agora records verification per client/transport rather than treating one plugin label as evidence for every launch path.

The current live workflow exercises the generated Codex path for all four v0.1 plugins and checks:

1. generated launch metadata;
2. MCP server startup or endpoint connection;
3. MCP initialization;
4. expected-tool discovery;
5. at least one representative real operation;
6. deterministic unit and packaging tests.

Claude launch metadata is tested deterministically but is not currently promoted to live-verified status. Context-Fabric additionally has a scheduled metadata audit over all 36 registered upstream resources; the current audit resolves 36/36 successfully.

Plugin-level verification and scholarly-data verification are deliberately separate. A working integration does not imply that every underlying corpus is research-grade. TLHdig-TF, for example, remains resource-level Experimental while its upstream conversion documents unresolved correctness issues.

## Scholarly skills

Agora plugins can bundle portable `SKILL.md` research guidance in addition to MCP access. The current Phase 5 layer includes tested skills for:

- Context-Fabric provider workflow;
- BHSA / ETCBC;
- CUC / Ugaritic;
- TLHdig-TF / Hittite;
- Greek Text-Fabric collections;
- Perseus;
- Sefaria;
- SEDRA.

Skills use the Agent Skills `skills/<name>/SKILL.md` layout and are checked in CI for valid YAML frontmatter, naming and size constraints, references to real plugin tools, source-specific research invariants, and Codex UI metadata.

## Context-Fabric resource model

Agora does not expose every Text-Fabric dataset as a separate marketplace plugin. Context-Fabric is one provider plugin with a resource catalog and lazy resolver.

Large repositories remain collection resources. In particular, `pthu/bible`, `pthu/patristics`, `pthu/greek_literature`, and `HuygensING/translatin-manif` contain many independently loadable TF datasets and are discovered at member level rather than flattened into hundreds or thousands of marketplace entries.

For example, the current source audit finds 1,779 TF dataset roots in `pthu/greek_literature`; using one work does not require registering 1,779 plugins. See [`ref-context-fabric-collections.md`](ref-context-fabric-collections.md).

## Generated marketplace formats

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

## Current implementation status

- **Phase 0 — foundation:** implemented.
- **Phase 1 — canonical marketplace/resource model:** implemented.
- **Phase 2 — deterministic Claude + Codex generation:** implemented.
- **Phase 3 — Context-Fabric runtime and 36-resource baseline:** implemented at the resolver/provider layer; all 36 upstreams currently pass the source audit, with resource-level scholarly verification remaining separate.
- **Phase 4 — Perseus, Sefaria, and SEDRA:** implemented; Codex paths are live-verified, while aggregate plugin status remains Community pending equivalent Claude-path evidence.
- **Phase 5 — scholarly skills:** underway; eight provider/corpus-specific skills are implemented and CI-validated, with additional resource-specific guidance still to add.
- **Phase 6 — verification/trust:** client-specific live verification is implemented for Codex paths; deeper resource/member verification remains ongoing.
- **Phase 7 — documentation:** underway; current Claude Code, managed ChatGPT/Codex, and local Codex installation flows are documented.

The next implementation work is tracked in the wiki index and latest independent review, with Context-Fabric snapshot integrity and representative corpus-load evidence among the highest-priority engineering items.

## Repository layout

- `registry/` — canonical marketplace, plugin, provider, resource, collection, release-scope, licensing, and verification metadata.
- `plugins/` — client packages, MCP integrations, and scholarly skills.
- `profiles/` — optional curated bundles.
- `scripts/` — generators, validators, audits, live-smoke tooling, and repository utilities.
- `tests/` — deterministic unit, packaging, registry, skill, and integration-contract tests.
- `generated/` — generated artifacts that do not have client-mandated native paths.
- `wiki/` — categorized architecture, release, guide, backlog, and review documentation.
