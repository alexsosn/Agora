# Installing Agora

Agora currently targets **Claude Code** and **ChatGPT/Codex**. The repository contains both marketplace formats at the repository root:

- `.claude-plugin/marketplace.json`
- `.agents/plugins/marketplace.json`

The marketplace ID is `agora`. The prospective v1.1 scope offers five plugins: `context-fabric`, `perseus`, `sefaria`, `sedra` and `cal`. The published v1.0 scope had four.

Client behavior changes quickly, so this document records the currently supported flows rather than inventing a common installer that neither platform provides.

## Claude Code

Claude Code can add a GitHub marketplace directly by `owner/repo` shorthand.

Inside Claude Code:

```text
/plugin marketplace add alexsosn/Agora
```

Then install whichever Agora plugins you need:

```text
/plugin install context-fabric@agora
/plugin install perseus@agora
/plugin install sefaria@agora
/plugin install sedra@agora
/plugin install cal@agora
```

Run:

```text
/reload-plugins
```

after installation or after pulling plugin updates into the current session.

You can also use the non-interactive Claude CLI equivalents:

```bash
claude plugin marketplace add alexsosn/Agora
claude plugin install context-fabric@agora
claude plugin install perseus@agora
claude plugin install sefaria@agora
claude plugin install sedra@agora
claude plugin install cal@agora
```

To inspect the installed marketplace/plugin state, use `/plugin` in Claude Code. Agora skills are discovered automatically from each plugin root's `skills/<name>/SKILL.md` directories and appear under the plugin namespace.

For local validation of a checkout, Claude documents:

```bash
claude plugin validate .
```

The generated `.claude-plugin/marketplace.json` deliberately contains only fields accepted by Claude's strict marketplace schema.

## ChatGPT / managed Codex workspace import

