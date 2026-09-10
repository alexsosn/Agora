# Plan amendment: eviction-safe parent lifetime (#135)

Research basis: `P1-research-materializer-parent-input-135-lifecycle-amendment.md`.

This amendment is additive to the original #135 plan and is committed before the corresponding lifetime production behavior.

## A. Finish registered forwarding slice

Preserve the existing tests-only RED requiring `materialize_registered(..., parent=...)` to forward the exact typed binding into the low-level host while retaining the installed-materializer runtime lock and making no fetch/install/repair calls. GREEN is only the optional typed parameter plus unchanged forwarding.

## B. Preserve lifecycle RED

Before adding a lifetime hook, add focused tests around the registered runner that require an explicitly supplied parent lifetime context/capability to be active for the complete low-level host call. The RED must prove:

- enter occurs before `host.materialize`;
- the context remains active inside the host call;
- exit occurs after successful host completion;
- exit also occurs after a host exception;
- the runner itself never invokes canonical parent acquisition/fetch/export/prepare functions;
- ordinary one-source execution remains unchanged when no parent binding is supplied.

The expected RED is that the current registered runner has no lifetime parameter and therefore cannot keep a provider-owned lease active.

## C. GREEN lifecycle seam

Add the smallest provider-neutral optional parent lifetime context to `materialize_registered`. It must not import the Context-Fabric package or `GitStore` and must not know how a parent was discovered. When a parent binding is supplied for managed/registered execution, the caller-provided context is entered **inside the installed-materializer runtime lock and around the complete `host.materialize` call**.

Use a context-manager protocol/type rather than a Context-Fabric concrete class. The binding remains an immutable identity/path value; the context remains the lifetime authority.

Do not expose a raw parent filesystem CLI option in the registered runner. The higher-level trusted orchestrator constructs the binding and lease.

## D. Downstream cache-only resolver contract

Do not add ordinary `ContextFabricResolver.prepare()` calls to the materializer host/runner. A later higher-level composition slice must preserve its own RED requiring exact cached parent lookup and `GitStore.acquire_cache_lease` with no `ensure_metadata`, `_export_snapshot`, Git fetch/clone, or fallback to a newer selected revision.

If current provider code lacks a public cache-only exact-snapshot lookup, file a focused implementation ticket rather than weakening this constraint.

## E. Final review gates

After GREEN, rerun Foundation, Materialization sandbox E2E, and Registered materializer install smoke on one exact head. Independent review must challenge lock ordering (runtime lock vs parent lease), exception release, lease coverage through receipt publication, implicit acquisition, parent/output overlap, standalone compatibility, and absolute-path leakage.
