# Perseus MCP

Access Perseus and Scaife text discovery, CTS passages, and search through tonyjurg/Perseus-mcp.

## Use this plugin for

- **Corpus discovery** (`corpus-discovery`)
- **Passage retrieval** (`passage-retrieval`)
- **Full text search** (`full-text-search`)

## Access and resources

The local plugin connects to remote Perseus and Scaife scholarly text services. There is no Agora-managed local corpus catalog for this plugin.

## What connects or runs

Claude and Codex launch the upstream perseus-mcp 1.0.2 package directly through uvx; Agora does not vendor or fork the server. Intel macOS additionally constrains cryptography below 43 because no CPython macOS x86_64 wheel is published after 42.x.

## Local and remote behavior

Runtime mode: `local`.
Data mode: `remote`.
Runtime type: `python`.

## Prerequisites

Use the [installation guide](../installation.md) for current host prerequisites and supported installation paths. Keep client/platform support decisions separate from the plugin's scholarly capabilities; consult the [compatibility guide](../compatibility.md).

## Install

Install `perseus@agora` through a supported Agora host. Follow the [short installation path](../installation.md) rather than copying host UI steps from this page.

## First success

> Discover Homer, resolve an Iliad edition in the service that exposes it, retrieve Iliad 1.1, and report the exact discovered URN and service path.

This is a bounded starting request, not a full tutorial. The first-success tutorial workstream can expand it without changing this page's capability contract.

## Typical research tasks

For agent-side source and routing guidance, see the [Perseus research skill](../../../plugins/perseus/skills/perseus-research/SKILL.md).

Canonical capabilities:

- **Corpus discovery** (`corpus-discovery`)
- **Passage retrieval** (`passage-retrieval`)
- **Full text search** (`full-text-search`)

## Important limitations

Passage retrieval and Scaife-backed discovery/search remain separate supported paths. Provider-wide CTS navigation is not advertised: legacy CTS metadata/navigation can fail, and merged discovery can include Scaife-only works that CTS resource lookup does not resolve.

Registered plugin-level advisories:

- `perseus/cts-scaife-inventory-routing` — Merged CTS/Scaife author discovery may return Scaife-only works; CTS get_author_resources/get_work_resources can report no match even when Scaife-native tools can retrieve the work.
- `perseus/legacy-cts-malformed-navigation` — perseus-mcp 1.0.2 does not validate malformed legacy CTS GetLabel/GetValidReff responses at the provider boundary, so metadata and derived navigation helpers can fail for otherwise valid discovered editions.

## Disk, memory, and network

The canonical runtime is local while scholarly data are remote; normal provider operations require network access.

## Provenance and licensing

The plugin registry records:

- `software`: `MIT`
- `data`: `upstream-dependent`

These fields describe the plugin/software/service boundary. Corpus, edition, annotation, or hosted-data rights can remain resource- or upstream-specific.

## Troubleshooting

Start from the observed symptom in [installation troubleshooting](../installation.md#troubleshooting). For current client/platform evidence and structured advisories, use [compatibility and known limitations](../compatibility.md#current-upstream-limitations).

## Upstream

- Repository: https://github.com/tonyjurg/Perseus-mcp
