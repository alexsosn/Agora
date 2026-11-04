# Nabu

Search, read, align, and cite a locally built Nabu library of ancient-text corpora through its read-only MCP server.

## Use this plugin for

- **Full text search** (`full-text-search`)
- **Passage retrieval** (`passage-retrieval`)
- **Reference resolution** (`reference-resolution`)
- **Dictionary lookup** (`dictionary-lookup`)
- **Lexeme lookup** (`lexeme-lookup`)
- **Linked text navigation** (`linked-text-navigation`)

## Access and resources

Nabu is a user-local Ruby runtime: the user clones [arvicco/nabu](https://github.com/arvicco/nabu), builds their own library (`bin/nabu quickstart`, then enable/sync per source), and sets `NABU_HOME` so the generated launch finds the checkout. Agora vendors no runtime and no corpus data; the read-only MCP server serves only what that user's library holds.

## What connects or runs

Nabu is a local-first Ruby 3.3+ application; the user clones arvicco/nabu, runs bundle install, and builds their own library (bin/nabu quickstart, then enable/sync per source) before launching. Both launch paths resolve the checkout through a NABU_HOME environment variable the user must set; Agora vendors no runtime and no corpus data, and nothing is hosted. The server is read-only by construction (SQLITE_OPEN_READONLY, no write tools) and serves only what the user's own library holds.

## Local and remote behavior

Runtime mode: `local`.
Data mode: `local`.
Runtime type: `ruby`.

## Prerequisites

Use the [installation guide](../installation.md) for current host prerequisites and supported installation paths. Keep client/platform support decisions separate from the plugin's scholarly capabilities; consult the [compatibility guide](../compatibility.md).

## Install

Install `nabu@agora` through a supported Agora host. Follow the [short installation path](../installation.md) rather than copying host UI steps from this page.

## First success

> Call `nabu_status` and report which sources the library actually holds, then run one `nabu_search` for a term in a held source and cite one result's URN and license class. An empty catalog is a correct answer for an unbuilt library, not an error.

Follow the [first-success walkthrough](../first-success/nabu.md) for a short post-installation workflow, expected success signal, and interpretation limits.

## Typical research tasks

Use the [plugin README](../../../plugins/nabu/README.md) for the tool table and upstream's own [MCP documentation](https://github.com/arvicco/nabu/blob/main/docs/mcp.md). Every result carries its per-document license class (open / attribution / nc) — keep it attached when quoting.

See the [human scholarly guidance](../scholarly-guidance.md) for direct links to source-specific research-method sections maintained with the agent skills.

Canonical capabilities:

- **Full text search** (`full-text-search`)
- **Passage retrieval** (`passage-retrieval`)
- **Reference resolution** (`reference-resolution`)
- **Dictionary lookup** (`dictionary-lookup`)
- **Lexeme lookup** (`lexeme-lookup`)
- **Linked text navigation** (`linked-text-navigation`)

## Important limitations

Verification is experimental on both clients: the deterministic checks cover the generated launch metadata, and the bounded startup smoke (`scripts/smoke_nabu_user_local.py`) runs only on the operator's machine, because a user-local environment exists nowhere else. Coverage varies per install — `nabu_status` is the ground truth, never the upstream site's headline figures.

Registered plugin-level advisories:

No structured plugin-level known issues are currently registered.

## Disk, memory, and network

The canonical runtime and data mode are local; disk and memory use depend on the selected corpus and cache state. All queries are local reads against the user's SQLite catalog; nothing calls out to the network. The expensive step is the user's own library build, which happens outside Agora entirely.

## Provenance and licensing

The plugin registry records:

- `software`: `MIT`
- `data`: `resource-specific`

These fields describe the plugin/software/service boundary. Corpus, edition, annotation, or hosted-data rights can remain resource- or upstream-specific.

## Troubleshooting

Start from [symptom-based troubleshooting](../troubleshooting.md), with [compatibility and known limitations](../compatibility.md#current-upstream-limitations) for client and upstream boundaries.

If the server fails to start, run the bounded startup smoke (`NABU_HOME=/path/to/nabu python3 scripts/smoke_nabu_user_local.py`) — it names the failing step. Empty results usually mean the user's library has not synced that source (`bin/nabu status` in the checkout shows coverage).

## Upstream

- Repository: https://github.com/arvicco/nabu
- Homepage/docs: https://arvicco.github.io/nabu
