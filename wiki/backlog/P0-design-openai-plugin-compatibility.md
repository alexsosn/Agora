# Plan: ChatGPT and Codex compatibility without thickening Agora

**Status:** design / implementation plan only  
**Date:** 2026-09-03  
**Depends on:** [`P0-research-openai-plugin-compatibility.md`](P0-research-openai-plugin-compatibility.md)  
**Normative boundary:** [`ref-plugin-boundary.md`](../architecture/ref-plugin-boundary.md)

## Objective

Make Agora a centralized marketplace from which research integrations can be discovered and installed with the least possible friction across ChatGPT and Codex, while keeping Agora limited to curation, metadata, packaging, compatibility, transport adaptation, resource discovery, and integration verification.

The implementation should make it easier to add scholarly tools without turning Agora into a hosted research platform.

## Non-goals

This plan does not authorize:

- hosting all third-party MCP servers behind an Agora gateway;
- creating a shared semantic API for heterogeneous research tools;
- fixing or extending upstream scholarly behavior;
- duplicating upstream server implementations;
- uploading local corpora to Agora infrastructure for Web compatibility;
- mobile-only proxy workarounds for current ChatGPT product limitations;
- replacing OpenAI's GitHub marketplace import with a custom installer.

## Design principles

### 1. One logical integration, multiple bindings

`sefaria`, `perseus`, `context-fabric`, and future services should remain stable logical plugin identities. Client-specific ways of reaching them are bindings.

For example:

```text
sefaria
  -> upstream hosted MCP
      -> registered OpenAI App binding
      -> local Codex SSE-to-stdio bridge binding
```

Do not create separate scholarly identities merely because a client needs a different transport.

### 2. Prefer registered/upstream capabilities over Agora wrappers

For each integration, prefer in order:

1. upstream plugin package that Agora can reference directly;
2. upstream MCP endpoint referenced through a registered App;
3. thin Agora packaging/transport adapter;
4. Agora-hosted service only after an explicit architecture decision.

### 3. Keep package projections disposable

Generated client packaging is not canonical truth. The registry is canonical; `.agents/plugins/marketplace.json`, `.codex-plugin/plugin.json`, `.app.json`, and `.mcp.json` are projections.

If OpenAI changes packaging rules, the registry should survive with minimal semantic change.

### 4. Compatibility claims are surface-specific

Do not use `codex: verified` as a proxy for all OpenAI surfaces.

Verification should eventually identify the tested product surface and binding, for example:

- `codex-local + bundled-mcp`;
- `chatgpt-web + registered-app`;
- `chatgpt-web + tunnel + registered-app`.

## Phase 0 — compatibility experiments before schema migration

Do not start by rewriting the registry schema. First establish the packaging behavior that the schema must represent.

### Experiment A: Sefaria App-backed Web plugin

Goal: prove the smallest Web-capable Agora integration using a service that is already hosted upstream.

Test package characteristics:

- `.codex-plugin/plugin.json`;
- `skills/` if useful;
- `.app.json` referencing a registered Sefaria MCP connection;
- **no bundled `mcpServers` declaration in the Web test package**.

Verify:

1. GitHub marketplace import succeeds.
2. The plugin is not classified Desktop-only solely because of its packaging.
3. The required App is surfaced correctly in workspace setup.
4. A user with access can retrieve a representative Sefaria passage from ChatGPT Web.
5. Installation does not require an Agora-hosted service.
6. The same logical integration remains usable in Codex through an appropriate binding.

Record the exact App-ID scope observed: public/stable, workspace-local, or otherwise constrained.

### Experiment B: bundled-MCP package behavior

Create the equivalent minimal local package with root `.mcp.json` and no App reference.

Verify current Codex behavior and confirm the expected Desktop-only ChatGPT Web classification after GitHub import.

This gives a regression fixture for the product distinction Agora must model.

### Experiment C: package containing both App and bundled MCP

Use a disposable test package, not a production integration.

