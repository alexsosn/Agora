# Plan amendment: eviction-safe parent lifetime (#135)

Research basis: `P1-research-materializer-parent-input-135-lifecycle-amendment.md`.

This amendment is additive to the original #135 plan and is committed before the corresponding lifetime production behavior.

## A. Finish registered forwarding slice

Preserve the existing tests-only RED requiring `materialize_registered(..., parent=...)` to forward the exact typed binding into the low-level host while retaining the installed-materializer runtime lock and making no fetch/install/repair calls. GREEN is only the optional typed parameter plus unchanged forwarding.

## B. Preserve lifecycle RED

Before adding a lifetime hook, add focused tests around the registered runner that require an explicitly supplied parent lifetime capability to be active for the complete low-level host call. The capability is supplied as a **lazy zero-argument context-manager factory**, not as an already-entered lease. This keeps acquisition ordering under the registered runner's control and lets the future Context-Fabric adapter supply `lambda: store.acquire_cache_lease(path)` without importing `GitStore` here.

The RED must prove:

- the lease factory is called only after the installed-materializer runtime lock is held;
- its returned context is entered before `host.materialize`;
- the context remains active inside the host call;
- exit occurs after successful host completion;
- exit also occurs after a host exception;
- a managed parent binding without a lifetime factory fails closed before the converter host is invoked;
- a lifetime factory without a parent binding is rejected rather than silently ignored;
- the runner itself never invokes canonical parent acquisition/fetch/export/prepare functions;
- ordinary one-source execution remains unchanged when neither parent nor lifetime factory is supplied.

The expected RED is that the current registered runner has no `parent_lease_factory` parameter and therefore cannot keep a provider-owned lease active.

## C. GREEN lifecycle seam

Add the smallest provider-neutral lifetime seam to `materialize_registered`, conceptually:

```python
parent_lease_factory: Callable[[], ContextManager[object]] | None = None
```

It must not import the Context-Fabric package or `GitStore` and must not know how a parent was discovered. When a parent binding is supplied for managed/registered execution, a lifetime factory is required. The factory is invoked and its context entered **inside the installed-materializer runtime lock and around the complete `host.materialize` call**.

Required lock/lifetime order:

1. acquire installed-materializer runtime lock;
2. revalidate installed environment and current registry binding;
3. invoke `parent_lease_factory()`;
4. enter the returned parent lease/context;
5. call `host.materialize(...)` completely, including converter execution, output validation, and provenance publication;
6. exit parent lease/context on success or exception;
7. release runtime lock.

This ordering avoids a caller pre-acquiring a cache lease and then blocking on the runtime lock in the opposite order elsewhere. The binding remains an immutable identity/path value; the context remains the lifetime authority.

Do not expose a raw parent filesystem CLI option or a lease-factory CLI option in the registered runner. The higher-level trusted orchestrator constructs the binding and lease factory.

## D. Downstream cache-only resolver contract

Do not add ordinary `ContextFabricResolver.prepare()` calls to the materializer host/runner. Current Context-Fabric already has useful offline pieces (`GitStore.materialize(..., allow_network=False)` and explicit offline source mode), but those do not by themselves provide the required public exact-identity lookup + lease handle. A later higher-level composition slice/#146 must preserve its own RED requiring exact cached parent lookup and `GitStore.acquire_cache_lease` with no `ensure_metadata`, `_export_snapshot`, Git fetch/clone, or fallback to a newer/cached-selected revision.

## E. Final review gates

After GREEN, rerun Foundation, Materialization sandbox E2E, and Registered materializer install smoke on one exact head. Independent review must challenge lock ordering (runtime lock before lazy parent lease), exception release, lease coverage through receipt publication, implicit acquisition, parent/output overlap, standalone compatibility, and absolute-path leakage.
