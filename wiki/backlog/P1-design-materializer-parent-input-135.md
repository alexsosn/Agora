# Design/plan: trusted parent-resource inputs for feature-module materializers (#135)

## Preconditions

Research: `wiki/backlog/P1-research-materializer-parent-input-135.md`.
Implementation is gated on #134 landing first because this design reuses `output.composition` as the single declarative parent/compatibility source of truth.

## 1. Preserve RED after #134 is merged

Create focused tests before production changes for:

- `{parent}` is accepted only for `output.composition.kind = feature-module`;
- a trusted immutable parent binding is required before converter execution when `{parent}` is used;
- binding resource ID must equal declared `composition.parent`;
- binding version must be one of declared `parent_versions`;
- non-immutable parent revision is rejected;
- source and parent paths are passed separately and never copied/flattened;
- registered runner preserves parent identity separately in the host call;
- materialization receipt records parent resource/version/revision but not parent host path;
- standalone one-source materializers remain byte/behavior compatible;
- binding supplied to a standalone materializer fails rather than being ignored;
- sandbox mount planning marks both source and parent read-only and output writable;
- sandbox-visible `{parent}` substitution cannot escape or alias output.

Preserve the exact failing RED commit/run before GREEN.

## 2. Schema GREEN

Extend execution argument placeholder grammar with `{parent}` under a conditional rule tied to feature-module composition. Do not introduce a separate manifest `parent` field: #134 output composition is the canonical declaration.

If JSON Schema conditional validation becomes unreadable, use a small post-schema semantic validator, but keep one authoritative error path and tests proving malformed manifests fail before execution.

## 3. Typed trusted binding

Add an immutable `ParentResourceBinding` at the registered-runner/core boundary containing:

- resource_id;
- version;
- immutable source_revision;
- resolved local path.

Validate declaration-vs-binding before entering converter execution. Never infer resource identity from a path.

## 4. Low-level host + sandbox

Teach the low-level materializer host to accept an already-validated parent binding/path without resolving resources itself.

Extend the sandbox workspace/mount plan so parent is a distinct read-only mount and `{parent}` expands to the sandbox-visible mount. Preserve existing source/output containment and network-deny behavior.

## 5. Registered/higher-level resolution seam

The registered runner accepts a trusted parent binding from a higher-level resource orchestrator. It must not silently fetch/install a parent while holding materializer runtime locks.

A small resolver adapter may be added at the higher-level Context-Fabric/Agora integration boundary if needed, but core materialization must remain independent of plugin implementation details.

## 6. Provenance

Write parent identity into reserved host provenance separately from source provenance. Do not persist the absolute parent path. Preserve #134 `output.composition` as the declaration and the parent receipt as the observed trusted execution binding.

## 7. Full regression

Run:

- focused parent-binding tests;
- materialization security/sandbox E2E suites;
- registered-materializer execution/install suites;
- Context-Fabric resolver/runtime suites if an adapter changes;
- full Foundation and platform workflows.

## 8. Logically independent adversarial review

Freeze exact head and independently challenge:

- duplicate parent metadata sources that can drift;
- arbitrary path spoofing as canonical parent identity;
- branch/tag acceptance where immutable revision is required;
- hidden parent auto-install/network behavior;
- writable or overlapping parent mount;
- host-path leakage into receipt/cache identity;
- source/parent provenance conflation;
- compatibility check occurring after converter execution rather than before;
- accidental behavior changes for standalone materializers;
- core ↔ Context-Fabric plugin dependency inversion;
- cache identity unable to incorporate immutable parent identity later.

Only merge after exact-head CI and commit-anchored independent review have no blockers.

## Definition of done

Agora can execute a registered feature-module materializer against a private local source plus an independently resolved trusted parent corpus, with compatibility checked before execution, separate read-only mounts, immutable parent provenance, no materializer network fallback, and no regression for ordinary one-source materializers.
