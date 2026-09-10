# Research amendment: parent snapshot lifetime and cache-only resolution (#135)

## Trigger

Independent adversarial review of the in-flight #135 implementation re-read the accepted #139/#140 research feedback against current Agora `main` and found a lifecycle gap that the initial #141 implementation did not yet encode.

Current Context-Fabric `GitStore` now has a concrete cross-process `acquire_cache_lease(path)` primitive. Corpus snapshots are eviction-managed cache objects. A `ParentResourceBinding.path` that is merely validated as an existing directory is therefore not sufficient evidence that the parent remains present for the converter lifetime: concurrent prune/eviction may detach an unleased snapshot after validation and before or during sandbox execution.

## Current primitives

`GitStore.acquire_cache_lease(path)`:

- accepts only recognized managed snapshot/overlay paths;
- acquires a shared per-object lock;
- validates the managed object before returning;
- prevents the eviction path from obtaining the corresponding exclusive object lock;
- is explicitly releasable/context-managed.

`ContextFabricResolver.prepare(...)`, by contrast, is not a cache-only lookup. Its normal path may call repository metadata refresh and snapshot export, including Git/network acquisition. Calling ordinary `prepare()` from the materializer runner would violate #135's no-implicit-parent-acquisition boundary.

## Corrected execution contract

Separate three responsibilities:

1. **Provider resolution**: a trusted higher-level Context-Fabric/Agora orchestration layer identifies an already-resident exact corpus snapshot by canonical resource ID, exact opaque TF version, and immutable source revision. This lookup is cache-only. Missing exact state fails closed; it does not fetch, export, update a selected ref, or fall back to current upstream state.
2. **Lifetime lease**: before handing the binding to materializer execution, trusted orchestration acquires a shared lease on that exact managed snapshot and retains it for the complete converter call, including sandbox startup, execution, output validation, provenance publication, and exceptional exit.
3. **Execution**: `materialize_registered()` and the low-level host validate/forward the typed `ParentResourceBinding` but do not import Context-Fabric, fetch the parent, or infer canonical identity from a filesystem path.

The parent binding remains a value object containing observed identity and path. The lease is a separate lifetime capability owned by the orchestration/provider layer; filesystem path existence is not a substitute for it.

## Ticket boundary

#135 must make the registered execution seam capable of forwarding the validated parent binding under the existing materializer-runtime lock. It must also define/test a provider-neutral lifetime hook so trusted orchestration can hold the parent lease around the entire host execution without the runner acquiring/fetching resources itself.

A concrete canonical-resource cache-only resolver adapter belongs to the higher-level composition work (#101 / resource-manager work) unless an existing provider-neutral API already exposes it. #135 must not claim automatic parent resolution is complete merely because `{parent}` can be rendered.

For the Burns migration, the next downstream integration must prove:

- exact cached `cuc` snapshot identity matches `parent=cuc`, version `0.2.8`, and an immutable resolved revision;
- no `ensure_metadata`, Git fetch/clone, `_export_snapshot`, or ordinary acquiring `prepare()` occurs as a side effect of materialization;
- a `GitStore.acquire_cache_lease()` (or equivalent provider lease) is held until converter completion and released on both success and failure;
- missing or evicted exact parent fails before converter/source acquisition rather than falling back to the network.

## TDD amendment

After the current registered-forwarding RED/GREEN slice, add a preserved RED before any lifetime-hook production change. It must prove:

- the supplied parent lifetime context is entered before the low-level host call and remains active throughout that call;
- the context is exited on host success and exception;
- no parent resolver/fetch/install/repair function is called by the registered runner;
- supplying a parent binding without the required lifetime capability is rejected on the managed/registered path once that path claims eviction-safe parent execution;
- ordinary one-source materializers remain unchanged.

Do not make the low-level explicit-manifest host depend on `GitStore`; it remains usable with caller-owned parent directories outside the managed Context-Fabric cache in explicit trusted/development contexts.

## Security consequence

Without the lifetime lease, the immutable identity in `agora-materialization.json` could truthfully describe what was validated but not what remained mounted/read during execution. The lease closes that TOCTOU window for Agora-managed canonical parent snapshots; producer-side CUC fingerprint verification remains an additional semantic compatibility check, not a replacement for cache lifetime protection.
