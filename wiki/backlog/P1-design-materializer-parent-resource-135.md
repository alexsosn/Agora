# Plan: named resource inputs for materializers (#135)

Frozen after `P1-research-materializer-parent-resource-135.md`. Production changes must follow preserved RED evidence.

## Goal

Allow a registered materializer to declare immutable named Agora resource inputs in addition to its primary source, resolve those inputs from already-acquired trusted Context-Fabric snapshots, mount them read-only at deterministic paths, and bind their exact logical identity into provenance.

This is the generic execution primitive needed for Burns -> CUC feature-module materialization. Burns/Agora registry migration remains downstream.

## Contract decision

A materializer may optionally declare:

```json
"resource_inputs": [
  {
    "name": "parent",
    "resource": "cuc",
    "version": "0.2.8",
    "source_revision": "ad69400f5446e1c8217af01659c7c10ab00c015b"
  }
]
```

Execution arguments may reference `{resource:parent}`.

V1 resource inputs are intentionally limited to Context-Fabric `kind: corpus` resources with an explicit TF `version` and immutable 40/64-hex `source_revision`. Collection members and feature-module-as-input selection remain out of scope until their extra identity dimensions are designed.

## Phase 1 — RED: manifest + host contract

Before production changes, add focused failing tests that require:

1. `materializer-plugin.schema.json` accepts optional `resource_inputs` entries with safe unique names, resource id, version and immutable source revision.
2. Existing manifests without `resource_inputs` remain valid.
3. Unsafe names, duplicate names, non-immutable revisions, and `{resource:name}` placeholders for undeclared names fail manifest validation.
4. `_render_args` renders a declared named resource path and rejects unresolved/undeclared resource placeholders.
5. A typed `PreparedResourceInput`/equivalent carries name, resource id, version, source revision and trusted local path independently of `PreparedSource`.
6. Linux sandbox commands read-only bind the parent at `/resources/parent` and render `{resource:parent}` to that deterministic in-sandbox path; source remains `/input`.
7. macOS and sandbox-off execution render the same logical binding without copying/flattening parent bytes into the source.
8. Host provenance records logical `name/resource/version/source_revision`, excludes the absolute host resource path, and retains old one-source provenance shape compatibly when there are no resource inputs.
9. Supplying missing/extra resource bindings fails before converter subprocess execution/output publication.

Preserve the exact RED commit and CI failure before implementation.

## Phase 2 — GREEN A: generic manifest/host support

Minimal files expected:

- `registry/schema/materializer-plugin.schema.json`
- `scripts/agora_materialize.py`
- focused tests

Implementation rules:

- add optional `resource_inputs`; no schema-version bump is needed because it is additive and old manifests remain valid;
- semantic validation enforces unique names and declared-placeholder references;
- add `PreparedResourceInput` dataclass;
- extend argument rendering with a deterministic `resource_paths` mapping;
- resource bindings supplied to `materialize()` must exactly match declarations and exact identity fields;
- generic host never resolves/fetches resource identities;
- Linux mounts each resource input read-only at `/resources/<name>` in declaration order;
- macOS grants only file-read access to each resolved path;
- `sandbox=off` receives host paths directly;
- preserve existing staging, validation, network-denial and atomic publication behavior;
- provenance contains resource logical identities only, not local absolute paths.

Run focused tests and full Foundation/materialization/sandbox suites before proceeding.

## Phase 3 — RED: trusted cached resolution + registered-run orchestration

Add failing tests before resolver/orchestration production changes:

1. cached resolution accepts `(resource_id, version, source_revision)` and returns exactly one managed corpus snapshot matching all three dimensions;
2. resolution performs no `ensure_metadata`, Git fetch/clone, network call or snapshot export; absent exact snapshot fails closed with an actionable error;
3. non-corpus resource declarations are rejected for v1;
4. resolver acquires a `GitStore.acquire_cache_lease(path)` lease before handing the binding to execution;
5. the lease remains held through `host.materialize()` and releases on both success and exception;
6. registered runner resolves all manifest-declared resource inputs before host invocation, in declaration order;
7. any dependency failure prevents host invocation/output publication and does not fetch/install/repair the materializer;
8. plugin runtime lock semantics from the existing registered runner remain unchanged;
9. exact logical resource identity is passed to host unchanged;
10. registered CLI has no arbitrary `name=/host/path` trust bypass.

