# Agora plugin boundary

**Status: normative architecture reference.** If an older research, plan, backlog, or review document suggests behavior that conflicts with this document, this boundary takes precedence until an explicit architecture decision changes it.

## Purpose

Agora is a **thin plugin marketplace**. Its job is to help agents discover, understand, install, configure, launch, and select third-party scholarly plugins and their resources. Agora is not a maintenance fork, feature layer, or semantic compatibility layer for those projects.

The marketplace should make upstream software easier to reach without quietly becoming responsible for what that software computes.

## Ownership rule

Use this test first:

> If removing Agora and running the third-party plugin directly leaves the same bug, limitation, or missing capability, the change normally belongs upstream.

The inverse is also useful:

> If the failure is caused by Agora's registry, generated metadata, installer, launcher, transport bridge, resource resolver, or other Agora-owned integration glue, it belongs in Agora.

When ownership is ambiguous, prefer the thinner interpretation and document the upstream limitation rather than silently taking ownership of third-party behavior.

## Agora owns

Agora may implement and maintain:

- canonical marketplace, plugin, provider, resource, version, licensing, and provenance metadata;
- plugin discovery and selection;
- generation of client-native marketplace/plugin manifests;
- installation/bootstrap instructions and dependency constraints needed to launch a supported upstream release;
- process launch and client configuration;
- transport adaptation required to connect a supported client to an upstream endpoint;
- resource discovery/resolution that is part of Agora's marketplace model rather than an upstream domain algorithm;
- health checks and integration smoke tests;
- compatibility declarations and known-limitations metadata;
- generic cross-plugin workflows;
- thin usage guidance that helps an agent call an individual plugin's **existing published capabilities** correctly.

## Agora does not own

Agora must not normally:

- patch a third-party plugin's functions or methods to change their results;
- repair upstream search, counting, parsing, ranking, morphology, tokenization, retrieval, annotation, or other domain semantics;
- add a tool, query mode, transformation, or scholarly capability missing from upstream;
- access private upstream internals in order to fix or extend upstream behavior;
- maintain an Agora-specific semantic fork of a third-party API;
- reproduce an upstream behavioral test suite merely so Agora can carry an upstream bug fix;
- present an Agora-generated workaround as if the third-party plugin natively supported it.

A bug being severe, easy to patch, or important for scholarship does not move ownership into Agora.

## Thin adapters

Adapters are allowed when they solve an **integration** mismatch rather than a **behavior** mismatch.

Examples of acceptable adapter responsibilities:

- stdio/SSE/HTTP transport bridging;
- executable/command construction;
- environment setup;
- translating Agora's canonical registry entry into a public upstream configuration or identifier;
- lazy acquisition or resource selection that Agora itself advertises as marketplace behavior;
- normalizing client-specific packaging metadata.

An adapter should satisfy all of these:

1. **Necessary for integration:** a supported client cannot otherwise install, launch, reach, or select the upstream plugin/resource in the advertised way.
2. **Semantics-preserving:** domain inputs and outputs retain the meaning defined by upstream.
3. **Public-boundary first:** use documented/public upstream interfaces whenever possible.
4. **Small and removable:** it should be possible to delete the adapter when upstream/client support removes the integration mismatch.
5. **Visible:** metadata or documentation should make material adaptation clear rather than impersonating native upstream behavior.

Transport adaptation may change how bytes travel; it must not change the scholarly answer.

## Upstream bugs and missing features

When Agora discovers an upstream defect:

1. reproduce enough to determine whether Agora itself caused it;
2. if not, report or link the issue upstream;
3. record the limitation in Agora metadata/documentation when it affects users;
4. constrain or pin a known-good upstream version if that is sufficient and appropriate;
5. adjust Agora verification/status claims if the limitation invalidates them;
6. remove the limitation note when a supported upstream release fixes it.

Do **not** insert a monkey-patch, private-API shim, alternative algorithm, or replacement tool into Agora simply because an upstream release is currently wrong.

