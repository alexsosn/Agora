# Research: optimal ChatGPT and Codex compatibility for Agora

**Status:** research only  
**Date:** 2026-09-03  
**Scope:** OpenAI plugin/App/MCP compatibility and Agora packaging. No implementation is authorized by this document.

## Research question

How should Agora expose heterogeneous scholarly tools through one centralized marketplace while remaining as thin as possible and maximizing compatibility with both ChatGPT and Codex?

The desired user experience is:

- add or import Agora once;
- discover many research integrations from that central catalog;
- install only the integrations needed for a task;
- reuse upstream MCP servers, services, APIs, and skills instead of copying their behavior into Agora;
- support local scholarly tools where local execution is intrinsic to the use case;
- avoid operating a central Agora backend or proxy unless no thinner architecture exists.

This research is subordinate to [`ref-plugin-boundary.md`](../architecture/ref-plugin-boundary.md). Any implementation must preserve that ownership boundary.

## Sources checked

Primary OpenAI sources, checked on 2026-09-03:

- [Package your plugin](https://developers.openai.com/plugins/build/plugins)
- [Plugins in ChatGPT and Codex](https://help.openai.com/en/articles/20001256-plugins-in-codex/)
- [Importing and syncing plugin marketplaces from GitHub](https://help.openai.com/en/articles/20001504)
- [Developer mode and MCP apps in ChatGPT](https://help.openai.com/en/articles/12584461-developer-mode-apps-and-full-mcp-connectors-in-chatgpt-beta)
- [OpenAI plugin examples](https://github.com/openai/plugins)
- [OpenAI Codex marketplace implementation/tests](https://github.com/openai/codex)

Agora sources inspected:

- `registry/plugins.yaml`
- `registry/schema/plugins.schema.json`
- `scripts/generate_marketplaces.py`
- `.agents/plugins/marketplace.json`
- `plugins/*/.codex-plugin/plugin.json`
- `plugins/*/.codex-plugin/mcp.json`
- current plugin skill directories
- `wiki/guides/installation.md`
- `wiki/architecture/ref-plugin-boundary.md`

Upstream integrations inspected where relevant:

- `tonyjurg/Perseus-mcp`
- Sefaria hosted MCP metadata already recorded by Agora
- Agora Context-Fabric and SEDRA adapter packages

## Current OpenAI plugin model

OpenAI currently treats a plugin as a package with a required `.codex-plugin/plugin.json` manifest and optional companion components. The documented package model includes:

- `skills/` for reusable workflows;
- `.app.json` for mappings to registered MCP server connections;
- `.mcp.json` for MCP servers distributed with the plugin;
- optional assets and hooks.

OpenAI states that only `plugin.json` belongs inside `.codex-plugin/`; `skills/`, `.app.json`, `.mcp.json`, hooks, and assets belong at the plugin root.

The manifest can explicitly point to these components with fields such as:

```json
{
  "skills": "./skills/",
  "mcpServers": "./.mcp.json",
  "apps": "./.app.json"
}
```

`apps` is a compatibility field for registered MCP-server mappings. The underlying primitive remains the MCP connection.

Public plugins are published to a universal directory shared by ChatGPT and Codex. Local and repository marketplaces are separate authoring/team-distribution mechanisms and may have different surface availability.

## Marketplace import already matches Agora well

OpenAI supports importing a GitHub marketplace whose selected directory contains `.agents/plugins/marketplace.json`. Workspace admins can import the repository URL, and imported marketplaces are automatically checked for changes daily. Manual `Sync now` is also supported.

Agora already has the required root path:

```text
.agents/plugins/marketplace.json
```

The current file names the marketplace `agora` and lists the four v0.1 plugin packages as local paths inside the repository. This is already a native OpenAI marketplace layout; Agora does not need a custom marketplace service for ChatGPT/Codex discovery.

The current central-catalog idea can become even thinner. OpenAI documents Git-backed marketplace sources:

- `source: "url"` when the plugin lives at a repository root;
- `source: "git-subdir"` when it lives in a repository subdirectory;
- optional `ref` pinning.

GitHub marketplace import likewise states that marketplace entries may reference plugin folders in other supported GitHub repositories. This allows Agora to remain the catalog while plugin packages progressively move upstream.

A desirable long-term pattern is therefore:

```text
Agora marketplace
  -> upstream plugin package A
  -> upstream plugin package B
  -> Agora-owned temporary wrapper C
```

The wrapper remains only where upstream has not yet adopted compatible packaging.

## Current Agora OpenAI packaging

Agora's canonical plugin schema currently models runtime launch configuration by client:

```yaml
runtime:
  launch:
    claude: ...
    codex: ...
```

Verification similarly requires exactly `claude` and `codex` client entries.

`scripts/generate_marketplaces.py` turns every OpenAI plugin into a package whose manifest contains:

```json
"mcpServers": "./.codex-plugin/mcp.json"
```

and writes the server configuration under:

```text
plugins/<id>/.codex-plugin/mcp.json
```

This design has two separate issues.

### 1. Packaging layout diverges from the current OpenAI convention

Current OpenAI documentation says only `plugin.json` belongs inside `.codex-plugin/` and places `.mcp.json` at plugin root. Manifest component paths can be explicit, so the existing path may be accepted by some clients, but it is not the documented target layout and should not be treated as the canonical design going forward.

### 2. Bundled MCP declarations make GitHub-imported plugins Desktop-only in ChatGPT

This is the main compatibility constraint.

OpenAI explicitly documents that an imported plugin can receive the **Desktop only** label when it declares an MCP server in `mcp.json` or `.mcp.json`, even when that MCP server is a remote HTTPS endpoint. A Desktop-only plugin cannot run in ChatGPT on the web.

OpenAI also explicitly states that adding `.app.json` does **not by itself** remove that restriction. Therefore a package intended for ChatGPT Web cannot simply keep the existing bundled-MCP declaration and add an App mapping next to it.

This means Agora currently conflates two different OpenAI delivery mechanisms:

1. a bundled/local MCP server useful for Codex and desktop/local execution;
2. a registered MCP connection/App needed for ChatGPT Web.

They should be modeled as bindings of one logical research integration, not as one unconditional runtime definition.

## `.app.json` is a reference, not a deployment mechanism

For ChatGPT-compatible App-backed plugins, OpenAI requires an already registered MCP server connection. During development, the MCP server is registered in ChatGPT developer mode, which produces a technical ID such as `plugin_asdk_app...`; `.app.json` maps a plugin-facing name to that ID.

Consequences:

- `.app.json` does not create or deploy an MCP server;
- it does not grant permissions or authentication;
- the App must already be available to the user's role/workspace;
- a workspace-specific custom App ID cannot safely be assumed to be globally reusable;
- Agora cannot turn an arbitrary local stdio MCP into a Web App merely by generating metadata.

This is an important limit on how much a marketplace can centralize installation today.

## ChatGPT Web and local MCP are fundamentally different deployment surfaces

ChatGPT developer-mode MCP Apps currently connect to remote MCP servers. OpenAI says ChatGPT cannot connect directly to a local MCP server.

For MCP servers on a developer machine, private network, or on-premises environment, OpenAI recommends Secure MCP Tunnel rather than exposing the service publicly.

This is particularly relevant to Context-Fabric, where local corpus acquisition, caching, local modifications, and potentially private datasets are legitimate requirements.

A reasonable Web path is therefore:

```text
ChatGPT Web
  -> registered workspace App
  -> Secure MCP Tunnel
  -> local/private Context-Fabric MCP
  -> local corpus cache
```

Agora can document or generate integration metadata for that path without operating the tunnel or corpus service itself.

## Mobile limitation

OpenAI's current developer-mode documentation states that MCP Apps are Web-only and are not available on mobile. This should be represented as a product-surface limitation rather than worked around inside Agora.

Agora should avoid inventing a mobile proxy architecture whose only purpose is to bypass a temporary product limitation.

## Skills

Agora already places skills under plugin-root `skills/` directories. Current OpenAI packaging documentation uses the same convention and recommends an explicit manifest entry:

```json
"skills": "./skills/"
```

Agora's generated OpenAI manifests currently omit the explicit `skills` field even when a plugin contains skills.

This omission is not evidence that the skills are unusable: component discovery and client behavior may find conventional paths. However, emitting the documented field is preferable because it makes package intent explicit and aligns generated artifacts with current OpenAI examples.

The existing Agora skill ownership rule should remain unchanged. Moving to the OpenAI plugin model does not justify adding substantive third-party behavior to Agora skills.

## Why the registry abstraction should change

The current canonical schema encodes `claude` and `codex` as launch targets. That worked when the principal distinction was client-specific MCP launch syntax. It becomes awkward once one OpenAI plugin may need several ways to reach the same upstream capability:

- local stdio MCP;
- remote HTTP/SSE MCP;
- transport bridge;
- registered OpenAI App reference;
- private remote connection through a tunnel.

These are connection/binding concerns, not separate scholarly plugins.

A better conceptual model is:

```text
logical plugin
  -> upstream capability/service
  -> one or more connections
  -> one or more client/surface bindings
```

For example:

```yaml
id: sefaria
connections:
  upstream-mcp:
    protocol: mcp
    ownership: upstream
    transport: sse
    url: https://mcp.sefaria.org/sse

bindings:
  openai-app:
    kind: registered-app
    connection: upstream-mcp

  codex-local:
    kind: bundled-mcp
    connection: upstream-mcp
    adapter: mcp-proxy
```

This separates stable research-service identity from temporary client transport workarounds.

## Package variants versus logical plugin identity

Because GitHub-imported plugins that declare bundled MCP servers can become Desktop-only, Agora should not assume that one generated OpenAI package can always optimize every surface simultaneously.

The registry should permit multiple package/binding projections from one logical integration. For example:

```text
Sefaria logical integration
  -> App-backed OpenAI package for ChatGPT Web / compatible Codex surfaces
  -> bundled/proxied MCP package only where local Codex needs it
```

Whether these projections should be separate marketplace entries, product-gated entries, generated artifacts, or one package selected differently by distribution channel should be decided experimentally against current OpenAI behavior before implementation. The research conclusion is only that the distinction must exist in the model.

## Official OpenAI examples and one important caveat

The public `openai/plugins` repository contains examples such as Figma and Notion whose manifests declare both `apps` and `mcpServers`. These examples demonstrate that a plugin package can represent both registered and bundled MCP integrations in the general plugin model.

They do **not** invalidate the GitHub-import limitation. OpenAI's help documentation specifically warns that GitHub-imported plugins declaring MCP servers can receive the Desktop-only label and that adding an App reference alone does not remove it. Public-directory distribution and GitHub-imported workspace distribution therefore must not be assumed to have identical surface behavior.

Agora should test the actual GitHub-import path it intends to support rather than infer behavior solely from public-directory examples.

## Per-plugin assessment

### Sefaria

Current Agora state:

- upstream hosted MCP endpoint is already recorded;
- Claude can connect directly to the hosted endpoint;
- Codex currently uses a local `mcp-proxy` bridge to convert the legacy SSE endpoint into the supported local path.

Assessment:

- strongest candidate for the first ChatGPT Web proof of concept;
- no Agora-hosted scholarly service is required;
- Web support should use a registered App pointing at the official upstream service where OpenAI's connection requirements permit it;
- the proxy should remain a client-specific fallback, not become part of Sefaria's logical identity.

### Perseus

Current Agora state:

- Agora launches upstream `perseus-mcp==1.0.2` directly with `uvx`;
- upstream currently runs its FastMCP server over the default stdio transport;
- Agora does not vendor the server.

Assessment:

- current local Codex integration is appropriately thin;
- ChatGPT Web requires a remotely reachable MCP connection, which upstream does not currently expose as Agora consumes it;
- preferred path is upstream remote/HTTP support or a user/workspace deployment, not an Agora-operated central Perseus gateway;
- an Agora-hosted service would materially expand project ownership and should require an explicit architecture decision.

### Context-Fabric

Current Agora state:

- local plugin runtime;
- lazy acquisition and cache of registered corpora;
- Agora-owned resource discovery/resolution tools around Context-Fabric MCP.

Assessment:

- local execution is a genuine product requirement rather than accidental packaging debt;
- Codex/local MCP remains a first-class path;
- ChatGPT Web should use a registered remote connection, with Secure MCP Tunnel as the natural path for local/private corpus use;
- Agora should not upload or centrally host users' corpora merely to obtain Web compatibility.

### SEDRA

Current Agora state:

- Agora contains a small read-only FastMCP adapter over SEDRA IV public JSON endpoints.

Assessment:

- this is the thickest of the four v0.1 integrations because Agora owns executable adapter code;
- it is consistent with the current thin-adapter policy only as integration glue;
- long term, a standalone/upstream `sedra-mcp` package would create a cleaner ownership boundary and let Agora reference it like Perseus;
- Web support should not cause more SEDRA domain behavior to accumulate in Agora.

## Federation opportunity

OpenAI's Git-backed marketplace source support enables a useful end state:

```text
                    Agora
          canonical registry + curation
                       |
           .agents/plugins/marketplace.json
                       |
      +----------------+----------------+
      |                |                |
 upstream repo A   upstream repo B   Agora wrapper C
```

This preserves centralized discovery while decentralizing code ownership.

The practical migration rule should be:

1. use an upstream plugin package when one exists and is compatible;
2. contribute standard OpenAI packaging upstream when maintainers accept it;
3. keep an Agora wrapper only when packaging/transport adaptation is necessary;
4. delete the wrapper when upstream/client support makes it redundant.

## What Agora should not build

This research does not support adding any of the following as a default architecture:

- a central Agora MCP gateway multiplexing every research service;
- an Agora-hosted copy of every local MCP server;
- a common semantic API across heterogeneous research tools;
- domain fixes for third-party plugins;
- a mobile-specific proxy intended only to bypass current ChatGPT mobile limitations;
- a proprietary installation service replacing OpenAI's GitHub marketplace support.

All of these increase ownership without being required for centralized discovery.

## Compatibility model recommended by the research

Compatibility should be expressed by product surface and binding rather than by vendor name alone.

A future compatibility matrix should be able to distinguish at least:

| Surface | Typical binding |
|---|---|
| Codex local/CLI | bundled/local MCP |
| Codex with registered connection | App/registered MCP where supported |
| ChatGPT Desktop | local/bundled MCP or registered App, depending on package/distribution |
| ChatGPT Web | registered App/remote MCP connection |
| ChatGPT Web to private/local MCP | registered App + Secure MCP Tunnel |
| ChatGPT mobile custom MCP | unsupported by current product |

The registry should record evidence for the exact surface/binding pair being claimed rather than a broad `codex: verified` flag that can be misread as Web compatibility.

## Findings

1. Agora already uses the correct centralized OpenAI marketplace path; no Agora marketplace backend is needed.
2. The present generator is optimized for local Codex and makes imported plugins poor ChatGPT Web packages because it unconditionally declares bundled MCP servers.
3. `.app.json` represents a registered MCP connection and cannot substitute for deployment, authorization, or workspace setup.
4. A bundled-MCP declaration and an App reference are different bindings and must not be collapsed into one unconditional package projection.
5. Current OpenAI package layout places only `plugin.json` under `.codex-plugin/`; Agora should eventually move generated MCP metadata to the documented root-level `.mcp.json` layout.
6. Agora should explicitly emit skill metadata in OpenAI manifests where skills are present.
7. Git-backed marketplace entries make upstream federation feasible while preserving one Agora catalog.
8. Sefaria is the best first Web pilot because the upstream service is already hosted.
9. Context-Fabric should remain local-first and use Secure MCP Tunnel for Web access where appropriate.
10. Perseus should stay upstream-first; Web hosting should preferably be solved upstream or by the user's deployment rather than by Agora.
11. SEDRA's adapter is a candidate for eventual extraction, not expansion inside Agora.
12. Mobile custom-MCP parity is currently blocked by the ChatGPT product surface and should be represented honestly rather than worked around.

## Open questions that require implementation experiments

- Does the desired combination of GitHub marketplace source, App availability, and workspace policy allow one App-backed package to install cleanly in both ChatGPT Web and current Codex surfaces without a bundled MCP fallback?
- What is the lifecycle and portability of App IDs for public versus workspace-private MCP connections?
- For one logical integration that needs both App-backed and bundled-MCP delivery, what packaging strategy gives the least confusing marketplace UX: separate entries, product-gated entries, or distribution-specific projections?
- Which existing scholarly upstreams are willing to accept `.codex-plugin/plugin.json` packaging directly so Agora can federate rather than wrap them?
- Which current Agora skill directories are discovered reliably without an explicit `skills` field across all target OpenAI surfaces?
- What exact CI signal can detect that a GitHub-imported plugin is Web-eligible rather than merely schema-valid?

These questions should be answered by narrow compatibility tests before changing the canonical registry schema.