Use synthetic cache snapshots/repositories only. Preserve exact RED evidence.

## Phase 4 — GREEN B: cached Context-Fabric resolver adapter

Preferred implementation:

- add a narrow cached resource-input resolver in the Context-Fabric/Agora boundary, not in the generic host;
- query only indexed managed `corpus-snapshot` objects already present in `GitStore`;
- match exact logical resource id, requested TF dataset version (derived from recorded relative path), and immutable revision;
- validate the catalog says the resource is a corpus;
- acquire the existing shared cache-object lease and return a binding/context object whose lifetime spans converter execution;
- do not call `ContextFabricResolver.prepare()` default online path because it can refresh/fetch;
- do not export/materialize a missing snapshot while executing a registered materializer;
- wire the registered runner to the trusted resolver through an explicit adapter/injectable seam so tests can prove the absence of hidden acquisition;
- release all leases in reverse acquisition order in `finally`.

If current repository/plugin packaging makes the resolver adapter unavailable to the registered-run orchestrator without duplicating Context-Fabric internals, stop and file a narrowly scoped packaging/integration child issue rather than adding path hacks. Generic GREEN A may still merge independently if useful, but #135 itself stays open until the real trusted resolution path exists.

## Phase 5 — end-to-end synthetic feature-module acceptance

Preserve/execute an end-to-end contract with no copyrighted data:

- synthetic user-local source directory;
- synthetic already-acquired parent Text-Fabric corpus snapshot represented as an Agora-managed Context-Fabric cache object at a fixed immutable revision;
- manifest declares `resource_inputs.parent` and execution uses `{resource:parent}`;
- registered execution receives separate source and parent paths;
- required sandbox has no network and parent mount is read-only;
- converter writes only feature-module output into staging;
- provenance binds exact parent identity and does not expose parent/source absolute paths;
- old single-source materializer still runs unchanged.

A downstream Burns-specific live test belongs in `ugarit-context-parsing#29` after #135 lands; #135 should not hard-code Burns/CUC semantics into generic runtime code.

## Exact-head test gate

Before final review require the frozen head to pass at least:

- full Foundation test suite;
- materializer manifest/schema tests;
- registered run-by-ID tests;
- materialization security/staging tests;
- Linux sandbox E2E where available;
- Context-Fabric cache lifecycle/lease tests touched by cached resource resolution;
- synthetic two-input feature-module acceptance;
- existing execution-identity v3 regressions.

Record exact environment/provenance using existing CI gates.

## Independent adversarial review

Freeze final head and review independently of implementation history. Challenge:

- arbitrary-path trust bypass;
- implicit fetch/clone/export during resource resolution;
- wrong-revision or wrong-version cache selection;
- ambiguous multiple snapshot selection;
- lease acquisition/lifetime and eviction races;
- lock-order cycles between plugin runtime lock and resource cache locks;
- writable parent mounts or path escape;
- placeholder injection/undeclared resource names;
- provenance absolute-path leakage;
- omission of resource identity from request/build provenance;
- accidental mutation of installed materializer execution identity v3 with run-specific parent state;
- regression of existing single-source manifests/runs;
- hidden coupling to Burns/CUC.

Any blocker requires a fix, fresh exact-head tests, and a new independent review. Merge only with expected-head SHA protection.

## Downstream

After #135 merges, return to `alexsosn/ugarit-context-parsing#29` to update the Burns materializer manifest and Agora registry so Burns is represented/executed as a feature module layered on exact CUC rather than as an independent corpus.