If an upstream project is abandoned and a capability is important enough to maintain independently, that requires an explicit architectural decision to adopt/fork the project. It must not happen accidentally through a sequence of marketplace fixes.

## Skills boundary

Skills are instructions and workflows, so they can create capability even without adding Python code. The same ownership rule applies to them.

### Default

Substantive skills for a third-party plugin should live with that plugin upstream whenever practical. Domain workflows and new research capability should evolve beside the tools they depend on.

### Skills allowed in Agora

Agora may ship:

- **generic marketplace skills** — discovery, comparison, installation, selection, orchestration, provenance, or other workflows that apply across plugins;
- **plugin-facilitation skills** inside an Agora plugin package — guidance for using existing upstream tools, identifiers, configuration, discovery flows, limitations, output interpretation, and reproducibility conventions;
- **repository-maintenance skills** under `.agents/skills/` — workflows for contributors/coding agents maintaining Agora itself. These are development guardrails, not scholarly plugin capabilities.

### Skills not allowed in Agora

An Agora skill must not:

- emulate a missing upstream tool through a sequence of unrelated calls and advertise it as a supported capability;
- post-process an incorrect upstream result into a replacement result that Agora then treats as authoritative;
- encode a new domain algorithm that belongs in the plugin;
- conceal an upstream limitation by teaching the agent a silent workaround;
- duplicate an upstream plugin's own substantive skill when Agora can package/reference the upstream skill instead.

A facilitation skill may explain a limitation and suggest an explicitly identified external/manual workflow. It may not make Agora the maintainer of the missing capability.

## Testing boundary

Agora tests should verify **Agora-owned contracts**:

- registry/schema validity;
- generated marketplace metadata;
- installation and launch configuration;
- transport compatibility;
- advertised tool discovery;
- Agora-owned resource resolution and packaging;
- a small number of representative smoke operations showing that the integration reaches the real upstream service.

Smoke tests may assert stable facts needed to detect a broken integration, such as successful initialization or a known public operation returning a structurally valid response. They should not become a substitute for upstream tests of search correctness, linguistic analysis, ranking, counts, or other domain behavior.

If a failing Agora test can only be fixed by changing how the third-party plugin computes its answer, the likely outcome is an upstream issue plus an Agora limitation/status update, not an Agora implementation patch.

## Decision examples

| Situation | Owner | Agora action |
|---|---|---|
| Generated MCP command points at the wrong executable | Agora | Fix generator/metadata and test it |
| Client supports stdio but upstream exposes only SSE | Agora integration | Use a thin transport bridge if needed |
| Agora resolves the wrong corpus repository/version | Agora | Fix resolver/registry logic |
| Upstream `count` silently truncates results | Upstream | Report/link; document limitation; pin a fixed release when available |
| Upstream lacks morphology search | Upstream feature request | Do not implement morphology search in Agora |
| Upstream tool returns malformed domain data | Upstream | Report/link and adjust verification/limitations |
| Agent routinely invents valid-looking identifiers although upstream has discovery tools | Agora plugin-facilitation skill | Teach the agent to discover identifiers first |
| A workflow chooses among Perseus, Sefaria, and Context-Fabric based on research need | Agora generic skill | Appropriate cross-plugin guidance |
| A new philological analysis algorithm would be useful for one plugin | Upstream/plugin project | Contribute it there, not to marketplace core |

## Review rule

Every plugin-related PR should be able to answer:

1. Which Agora-owned responsibility does this change serve?
2. Would the underlying bug/feature request still exist without Agora?
3. Does any adapter preserve upstream semantics?
4. Are tests validating Agora integration rather than taking ownership of upstream behavior?
5. Are new skills generic or strictly facilitative of capabilities the plugin already exposes?

If those questions reveal an upstream bug or feature request, redirect the substantive change upstream before merging the Agora PR.
