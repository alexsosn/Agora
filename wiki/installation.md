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

Agora plugins declare MCP servers. Current ChatGPT marketplace imports can therefore be labeled **Desktop only**, even when part of the underlying service is remote. This is a product/runtime distinction, not an Agora verification failure.

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
- Install **Perseus** for live Classics discovery, CTS navigation, passage retrieval, and Scaife search.
- Install **Sefaria** for Jewish texts, translations, links/commentaries, dictionaries, topics, and manuscript resources exposed by the official Sefaria MCP.
- Install **SEDRA** for Syriac word-form and lexeme lookup against SEDRA IV.

Installing Context-Fabric does not download all 36 registered resources. Corpus acquisition is lazy.

## Verification after installation

Agora CI verifies all four v0.1 plugin integrations by starting/connecting through their generated Codex MCP configuration, initializing MCP, enumerating expected tools, and executing a representative operation. The Context-Fabric source audit separately verifies that all 36 registered v0.1 upstream resources currently resolve to Text-Fabric dataset roots.

These integration checks do **not** mean that every underlying scholarly resource has Verified data quality. Consult resource status and the plugin's scholarly skills before using a corpus for research conclusions.

## Updating

For Claude Code, refresh the marketplace with:

```text
/plugin marketplace update agora
```

and reload plugins after updates when prompted.

For a managed ChatGPT/Codex GitHub marketplace, workspace administrators can use **Sync now** in the marketplace settings; automatic daily sync is also available for imported marketplaces.

For a local Codex checkout, pull the repository and reinstall/refresh the plugin using the local marketplace flow supported by your current Codex build.