Verify whether GitHub import remains Desktop-only as current OpenAI documentation states. This prevents assumptions based on public-directory Figma/Notion examples from leaking into Agora's GitHub-marketplace design.

### Experiment D: explicit skills manifest

For one minimal plugin with an existing skill, compare discovery with and without:

```json
"skills": "./skills/"
```

The implementation target should follow the documented explicit form regardless, but the test records compatibility behavior and protects against regressions.

### Exit criteria

Phase 0 is complete when Agora has a short evidence table containing:

- package shape;
- distribution path;
- target surface;
- observed status;
- tool/skill discovery result;
- reproducible setup steps.

No schema migration should merge before these observations exist.

## Phase 1 — define registry v2 concepts

Introduce a schema that separates scholarly identity, connection, binding, packaging, and verification.

The exact YAML syntax may differ, but the model should support the following concepts.

### `connections`

Describe the real service or executable boundary.

Candidate fields:

```yaml
connections:
  upstream-mcp:
    protocol: mcp
    ownership: upstream
    transport: sse
    url: https://example.org/mcp
```

For local servers:

```yaml
connections:
  local-mcp:
    protocol: mcp
    ownership: upstream
    transport: stdio
    command: uvx
    args: [...]
```

For Agora-owned integration glue, ownership must be explicit:

```yaml
ownership: agora-adapter
```

### `bindings`

Describe how a product surface consumes a connection.

Candidate kinds:

- `registered-app`;
- `bundled-mcp`;
- `transport-bridge`;
- `secure-mcp-tunnel` as deployment guidance/requirement rather than an Agora-owned service.

Example:

```yaml
bindings:
  openai-app:
    kind: registered-app
    connection: upstream-mcp

  codex-local:
    kind: transport-bridge
    connection: upstream-mcp
    output_transport: stdio
    adapter:
      package: mcp-proxy
      version: 0.12.0
```

### `surfaces`

Represent supported product surfaces separately from vendor identity.

Candidate values should be conservative and evidence-backed, for example:

- `codex-local`;
- `chatgpt-desktop`;
- `chatgpt-web`;
- `chatgpt-mobile`.

A surface entry references a binding rather than repeating launch details.

### `verification`

Replace or extend the current fixed `clients.claude/codex` structure with evidence per surface/binding pair.

A claim should answer:

- which package projection was tested;
- which surface was tested;
- which binding was used;
- whether verification is deterministic or live;
- which representative integration operation passed.

### Migration constraints

- preserve existing plugin IDs;
- preserve provider/resource relationships;
- preserve current v0.1 capability and license metadata;
- provide a deterministic migration from schema v1;
- do not embed workspace-specific App IDs into canonical records unless their portability is explicitly known;
- keep Claude support possible without forcing Claude semantics into OpenAI bindings.

## Phase 2 — refactor OpenAI artifact generation

After registry v2 is validated, change generation so package shape follows bindings rather than every OpenAI plugin receiving bundled MCP metadata.

### Root-level component layout

Generate current documented OpenAI structure:

```text
plugins/<id>/
  .codex-plugin/
    plugin.json
  skills/
  .app.json       # when a registered App binding is emitted
  .mcp.json       # when a bundled MCP binding is emitted
```

Only `plugin.json` should be generated under `.codex-plugin/`.

### Manifest generation

Emit component pointers only when the corresponding package projection actually includes the component.

Examples:

App-backed:

```json
{
  "skills": "./skills/",
  "apps": "./.app.json"
}
```

Bundled MCP:

```json
{
  "skills": "./skills/",
  "mcpServers": "./.mcp.json"
}
```

Do not automatically add both.

### Package projection decision

The generator must not guess which binding is Web-safe. That decision belongs in canonical metadata backed by Phase 0 evidence.

If a logical integration needs two incompatible package projections, choose the least confusing of these only after testing:

1. separate marketplace entries with explicit surface naming;
2. product-gated entries if OpenAI product policy supports the required distinction cleanly;
3. separate distribution-specific generated marketplaces.

