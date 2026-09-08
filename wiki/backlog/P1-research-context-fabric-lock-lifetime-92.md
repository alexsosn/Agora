# P1 research: Context-Fabric cache lock lifetime warnings

Issue: #92

## Question

Why does a green Foundation run emit `ResourceWarning` diagnostics for unclosed Context-Fabric cache-object lock files and portalocker warnings about releasing an already-closed file, and what is the smallest Agora-owned correction that preserves the existing cross-process cache safety contract?

## Current evidence

Research is grounded in `main` at `94bcddb45c9e1e7a1bcb766ce82a820f8be4209c` and Foundation run 795 (`34226030823`). The full suite is functionally green (517 tests, 3 skips), including Linux/macOS/Windows Context-Fabric cache-lifecycle lanes, but the Linux unit job reproducibly emits four warnings immediately before `test_context_fabric_load_smoke.ContextFabricLoadSmokeTests.test_main_without_case_arguments_runs_all_registered_cases`:

- four `ResourceWarning: unclosed file .../cache/locks/cache-objects/<digest>.lock` diagnostics;
- four portalocker cleanup warnings equivalent to `ValueError('I/O operation on closed file')` while releasing those locks;
- each warning points at a different `TemporaryDirectory` cache root but the same logical fixture object-lock identity.

The smoke CLI test that happens to display the warnings patches `run_case` and opens no Context-Fabric lock. The warnings therefore originate earlier and become visible only when later allocation/GC collects the leaked owners.

## Portalocker 4.3.0 contract

Agora pins `portalocker[win32]==4.3.0`. The tagged 4.3.0 implementation documents and implements the following relevant behavior:

- `Lock.release()` is deliberately a no-op when the instance does not own a handle;
- release clears/claims the owned handle before unlock/close cleanup;
- unlock and close are both attempted; cleanup errors are suppressed/logged by default;
- the 4.x line contains explicit fixes for failed-acquire handle leakage and stale/double-release paths.

Therefore Agora's defensive `lock.release()` calls after a failed nonblocking `acquire()` are redundant but are not, by themselves, a sufficient explanation for the reproduced leak. Changing those paths without a reproducer would weaken a proven lock contract for no demonstrated benefit.

## Agora ownership trace

`GitStore.acquire_cache_lease()` intentionally returns a process-backed shared lease. `ContextFabricService.load()` stores that lease in `_loaded_leases`; the lease remains held until `ContextFabricService.unload(logical_name)` is called. This is required so cache eviction cannot remove a corpus still loaded by the service.

The existing lifecycle tests respect that ownership: successful service loads are explicitly unloaded before their temporary cache root disappears.

The cold-load runtime test class has four successful load paths that do not unload before their `TemporaryDirectory` exits:

1. `test_warm_marker_bypasses_cold_compiler_and_limits`;
2. `test_successful_cold_worker_is_followed_by_parent_warm_load`;
3. `test_cold_warm_race_rechecks_marker_after_compile_lock`;
4. `test_cache_transition_is_not_held_during_cold_worker`.

That count exactly matches the four leaked temporary cache roots in Foundation 795. Failing/cancelled load tests do not retain a successful lease and do not contribute equivalent warnings.

## Root-cause conclusion

The current evidence supports a **test teardown ownership defect**, not a production lock-primitive defect:

- successful load correctly retains a shared lease;
- the four tests destroy the filesystem tree while that lease is intentionally still live;
- the service/lease becomes collectible only after the test frame is gone;
- later GC closes/releases a lock whose backing temporary cache has already been torn down, producing the delayed diagnostics.

There is no current evidence that normal failed acquisition leaks a handle, nor that a supported `load -> unload` runtime lifecycle leaks one.

## Scope decision

The first implementation must make test ownership explicit and add a regression that turns the confirmed delayed cache-lock `ResourceWarning` into a test failure. It must **not**:

- suppress `ResourceWarning` globally;
- delete defensive failed-acquire releases without a separate failing reproducer;
- add `ContextFabricService.__del__` or implicit production unload semantics;
- release a successfully loaded corpus lease before explicit `unload`, which would break eviction safety.

If the focused RED disproves this root-cause model, stop and re-research the actual owner before changing production code.

## User impact

The functional corpus API already works, but leaked descriptors and noisy cleanup diagnostics make long-running hosts and CI less trustworthy. The desired outcome is clean, explicit lifetime handling while preserving the guarantee that a loaded corpus cannot be evicted out from under a caller.