Where workspace GitHub marketplace import is available, an administrator can import Agora from `https://github.com/alexsosn/Agora`. The marketplace manifest is at the repository root, so leave Path empty; the default branch is `main`. Follow the [official GitHub marketplace import and sync guide](https://help.openai.com/en/articles/20001504-importing-and-syncing-plugin-marketplaces-from-github) for current UI, permissions, rollout and import diagnostics.

GitHub marketplace sync imports plugin content; it does not grant access to unrelated external accounts or bypass workspace policy.

Agora plugins declare MCP servers. Current GitHub-imported MCP plugins can therefore be labeled **Desktop only**, even when part of the underlying service is remote. A Desktop-only plugin cannot run in ChatGPT web. This is a product/runtime distinction, not an Agora verification failure.

Availability of marketplace import, plugin installation, and particular surfaces depends on the current ChatGPT/Codex plan, workspace, role, and rollout.

Local checkout and Codex plugin development commands are in the [local development setup](development-setup.md) guide; they are not required for ordinary researcher installation.

## Runtime prerequisites

Agora intentionally does not vendor third-party runtimes or corpora.

### `uv`

The current local MCP launch configurations use `uv`/`uvx`:

- Context-Fabric uses `uv run` against the bundled plugin project;
- Perseus uses `uvx` to run pinned upstream `perseus-mcp==1.0.2`;
- Codex's Sefaria bridge uses `uvx` with pinned `mcp-proxy==0.12.0` and its MCP-SDK compatibility constraint;
- SEDRA uses `uv run` against the bundled adapter project.

Install `uv` using Astral's supported installation method for your operating system if it is not already available on `PATH`.

### Python

The Context-Fabric plugin currently requires Python 3.13. The SEDRA adapter and published `cal-mcp==0.1.0` require Python 3.11 or later. `uv` can manage project Python environments, but a compatible interpreter must be obtainable on the machine.

### Network access

Network access is needed for:

- initial acquisition of a Context-Fabric corpus that is not cached locally;
- live Perseus/Scaife access;
- Sefaria's hosted MCP endpoint;
- SEDRA IV API lookups.

Context-Fabric corpus data remains external to Agora and is acquired lazily only when selected.

## What to install for a task

You do not need all five plugins for every project.

- Install **Context-Fabric** for local structured querying of registered Text-Fabric corpora and collection members.
- Install **CAL** to use the published CAL-MCP local stdio server for remote CAL lexical, text and bibliography research. For a bounded first use, see the [CAL lexicon walkthrough](first-success/cal.md); a successful generated Codex path is observed, while the Claude client path remains community.
- Install **Perseus** for live Classics discovery, passage retrieval, and Scaife-backed search.
- Install **Sefaria** for Jewish texts, translations, links/commentaries, dictionaries, topics, and manuscript resources exposed by the official Sefaria MCP.
- Install **SEDRA** for Syriac word-form and lexeme lookup against SEDRA IV.

Installing Context-Fabric does not download all 37 registered resources. Corpus acquisition is lazy.

## Context-Fabric first load and cache

For an unfamiliar or potentially large corpus, use `describe_available_corpus` → `prepare_corpus` → `load_corpus` instead of jumping directly to a cold load. `prepare_corpus` exposes acquisition/materialization work and, where relevant, load preflight information before compilation.

Agora's Context-Fabric cache defaults to `~/.cache/agora/context-fabric`. Set `AGORA_CORPUS_CACHE` in the server environment to choose another cache root.

Use `corpus_cache_status` to inspect managed cache usage, active loads, leases, and limits. Do not blindly retry a slow cold load when the same load is already active. After a corpus is no longer loaded, `prune_corpus_cache` can reclaim unused cache objects, while `remove_cached_corpus` targets unused objects for a selected resource.

See [Context-Fabric cache and cold-load safety](context-fabric-cache.md) for progress stages, acquisition/compile limits, cancellation, module-overlay costs, and detailed cleanup behavior.

## Verification after installation

Agora records verification per **client and transport**, rather than treating one successful MCP connection as proof of all launch paths. Representative-operation live checks exercise the generated Claude Code and Codex paths independently, while bounded Context-Fabric/SEDRA platform checks verify startup only on Linux x86_64, Intel macOS x86_64, and Windows x86_64.

The platform startup cells are not end-to-end Claude Code or Codex executable tests and do not make claims about ARM, Apple Silicon, or other operating systems. Deterministic checks separately validate generated configuration structure and registry bindings.

See [compatibility and verification](compatibility.md) for the exact check IDs, transport differences such as Sefaria's Claude direct SSE versus Codex `stdio-via-sse-proxy`, current provider limitations, and the evidence boundaries behind each status.

These integration checks do **not** mean that every underlying scholarly resource has Verified data quality. Consult resource status and the plugin's scholarly skills before using a corpus for research conclusions.

## Updating

For Claude Code, refresh the marketplace with:

```text
/plugin marketplace update agora
```

and reload plugins after updates when prompted.

For a managed ChatGPT/Codex GitHub marketplace, workspace administrators can use **Sync now** in the marketplace settings; automatic daily sync is also available for imported marketplaces.

For a local Codex checkout, pull the repository and reinstall/refresh the plugin using the local marketplace flow supported by your current Codex build.

## Removing

Remove one plugin through the host rather than deleting Agora files or caches manually.

For Claude Code, for example:

```bash
claude plugin uninstall context-fabric@agora
```

Inside Claude Code, the corresponding `/plugin uninstall ...` flow can be used as well. Replace `context-fabric` with the plugin you installed.

For local Codex:

```bash
codex plugin remove context-fabric@agora
```

Removing an entire marketplace is broader than removing one plugin and should be used only when you intend to remove all Agora plugins installed from that marketplace.

In a managed ChatGPT/Codex workspace, use the workspace's plugin availability and installation policy controls for an individual plugin. That is distinct from deleting the imported marketplace: deleting the marketplace is a workspace-level action that removes every plugin imported from that marketplace.

Removing a plugin does not imply deleting Context-Fabric corpus cache data. Use the Context-Fabric cache tools described above when you actually want to reclaim corpus data.

## Troubleshooting

Start from the observed error in [troubleshooting by symptom](troubleshooting.md). It covers visibility, startup, runtimes, provider outages, cold loads, disk usage, known search limitations and client differences. For the exact path verified in each host, see [compatibility](compatibility.md).
