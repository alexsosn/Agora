# Installing Agora

Agora currently targets **Claude Code** and **ChatGPT/Codex**. The repository contains both marketplace formats at the repository root:

- `.claude-plugin/marketplace.json`
- `.agents/plugins/marketplace.json`

The marketplace ID is `agora`. The four v0.1 plugins are `context-fabric`, `perseus`, `sefaria`, and `sedra`.

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
```

To inspect the installed marketplace/plugin state, use `/plugin` in Claude Code. Agora skills are discovered automatically from each plugin root's `skills/<name>/SKILL.md` directories and appear under the plugin namespace.

For local validation of a checkout, Claude documents:

```bash
claude plugin validate .
```

The generated `.claude-plugin/marketplace.json` deliberately contains only fields accepted by Claude's strict marketplace schema.

## ChatGPT / managed Codex workspace import

Where GitHub marketplace import is available to your workspace, an administrator can import Agora directly from GitHub:

1. Open **Workspace settings → Plugins**.
2. Choose **Add → Import marketplace**.
3. Set **Source** to `https://github.com/alexsosn/Agora`.
4. Leave **Path** empty because `.agents/plugins/marketplace.json` is at the repository root.
5. Leave the branch empty to track the default `main` branch, or explicitly enter `main`.
6. Import the marketplace and review the four imported plugins and their installation policies.

GitHub marketplace sync imports plugin content; it does not grant access to unrelated external accounts or bypass workspace policy.

Agora plugins declare MCP servers. Current GitHub-imported MCP plugins can therefore be labeled **Desktop only**, even when part of the underlying service is remote. A Desktop-only plugin cannot run in ChatGPT web. This is a product/runtime distinction, not an Agora verification failure.

Availability of marketplace import, plugin installation, and particular surfaces depends on the current ChatGPT/Codex plan, workspace, role, and rollout.

## Local Codex development/testing

Codex supports repo/team marketplaces at `<repo-root>/.agents/plugins/marketplace.json`. A local Agora clone therefore already has the expected marketplace layout.

Clone Agora:

```bash
git clone https://github.com/alexsosn/Agora.git
cd Agora
```

For a non-default local marketplace, current Codex tooling supports adding the marketplace root and then installing a plugin from its marketplace name:

```bash
codex plugin marketplace add /absolute/path/to/Agora
codex plugin add context-fabric@agora
```

Repeat the `codex plugin add ...@agora` command for `perseus`, `sefaria`, or `sedra` as needed.

After reinstalling or updating a local plugin, start a new Codex thread when necessary so the updated skill/MCP package is picked up cleanly.

For user-wide local plugin development, Codex also supports the default personal marketplace at `~/.agents/plugins/marketplace.json`; a marketplace entry's `source.path` is resolved relative to that marketplace root. Agora does not overwrite or manage a user's personal marketplace file automatically.

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

The Context-Fabric plugin currently requires Python 3.13. The SEDRA adapter requires Python 3.11 or later. `uv` can manage project Python environments, but a compatible interpreter must be obtainable on the machine.

### Network access

Network access is needed for:

- initial acquisition of a Context-Fabric corpus that is not cached locally;
- live Perseus/Scaife access;
- Sefaria's hosted MCP endpoint;
- SEDRA IV API lookups.

Context-Fabric corpus data remains external to Agora and is acquired lazily only when selected.

## What to install for a task

You do not need all four plugins for every project.

- Install **Context-Fabric** for local structured querying of registered Text-Fabric corpora and collection members.
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

In a managed ChatGPT/Codex workspace, **Disable plugin is not the same as uninstall**. Use the workspace's plugin installation/removal controls when they are available. Removing the imported marketplace is a workspace-level action affecting all plugins sourced from it, not the normal way to remove one Agora plugin.

Removing a plugin does not imply deleting Context-Fabric corpus cache data. Use the Context-Fabric cache tools described above when you actually want to reclaim corpus data.

## Troubleshooting

- **`uv` or `uvx` is missing:** install `uv` with Astral's supported installer and confirm it is on `PATH`, then retry the plugin launch.
- **Python cannot be resolved:** Context-Fabric requires **Python 3.13** and SEDRA requires Python 3.11 or later. Make sure `uv` can obtain a compatible interpreter rather than editing generated launch commands.
- **A remote lookup fails:** Perseus/Scaife, Sefaria, and SEDRA depend on network/provider availability. Preserve the provider error and check network/service status; reinstalling the plugin does not repair an unavailable upstream service.
- **A Context-Fabric corpus is slow to acquire or compile:** use `describe_available_corpus` → `prepare_corpus` → `load_corpus`, inspect `corpus_cache_status`, and do not start duplicate blind retries. See the [cache guide](context-fabric-cache.md) for bounded acquisition/compile behavior and cancellation.
- **The plugin is unavailable in the current ChatGPT surface:** imported MCP plugins may be **Desktop only** and therefore unavailable in ChatGPT web. Client/platform evidence is intentionally limited; in particular, current local-runtime platform checks cover Linux x86_64, Intel macOS x86_64, and Windows x86_64, not Apple Silicon. Check [compatibility and verification](compatibility.md) before treating an unlisted platform as supported.
