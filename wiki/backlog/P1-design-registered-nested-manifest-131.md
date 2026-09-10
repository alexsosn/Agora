# Design: registered materializer nested-manifest consistency (#131)

Research: `wiki/backlog/P1-research-registered-nested-manifest-131.md`.

## Goal

Make direct registered materializer execution honor the registry's existing safe-relative nested manifest contract while preserving fail-closed registry/runtime integrity under concurrent registry drift.

## Non-goals

- no third-party converter or scholarly behavior changes;
- no automatic fetch/install/repair;
- no cacheability-policy dependency;
- no schema expansion: nested safe-relative manifests are already valid;
- no weakening of runtime-lock, receipt, source/ref, registry↔manifest, or materializer-id checks.

## TDD sequence

### RED

Commit focused tests before production changes requiring:

1. a schema-valid nested `manifest: pkg/agora.materializer.json` can be installed and then executed through `materialize_registered()`;
2. an existing root-level manifest continues to execute unchanged;
3. absolute/traversal/escaping current manifest paths still fail closed through schema/containment;
4. a registry target/ref change while waiting for the runtime lock still fails closed;
5. a registry manifest-path change to a different contained file while waiting for the runtime lock fails closed even when both files have the same parent directory;
6. nested-path drift likewise fails closed;
7. resolution/execution remain read-only with respect to installation state: no fetch, install, repair, or package build is triggered.

The expected RED on current `main` is the valid nested-manifest execution case because `materialize_registered()` requires `manifest.parent == expected_runtime`; the stale same-directory manifest-path case should also demonstrate why simply deleting that check would be unsafe.

### GREEN

Inside the existing runtime-lock region:

1. preserve the manifest path returned by the already integrity-verifying `resolve_installed_manifest()`;
2. re-read current plugin/target state as today;
3. compute `current_manifest = installer._contained(expected_runtime, current_plugin["manifest"], "current managed runtime manifest").resolve()`;
4. replace `manifest.parent == expected_runtime` with exact equality `manifest == current_manifest` alongside `current_target == target`;
5. retain `installer._validate_binding(current_plugin, expected_runtime)` and the current approved-materializer check before calling `host.materialize()`.

No other execution flow changes are justified.

## Lifecycle ordering

The existing runtime lock remains authoritative. The required order is:

```text
acquire runtime lock
  → verify installed runtime / resolve registered manifest
  → re-read current registry target
  → resolve current registered manifest by containment
  → compare exact target + exact resolved manifest path
  → validate current registry↔manifest binding
  → verify requested materializer remains approved
  → execute host materializer while lock remains held
release runtime lock
```

This closes the path-selection TOCTOU without adding a new lock domain.

## Error semantics

A current registry manifest path that escapes containment, disappears, changes path, or no longer binds to the registered plugin must fail as `MaterializerInstallError`/existing domain failure before converter execution. Do not silently fall back to the previously verified path.

## Validation gates

After GREEN:

- focused nested-manifest and registry-drift tests;
- existing `test_materializer_run_by_id*` lifecycle/binding tests;
- canonical registry validation;
- full Foundation;
- Registered materializer install smoke;
- Materialization sandbox E2E;
- Linux/macOS/Windows materializer-install lock regressions;
- exact-head logically independent adversarial review before merge.

## Independent review focus

Challenge the final patch for:

- accidental string-prefix rather than resolved containment checks;
- resolving the current manifest outside the runtime lock;
- validating one manifest but executing another;
- target/ref drift not invalidating execution;
- nested path accepted by runner but not installer/schema;
- new implicit install/repair/network side effects;
- weakening root-level legacy behavior;
- coupling direct execution to cacheability policy.

## Definition of done

A materializer registered with a contained nested manifest behaves exactly like a root-level registration through install and direct registered execution, while any change in the currently registered target or exact manifest path during the runtime-lock wait causes execution to fail closed.