Avoid duplicating plugin metadata by hand in any option.

## Phase 3 — add federated plugin sources

Extend Agora's canonical marketplace model so a plugin package can be sourced from another GitHub repository using the OpenAI-supported Git source forms.

Required source modes:

- local package in Agora;
- Git repository root;
- Git repository subdirectory;
- optional ref/SHA pinning where supported.

### Federation policy

Prefer an external source when all are true:

- the upstream repository intentionally contains compatible plugin packaging;
- the package exposes the same upstream capability Agora intends to list;
- Agora does not need to patch its substantive behavior;
- provenance/versioning is clear;
- Agora CI can still validate the integration contract.

Keep a local wrapper when:

- client-specific transport adaptation is still required;
- upstream packaging is absent and maintainers have not adopted it;
- Agora-owned resource discovery is itself part of the marketplace integration, as with current Context-Fabric behavior.

### Wrapper retirement

Every local wrapper around a third-party service should have an obvious deletion path. When upstream adopts equivalent packaging or the client removes the mismatch, Agora should migrate the marketplace source upstream and remove the wrapper.

## Phase 4 — plugin-by-plugin migration

### Sefaria: first Web-compatible pilot

Target state:

```text
Agora catalog
  -> Sefaria logical plugin
      -> official hosted MCP
      -> registered App binding for Web
      -> optional local bridge binding only where required
```

Tasks:

- register/test the upstream endpoint through the supported ChatGPT App flow;
- determine App-ID portability;
- generate an App-backed package projection;
- preserve the local Codex bridge only if current Codex requires it;
- verify Genesis 1:1 or another stable published operation on each claimed surface;
- keep all textual/search semantics upstream.

### Perseus: keep upstream-first

Target state:

- local Codex continues to launch upstream `perseus-mcp` directly while stdio is the upstream deployment model;
- investigate/contribute remote HTTP deployment support upstream if maintainers want it;
- if a user/workspace deploys a remote Perseus MCP, allow an App binding to reference that deployment;
- do not create an Agora-operated central Perseus service as a routine compatibility fix.

Any new scholarly capability belongs upstream.

### Context-Fabric: preserve local-first design

Target state:

- local Codex remains first-class;
- Web documentation supports remote deployment or Secure MCP Tunnel to the user's/private Context-Fabric MCP;
- corpus cache and acquisition remain outside Agora-hosted infrastructure;
- surface verification distinguishes local Codex from Web+tunnel rather than treating them as one status.

Do not require all Context-Fabric resources to become remote services.

### SEDRA: isolate adapter ownership

Short term:

- keep the current read-only adapter if needed for v0.1 compatibility;
- package it according to the new binding model;
- avoid adding any domain behavior.

Long term:

- propose/extract a standalone `sedra-mcp` project or upstream contribution;
- change Agora to reference that package through a federated source;
- remove executable SEDRA adapter code from Agora once equivalent upstream ownership exists.

## Phase 5 — compatibility validation and CI

Add tests only for Agora-owned integration contracts.

### Static tests

Validate:

- marketplace JSON against current expected structure;
- generated `plugin.json` paths;
- root placement of `.app.json` and `.mcp.json`;
- explicit `skills` references where skills exist;
- no stale generated files;
- federated source syntax and pins;
- declared surface -> binding references;
- Web-target package does not accidentally include a bundled MCP declaration when that would make the imported package Desktop-only.

### Live/acceptance tests

Where automation is possible, verify representative operations for each supported binding.

Examples:

- Sefaria App-backed Web: retrieve one stable passage;
- Sefaria local bridge: initialize MCP and retrieve one passage;
- Perseus local: discover Homer or retrieve one published passage;
- Context-Fabric local: initialize catalog and load/inspect one fixture/resource according to existing scope;
- SEDRA: execute one structurally stable word/lexeme lookup.

Do not assert linguistic correctness beyond what is necessary to prove the integration reaches the advertised upstream operation.

### Manual product-surface evidence

