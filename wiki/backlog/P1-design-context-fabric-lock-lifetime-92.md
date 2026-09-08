# P1 design: Context-Fabric cache lock lifetime warnings

Issue: #92
Research: `wiki/backlog/P1-research-context-fabric-lock-lifetime-92.md`

## Goal

Make Context-Fabric load-test teardown obey the same explicit `load -> unload` ownership contract as production, and make future cache-object file-handle leaks fail deterministically instead of surfacing later as incidental warnings.

## Constraints

- Preserve shared leases for the full lifetime of a successfully loaded corpus.
- Preserve cross-process eviction exclusion and existing explicit `unload` semantics.
- Do not add implicit destructor/shutdown behavior to the service in this ticket.
- Do not alter portalocker acquisition/release behavior without a separately reproduced production defect.
- Do not globally hide resource warnings.

## TDD slice

### RED

Instrument `ServiceColdCompileRuntimeTests` so every test captures `ResourceWarning` diagnostics for Context-Fabric cache-object lock files from setup through teardown. Teardown must force GC before inspecting the captured diagnostics, and fail if an unclosed warning names `cache/locks/cache-objects` (normalizing path separators for Windows).

This instrumentation is the tests-only RED change. On current `main`, the four successful service-load tests that omit `unload()` are expected to fail; unrelated cold-compile failures/cancellation paths should remain green.

The regression must target the confirmed warning signature rather than all Python `ResourceWarning` categories, avoiding unrelated false positives.

### GREEN

For each successful cold/warm service-load test that retains `fixture@1.0`, explicitly call `service.unload("fixture@1.0")` **inside the `TemporaryDirectory` context** after its assertions, preferably in a `try/finally` so an assertion failure still releases the lease before filesystem teardown.

Do not use `unittest.addCleanup` for this ownership boundary: unittest cleanups run after the test method returns, which is too late because the nested `TemporaryDirectory` context has already removed the cache root.

At least one successful path must additionally prove that after explicit unload the cache object is no longer protected by the lease and can be removed normally. This binds the warning cleanup to the actual runtime ownership contract instead of merely silencing diagnostics.

## Test gates

1. Commit only the warning-capture regression and observe the intended RED failures.
2. Apply only explicit in-context unload cleanup and the focused post-unload removal assertion.
3. Run full Foundation.
4. Require the existing Linux/macOS/Windows Context-Fabric cache lifecycle lanes to remain green; no production lock semantics are being changed.
5. Inspect the Foundation log to confirm the delayed cache-lock warnings are absent, not merely tolerated.
6. Freeze the exact head and perform a logically independent adversarial review focused on:
   - whether successful loads remain protected until explicit unload;
   - whether cleanup happens before temporary filesystem teardown;
   - whether failed/cancelled loads still release correctly;
   - whether any warning is globally suppressed;
   - whether the change accidentally weakens cross-process eviction safety.

Any review blocker starts a new regression RED -> minimal fix -> full GREEN -> fresh review loop.

## Acceptance criteria mapping

- Normal load-smoke unit execution emits no unclosed cache-object lock `ResourceWarning`.
- The reproduced teardown path has deterministic regression coverage.
- Explicit unload releases the cache lease and permits normal object removal.
- Existing failed acquisition/contention behavior is unchanged.
- Existing cross-process cache lifecycle tests remain green on Linux, macOS, and Windows.
- No global warning suppression or speculative production finalizer is introduced.
