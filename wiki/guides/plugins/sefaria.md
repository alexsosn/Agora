# Sefaria

Search and retrieve Jewish texts and linked resources through the official Sefaria Texts MCP.

## Use this plugin for

- **Passage retrieval** (`passage-retrieval`)
- **Full text search** (`full-text-search`)
- **Reference resolution** (`reference-resolution`)
- **Linked text navigation** (`linked-text-navigation`)
- **Dictionary lookup** (`dictionary-lookup`)

## Access and resources

The plugin connects to Sefaria's official hosted Texts MCP and remote Sefaria Library. It does not install a local copy of the library.

## What connects or runs

Claude connects directly to Sefaria's hosted Texts MCP over SSE; Codex bridges the legacy SSE endpoint to stdio with mcp-proxy 0.12.0 constrained to MCP SDK 1.x compatibility because current Codex plugin MCP support does not accept legacy SSE directly.

## Local and remote behavior

Runtime mode: `hosted`.
Data mode: `remote`.

## Prerequisites

Use the [installation guide](../installation.md) for current host prerequisites and supported installation paths. Keep client/platform support decisions separate from the plugin's scholarly capabilities; consult the [compatibility guide](../compatibility.md).

## Install

Install `sefaria@agora` through a supported Agora host. Follow the [short installation path](../installation.md) rather than copying host UI steps from this page.

## First success

> Retrieve Genesis 1:1 in Hebrew and English and show linked classical commentaries for the verse.

This is a bounded starting request, not a full tutorial. The first-success tutorial workstream can expand it without changing this page's capability contract.

## Typical research tasks

For agent-side reference, search, and linked-text guidance, see the [Sefaria research skill](../../../plugins/sefaria/skills/sefaria-research/SKILL.md).

Canonical capabilities:

- **Passage retrieval** (`passage-retrieval`)
- **Full text search** (`full-text-search`)
- **Reference resolution** (`reference-resolution`)
- **Linked text navigation** (`linked-text-navigation`)
- **Dictionary lookup** (`dictionary-lookup`)

## Important limitations

Search can return duplicate references from separately indexed versions. Treat them as ambiguous search hits, not as an exact occurrence count; retrieve the selected reference/version before quantitative interpretation.

Registered plugin-level advisories:

- `sefaria/search-version-duplicates` — Sefaria book search can surface separate indexed-version hits for the same reference while current MCP result rows omit version identity, so row counts must not be interpreted as exact textual occurrence counts.

## Disk, memory, and network

The canonical runtime is hosted and scholarly data are remote; normal provider operations require network access.

## Provenance and licensing

The plugin registry records:

- `software`: `MIT`
- `data`: `upstream-dependent`
- `service_terms`: `upstream-dependent`

These fields describe the plugin/software/service boundary. Corpus, edition, annotation, or hosted-data rights can remain resource- or upstream-specific.

## Troubleshooting

Start from the observed symptom in [installation troubleshooting](../installation.md#troubleshooting). For current client/platform evidence and structured advisories, use [compatibility and known limitations](../compatibility.md#current-upstream-limitations).

## Upstream

- Repository: https://github.com/Sefaria/sefaria-mcp
- Homepage/docs: https://developers.sefaria.org/docs/the-sefaria-mcp
- Service endpoint: https://mcp.sefaria.org/sse
