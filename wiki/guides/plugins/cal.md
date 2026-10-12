# Comprehensive Aramaic Lexicon MCP

Read-only CAL lexical, textual, concordance, Syriac, Targum, and bibliography tools via the published CAL-MCP server.

## Use this plugin for

- **Dictionary lookup** (`dictionary-lookup`)
- **Lexeme lookup** (`lexeme-lookup`)
- **Passage retrieval** (`passage-retrieval`)
- **Structured search** (`structured-search`)

## Access and resources

CAL-MCP is a local Python stdio MCP server installed from the published `cal-mcp==0.1.0` package. It queries remote Comprehensive Aramaic Lexicon (CAL) pages on demand; Agora never downloads or mirrors the CAL text database.

## What connects or runs

Upstream cal-mcp 0.1.0 is launched directly with uvx (Python >=3.11) over local stdio; CAL data remain remote and the adapter is not hosted by Agora.

## Local and remote behavior

Runtime mode: `local`.
Data mode: `remote`.
Runtime type: `python`.

## Prerequisites

Use the [installation guide](../installation.md) for current host prerequisites and supported installation paths. Keep client/platform support decisions separate from the plugin's scholarly capabilities; consult the [compatibility guide](../compatibility.md).

## Install

Install `cal@agora` through a supported Agora host. Follow the [short installation path](../installation.md) rather than copying host UI steps from this page.

## First success

> Use `cal_lexicon_lookup` with query `br` and lemma_key `br N`. Report the returned `found` status, exact entry and CAL provenance, or distinguish a genuine CAL upstream error. Do not expand this into a vocabulary crawl.

Follow the [first-success walkthrough](../first-success/cal.md) for a short post-installation workflow, expected success signal, and interpretation limits.

## Typical research tasks

Use the published [CAL-MCP integration guide](https://github.com/alexsosn/CAL-MCP/blob/v0.1.0/docs/integrations/standalone-mcp.md) and the [Agora CAL research handoff](../../../plugins/cal/README.md). Keep lexical ambiguity, citation, editorial status and remote service provenance visible.

See the [human scholarly guidance](../scholarly-guidance.md) for direct links to source-specific research-method sections maintained with the agent skills.

Canonical capabilities:

- **Dictionary lookup** (`dictionary-lookup`)
- **Lexeme lookup** (`lexeme-lookup`)
- **Passage retrieval** (`passage-retrieval`)
- **Structured search** (`structured-search`)

## Important limitations

The generated Codex stdio path is verified by one observed CAL found/provenance lookup, while Claude integration remains community and aggregate plugin status is community. Neither guarantees remote CAL availability. CAL data/terms are upstream-dependent and not relicensed by MIT. One found lexeme does not establish exhaustive corpus coverage.

Registered plugin-level advisories:

No structured plugin-level known issues are currently registered.

## Disk, memory, and network

The canonical runtime is local while scholarly data are remote; normal provider operations require network access. A successful lexicon lookup normally makes two real CAL requests: one browse GET and one entry GET. The upstream client enforces request pacing, rolling caps and a cooldown after CAL 429. Do not use multi-page sweeps or unchecked retries.

## Provenance and licensing

The plugin registry records:

- `software`: `MIT`
- `data`: `upstream-dependent`
- `service_terms`: `upstream-dependent`

These fields describe the plugin/software/service boundary. Corpus, edition, annotation, or hosted-data rights can remain resource- or upstream-specific.

## Troubleshooting

Start from [symptom-based troubleshooting](../troubleshooting.md), with [compatibility and known limitations](../compatibility.md#current-upstream-limitations) for client and upstream boundaries.

For HTTP 429, upstream outages, or CAL token/lexicon errors, see [remote lookup recovery](../troubleshooting.md#remote-lookup-fails); do not retry aggressively.

## Upstream

- Repository: https://github.com/alexsosn/CAL-MCP
- Homepage/docs: https://github.com/alexsosn/CAL-MCP/releases/tag/v0.1.0
