---
name: agora-plugin-integration
description: "Use this skill when adding, updating, fixing, or integrating a third-party plugin in Agora; keep the marketplace layer thin, identify ownership before coding, and redirect upstream bugs or missing capabilities to the upstream project."
license: MIT
metadata:
  scope: repository-maintenance
  project: Agora
---

# Agora plugin integration

Use this skill for repository work involving `plugins/`, plugin runtime metadata, provider adapters, dependency/version changes, plugin-specific tests, or plugin-related issues.

Agora is a thin marketplace. Before writing code, identify whether the requested change belongs to Agora or to the third-party plugin.

## Ownership test

Ask both questions:

1. **Would the bug or missing capability still exist if the third-party plugin were run directly without Agora?**
   - Yes: it normally belongs upstream.
   - No: continue investigating Agora's integration layer.
2. **Is the desired change about discovery, description, installation, launch, transport, configuration, resource selection, or another explicit Agora-owned marketplace contract?**
   - Yes: it may belong in Agora.
   - No: do not implement it in Agora merely because the plugin is exposed here.

Read `wiki/architecture/ref-plugin-boundary.md` when the answer is not obvious.

## Allowed implementation work

Agora changes may include:

- registry/plugin/resource metadata;
- generated client manifests and their generator;
- installation/bootstrap configuration;
- dependency constraints needed to launch a supported upstream version;
- executable/process configuration;
- transport bridges;
- Agora-owned resource discovery/resolution;
- health checks and smoke tests;
- known limitations and verification/status metadata;
- thin facilitation skills for capabilities the upstream plugin already exposes.

Keep adapters small, semantics-preserving, public-API-first, visible, and removable.

## Stop conditions

Do not implement the requested change in Agora when it requires any of these primarily to alter third-party behavior:

- monkey-patching upstream functions;
- replacing an upstream algorithm;
- using private internals to repair a result;
- adding a tool or query mode absent upstream;
- correcting search/count/parser/ranking/morphology/retrieval semantics;
- post-processing an incorrect upstream answer into a new authoritative answer;
- maintaining tests whose purpose is to prove the upstream algorithm is correct.

Instead:

1. confirm Agora itself is not causing the defect;
2. find or open the upstream issue/PR when possible;
3. record the limitation in Agora if users need to know;
4. pin/constrain a fixed or known-good upstream release if appropriate;
5. adjust Agora verification claims if necessary.

Do not create a silent compatibility shim as a substitute for an upstream fix.

## Skills

A third-party plugin's substantive domain skills belong upstream whenever practical.

An Agora plugin-specific skill is acceptable only when it facilitates an existing published capability: for example, discovering identifiers before calling a tool, selecting among existing tools, explaining configuration, preserving provenance, or warning about documented limitations.

Do not use a skill to emulate a missing upstream tool or silently compensate for incorrect upstream behavior.

Generic cross-plugin marketplace skills may live in Agora because choosing, installing, and coordinating plugins is Agora-owned behavior.

## Testing

Test the contract Agora owns.

Good tests cover registry validity, generated metadata, process/transport configuration, installation, tool discovery, Agora-owned resource resolution, and smoke-level evidence that a published upstream operation can be reached.

Do not turn Agora CI into an upstream semantic test suite. If a failing test can only be repaired by changing how the third-party plugin computes its answer, redirect the fix upstream and update Agora's limitation/status metadata.

## PR summary

For plugin-related PRs, include a short scope statement answering:

- What Agora-owned responsibility does this change serve?
- Would the underlying problem exist without Agora?
- What upstream version/interface is being integrated?
- Does any adapter preserve upstream semantics?
- Are new tests limited to Agora-owned contracts?
- Are any new skills generic or facilitative rather than capability-adding?
