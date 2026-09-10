# Design/plan: trusted parent-resource inputs for feature-module materializers (#135)

## Preconditions

Research: `wiki/backlog/P1-research-materializer-parent-input-135.md` committed at `56ecbd7893c03302c2661186512c683d477b5ca2` on top of #134 merge `4ebd63f168993a2e7667cd5c464efd0109b7fde8`.

No production behavior changes before the RED commit below.

## Slice 1 — manifest and pure binding contract

### RED

Add focused tests requiring:

- `{parent}` is accepted only when `output.composition.kind = feature-module`;
- standalone materializers reject `{parent}`;
- immutable `ParentResourceBinding` validates resource ID, opaque exact parent version, immutable 40/64-hex revision, and an existing directory;
- binding resource/version mismatch fails before converter execution;
- supplying a parent binding to a standalone materializer fails rather than being ignored;
- feature-module execution using `{parent}` requires a binding.

The expected RED on merged #134 is that the placeholder grammar rejects `{parent}` and no typed binding/runtime path exists.

### GREEN

- Extend the execution-arg placeholder schema to permit `{parent}` syntactically.
- Add a post-schema semantic validation rule: any `{parent}` placeholder requires feature-module output composition.
- Add frozen `ParentResourceBinding` plus pure validation helpers in the low-level materialization module.
- Keep versions opaque; validate only declared exact membership.

## Slice 2 — low-level execution and provenance

### RED

Add tests proving:

- unsandboxed explicit-development execution receives source and parent as distinct paths;
- parent identity is written separately to reserved provenance without the host path;
- ordinary one-source receipt shape is unchanged;
- converter execution is not invoked when parent validation fails;
- parent cannot alias the writable final/staging output boundary.

### GREEN

Extend `materialize(..., parent=...)`:

1. validate declaration/binding before acquisition or converter execution where possible;
2. preserve current source acquisition semantics;
3. render `{parent}` using the validated local path only in unsandboxed mode;
4. add immutable parent identity to host-owned provenance;
5. leave ordinary materializers byte/behavior compatible when `parent is None`.

## Slice 3 — sandbox mounts

### RED

Add command-plan/E2E assertions requiring:

- Linux bubblewrap has a dedicated read-only parent mount and `{parent}` renders to that sandbox path;
- macOS sandbox-exec includes parent in read rules, never write rules;
- output remains the only materializer payload write root;
- source and parent remain distinct read-only inputs;
- network denial is unchanged.

### GREEN

- introduce one stable sandbox parent path (`/agora-parent`) for Linux;
- pass parent path through both sandbox builders only when present;
- extend macOS readable-root calculation without changing writable roots;
- keep current Python/runtime/plugin mounts unchanged.

## Slice 4 — registered runner forwarding

### RED

Require `materialize_registered(..., parent=...)` to:

- preserve the parent binding unchanged into the low-level host call;
- perform host execution under the existing installed-runtime lock;
- never fetch/install/repair a parent;
- reject invalid binding/manifest combinations before source acquisition.

### GREEN

Add the smallest optional typed `parent` parameter to the registered runner and forward it to `host.materialize`. Do not import Context-Fabric or add canonical resource resolution here.

## Slice 5 — regression and integration evidence

Run focused parent tests plus existing:

- Foundation;
- Materialization sandbox E2E;
- Registered materializer install smoke;
- any security/provenance contracts touched by the host/runner.

Use synthetic materializer fixtures only. No Burns-derived source/artifact is required for #135.

## TDD history requirement

Each slice that introduces production behavior must have a preserved tests-only failing commit before the corresponding GREEN. Do not squash the ticket history at merge.

## Independent adversarial review

Freeze one exact final head only after temporary test/workflow scaffolding is removed. Re-derive the contract and challenge:

- duplicate parent declarations or drift from `output.composition`;
- path spoofing as resource identity;
- branch/tag/non-immutable revisions;
- compatibility validation occurring after converter execution;
- implicit parent acquisition/network behavior;
- writable parent mounts or output aliasing;
- absolute path leakage into receipts;
- source/parent provenance conflation;
- standalone materializer regressions;
- low-level host depending on Context-Fabric implementation;
- registered-runner lock/lifecycle races;
- future managed-artifact identity lacking immutable parent identity.

Merge only with exact-head green CI and a commit-anchored logically independent review with no blockers.

## Definition of done

Agora can execute a registered feature-module materializer with two independently trusted inputs — private source plus prepared canonical parent corpus — while keeping parent resolution outside the host, compatibility checks pre-execution, both inputs read-only, output isolated, network policy unchanged, and parent identity durable in provenance.