Some ChatGPT workspace/App behaviors may not be testable in ordinary CI. Record manual evidence with:

- date;
- plan/workspace type;
- package commit;
- App/binding type;
- import result;
- Desktop-only status;
- representative operation result.

Treat this evidence as product compatibility evidence, not a permanent guarantee.

## Phase 6 — documentation and UX

After implementation is proven, update user-facing installation guidance.

### Codex

Prefer direct remote marketplace registration rather than requiring a clone for normal use:

```text
codex plugin marketplace add alexsosn/Agora
```

Keep local clone instructions only for development/testing.

### Managed ChatGPT

Keep the existing one-time GitHub marketplace import flow:

```text
Workspace settings -> Plugins -> Add -> Import marketplace
Source: https://github.com/alexsosn/Agora
```

Then explain per-plugin setup:

- App-backed and Web-capable;
- Desktop/local only;
- requires workspace App registration;
- requires Secure MCP Tunnel/private deployment.

### Compatibility table

Generate or maintain a concise table from canonical metadata rather than prose claims:

| Plugin | Codex local | ChatGPT Web | ChatGPT Desktop | Mobile | Extra setup |
|---|---:|---:|---:|---:|---|
| Sefaria | evidence-backed | evidence-backed when App available | evidence-backed | current product limitation | App/auth as applicable |
| Perseus | evidence-backed | deployment-dependent | local | current product limitation | remote MCP for Web |
| Context-Fabric | evidence-backed | tunnel/deployment-dependent | local | current product limitation | local corpora/tunnel |
| SEDRA | evidence-backed | deployment-dependent | local | current product limitation | adapter deployment/App |

Do not populate statuses optimistically before tests exist.

## Security and privacy constraints

The compatibility redesign must preserve the following:

- marketplace import does not imply trust of every future upstream change;
- remote Git sources should be pinnable where reproducibility matters;
- App references must not embed credentials;
- workspace authorization remains controlled by OpenAI/provider mechanisms;
- Secure MCP Tunnel is preferable to public exposure for private/local scholarly resources;
- no corpus or user data should be relayed through Agora solely for installation convenience;
- write-capable future research tools require explicit action/permission review at the App level.

## Rollout order

Recommended sequence:

1. run Phase 0 experiments;
2. document observed compatibility matrix;
3. design schema v2 from those observations;
4. implement root-level OpenAI package projections;
5. land Sefaria App-backed proof of concept;
6. add federated Git source support;
7. migrate remaining v0.1 integrations without changing scholarly behavior;
8. update installation/compatibility documentation;
9. consider upstream PRs that let local Agora wrappers be removed.

The sequence intentionally delays schema churn until the OpenAI behavior is empirically confirmed.

## Acceptance criteria

The project-level compatibility work is successful when:

- Agora remains importable as one GitHub marketplace;
- a user/admin does not need an Agora-hosted account or service to use the marketplace;
- at least one hosted scholarly integration is demonstrated from ChatGPT Web through an App-backed Agora plugin;
- local Codex integrations continue to work;
- Context-Fabric remains usable without central corpus hosting;
- the registry can represent more than one binding for a logical integration;
- generated OpenAI packages follow current documented component layout;
- Web-target package projections do not accidentally become Desktop-only through bundled MCP metadata;
- external Git plugin sources can be represented so upstream packages can replace Agora wrappers;
- compatibility/verification is surface-specific and evidence-backed;
- no implementation adds domain behavior that belongs to a third-party project.

## Explicit stop conditions

Stop and revisit the architecture before implementing any change that would require Agora to:

- proxy all research traffic through infrastructure maintained by Agora;
- store credentials for third-party scholarly services;
- host user corpora as a default requirement;
- fork a third-party MCP server to obtain ChatGPT compatibility;
- reproduce upstream tools under an Agora API;
- introduce a workaround whose only justification is a temporary mobile product limitation.

Any of those changes would alter Agora's ownership model and requires a separate explicit architecture decision rather than being smuggled into compatibility work.