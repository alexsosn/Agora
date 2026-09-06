# Context-Fabric cold-load safety

**State:** design gate for [#37](https://github.com/alexsosn/Agora/issues/37)  
**Related:** [#38](https://github.com/alexsosn/Agora/issues/38), [#46](https://github.com/alexsosn/Agora/issues/46)  
**Baseline:** Agora `main` at `fc300012900e563720e6dac9ae4ebaef0ead5b54`  
**Checked:** 2026-09-06

## Decision summary

Agora should contain **cold** Context-Fabric compilation in a separate subprocess and put an Agora-owned resource/lifecycle boundary around that worker: conservative free-space preflight, observed compiled-size/free-space/time guards, cross-process duplicate suppression, observable state, explicit cancellation, and cleanup of incomplete derived output.

The adapter must preserve upstream semantics. The worker calls the pinned public `cfabric_mcp.corpus_manager.load(...)` operation unchanged. After the worker exits successfully, Agora verifies that the current-format `.cfm` completion marker exists and only then invokes the existing loader in the parent process, which is therefore a warm upstream load.

[#38](https://github.com/alexsosn/Agora/issues/38) load-cost metadata is useful selection guidance but is **not a prerequisite** for #37. Runtime safety must not trust single-machine performance measurements as a hard guarantee.

## Why this is Agora-owned

The Context-Fabric compiler is allowed to be expensive. The Agora-specific failure is that Agora advertises dynamic lazy `load_corpus`, materializes data into its own managed cache, and currently places no integration-level resource boundary around the synchronous upstream cold load.

This change belongs to Agora's process launch, cache lifecycle, resource selection, and marketplace UX responsibilities. It does not change feature parsing, graph construction, corpus contents, or scholarly/query semantics.

The adapter must remain:

- **necessary for integration:** Agora added dynamic lazy loading on top of an upstream MCP that does not expose a cancellable cold-load job;
- **semantics-preserving:** the worker invokes the same upstream load method with the same path, logical name, and feature request;
- **public-boundary first:** no compiler monkey-patch, callback shim, or replacement algorithm;
- **small/removable:** delete the wrapper if upstream later supplies a public safe progress/cancellation primitive;
- **visible:** limits, status, cancellation, and failures are explicit Agora behavior.

## Reproduced current boundary

### Agora already protects source materialization, not compilation

`plugins/context-fabric/src/agora_context_fabric/gitstore.py` currently defines:

- a 3 GiB snapshot soft target (`AGORA_CORPUS_CACHE_MAX_GB`); and
- a 6 GiB minimum free-space reserve (`AGORA_CORPUS_MIN_FREE_GB`).

`GitStore._ensure_free_reserve()` is used during Git snapshot export/materialization. `prune()` and `cache_status()` also expose the reserve and cache limits.

`ContextFabricService.load()`, however, prepares the corpus, acquires a cache-object lease, and then directly calls `self.loader.load(...)`. No compile-specific guard exists between preparation and that call. The current reserve therefore does not bound the later `.cfm` write amplification.

### Exact pinned upstream versions and sources

Agora pins `cfabric-mcp==0.1.7`; the current lock resolves Context-Fabric 0.5.7. Both were inspected at upstream monorepo commit:

`3a38ca80e617d872ce1664e0f0740486d0e7e8ac`

Primary paths:

- `libs/mcp/pyproject.toml` — `cfabric-mcp` 0.1.7;
- `libs/core/pyproject.toml` — `context-fabric` 0.5.7;
- `libs/mcp/cfabric_mcp/corpus_manager.py`;
- `libs/core/cfabric/core/fabric.py`;
- `libs/core/cfabric/io/compiler.py`;
- `libs/core/cfabric/core/config.py`.

Stable source root:

<https://github.com/Context-Fabric/context-fabric/tree/3a38ca80e617d872ce1664e0f0740486d0e7e8ac>

### Upstream cold load is synchronous and not cancellable

`CorpusManager.load()` constructs `cfabric.Fabric` and synchronously calls either `CF.load(features, silent="deep")` or `CF.loadAll(silent="deep")`. It exposes no cancellation token, progress callback, disk budget, byte limit, or deadline.

A timed-out MCP request therefore cannot safely stop an arbitrary in-process Python thread already executing upstream compilation.

### Cold load auto-compiles `.cfm`

`Fabric.load()` checks for a usable `.cfm/<CFM_VERSION>/meta.json`. If none is present, it loads `.tf` data and automatically invokes `self.compile(...)` after constructing the API. The pinned runtime has `CFM_VERSION = "1"`.

`Compiler.compile()` defaults to `{source_dir}/.cfm/<CFM_VERSION>/`, creates directories there, writes arrays/features directly, and writes `meta.json` at the end. It has no transactional output directory or cancellation/progress callback.

Consequences:

1. interrupted work can leave a large incomplete current-format `.cfm` tree;
2. a size estimate alone cannot safely bound an underestimated compile;
3. a same-process watchdog cannot reliably stop the upstream work;
4. process containment is the smallest killable boundary available without changing upstream semantics.

### Feature selection does not bound cold compilation

For a feature subset, `Fabric.load(features)` still auto-compiles. `_gather_precomputed_data()` returns `None` unless all `.tf` features are already loaded, so the compiler then falls back to reading/compiling all direct `.tf` files.

`features=` may reduce the API surface in memory, but it must **not** reduce Agora's cold-compile disk budget.

### Measured amplification justifies a conservative default

Controlled observations already recorded in #37/#38 on one macOS x86_64 machine:

| Resource | Source `.tf` | Compiled `.cfm` | Amplification |
| --- | ---: | ---: | ---: |
| `cuc` | 3.1 MB | 20 MB | 6.5× |
| `bhsa` | 165 MB | 866 MB | 5.2× |
| `TLHdig-TF` | 388 MB | 4.6 GB | ~12× |

These are evidence that the ratio is not constant, not portable performance promises.

## Safety and UX requirements

1. A cold compiler must not be started unless preflight shows enough free space for the selected compile budget **plus** the configured host reserve.
2. Once running, Agora must continuously observe compiled output, free space, elapsed time, and cancellation and terminate the worker when a configured threshold is observed as crossed.
3. The byte/time monitors are polling guards, not filesystem quotas. The contract must not claim byte-perfect prevention of overshoot between samples. The configured free-space reserve is deliberately retained as detection/termination headroom rather than promised as an exact residual byte count.
4. A timed-out/disconnected client must not turn the worker into unbounded background work: server-side byte/free-space/time limits remain active until the worker exits.
5. Retrying the same cold load must not create a second compiler for the same exact prepared cache object, including across Agora server processes.
6. Cancellation must be possible for an active cold worker owned by the current server process.
7. Failed/cancelled/limited cold loads must release their cache lease and reclaim only incomplete derived current-format `.cfm` output owned by that attempt.
8. No per-call override may disable `AGORA_CORPUS_MIN_FREE_GB`. Users who intentionally want a smaller reserve must change that explicit server configuration.
9. `corpus_cache_status` must expose active cold loads with at least: `load_id`, resource/member/logical name, phase, elapsed time, source bytes, observed compiled bytes, hard compile budget, observed free bytes, configured reserve, and cancellation capability.
10. Add narrow `cancel_corpus_load(load_id)` UX. Repeated cancellation is safe.
11. Guard failures must be actionable and report relevant measured limits plus `corpus_cache_status` / `prune_corpus_cache` guidance.
12. A genuinely warm current-format cache keeps the existing direct loader path and does not pay the cold-worker/preflight cost.

## Selected design

### 1. Cold worker invokes the unchanged upstream loader

Add a small Agora worker module whose substantive operation is only:

```python
from cfabric_mcp.corpus_manager import corpus_manager
corpus_manager.load(path, name=name, features=features)
```

The worker runs in the same installed/pinned environment as the MCP server. It does not return a scholarly result to the parent. Its purpose is containment of the cold compilation phase.

After worker success the parent **must first verify** that the expected current-format completion marker exists. Only then may it call the existing in-process `self.loader.load(...)`. If the worker exits zero but the marker is absent, treat that as failed cold compilation, clean the incomplete current-format output, and do not call the parent loader; this prevents a silent second cold compile in the main MCP process.

### 2. Isolate warm/cold compatibility detection

Use one small helper that reads Context-Fabric's runtime `CFM_VERSION` and resolves:

`prepared.path / ".cfm" / CFM_VERSION / "meta.json"`

The helper is an integration/storage compatibility coupling, not a semantic reimplementation. Cover it with a runtime-environment regression so a dependency update cannot silently change the storage contract.

A first warm check provides the fast path. A second warm check is required after the compile lock is acquired (see concurrency protocol) because another process may have completed the cache between those two points.

### 3. Derive the default budget from the actual prepared source bytes

After `prepare_with_modules()` returns, sum direct `*.tf` file sizes in `prepared.path`, which is the directory Context-Fabric compiles. Do not use repository size, collection size, Git metadata, or `features=`.

Default observed-output budget:

```text
max(256 MiB, source_tf_bytes × 16)
```

Rationale:

- 16× is above the largest currently observed ~12× amplification;
- 256 MiB avoids unrealistically tiny limits for small corpora with fixed computed structures;
- the process monitor is the final containment mechanism; the multiplier is conservative integration policy, not a prediction guarantee.

Allow `max_compile_gb` as an explicit positive per-load override. It changes the observed-output threshold and preflight reservation, never the host reserve.

### 4. Preflight on the cache filesystem

For a cold worker require:

```text
free_bytes >= min_free_bytes + compile_budget_bytes
```

Measure free bytes from the same filesystem containing the prepared cache object / `.cfm` output. If the requirement is not met, refuse before spawning and include measured free/budget/reserve values in the error.

This is intentionally conservative. Users with better measurements may choose a smaller explicit `max_compile_gb`, while the runtime monitor still contains underestimation.

### 5. Poll and contain the worker honestly

While the child is alive, sample at a bounded short interval (target 0.5–1.0 s):

- current `.cfm/<version>` bytes;
- free bytes on the same filesystem;
- monotonic elapsed time;
- cancellation event.

Terminate when an output, free-space, timeout, or cancellation threshold is observed. After a short grace period, kill if necessary, then wait for process death **before** cleanup.

Because this is polling, output/free-space values may move between samples. The implementation and messages must call these **observed thresholds**, not claim an OS-level quota or exact byte-perfect cap. The existing multi-GiB minimum free-space reserve is the host-safety cushion for detection/termination latency.

Default wall-time threshold: 60 minutes. Allow positive `max_compile_minutes` override. Time and byte overrides never disable the free-space reserve.

### 6. Exact concurrency and lock ordering

Use a dedicated exclusive cross-process **compile lock** keyed by the exact managed prepared cache object. Do not overload the cache object's shared lease lock.

Required order for a cold candidate:

1. prepare and acquire the existing source/overlay cache lease under the normal short cache-transition protocol;
2. leave `cache_transition` — never hold the transition lock while waiting for a compiler, spawning, monitoring, terminating, or warm-loading;
3. perform a warm fast-path check;
4. reserve/check the same-process active-load identity so a local retry can fail fast;
5. acquire the dedicated compile lock with fail-fast/short-timeout semantics;
6. **re-check the warm marker while holding the compile lock**;
7. if now warm, release the active reservation/compile lock and use the normal warm parent load;
8. if still cold, perform final preflight, register the active worker state, then spawn and monitor;
9. after worker death, verify success/marker or clean failure while the compile lock still prevents a competing cold compiler;
10. release compile lock and active reservation in `finally` paths; release the cache lease according to existing load success/failure semantics.

The same-process active reservation must be race-safe: check-and-reserve is one operation under its own lock, and every exit path clears it. A failed compile-lock acquisition must not leave a fake active job in status.

This protocol prevents the race:

- process A sees cold;
- process B finishes compilation;
- A later acquires the compile lock;
- A re-checks and observes warm instead of starting a redundant second compiler.

### 7. Active load state and cancellation

Maintain a thread-safe in-memory map keyed by `load_id` plus a same-object identity index used for local duplicate suppression.

Suggested phases:

- `preflight`;
- `compiling`;
- `warm-load`.

`corpus_cache_status()` merges current `active_loads` into the existing cache status. This is live state, not durable job history. Once the operation has definitively returned/raised and no worker remains, the active record may be removed.

`cancel_corpus_load(load_id)` sets the load's cancellation event and returns structured state (`found`, `load_id`, `cancellation_requested`, `phase`). The monitor remains the single owner of worker termination and cleanup.

Cancellation is process-local. A compiler owned by another Agora server process cannot be cancelled by this process; the cross-process lock merely prevents a duplicate compiler.

### 8. Failure cleanup is narrow and ordered

A cold worker is only allowed when the current-format completion marker is absent after the compile-lock recheck.

After worker failure/cancellation/limit termination:

1. terminate/kill as needed;
2. wait until the worker is confirmed dead;
3. while still owning the compile lock, remove only `prepared.path/.cfm/<current-version>`;
4. never remove direct `.tf` source, other CFM versions, repository metadata, sibling cache objects, or an independently valid pre-existing current-format cache.

If cleanup itself fails, report that explicitly with the residual path; do not disguise it as a successful cancellation.

Capture child exit diagnostics in a bounded way so a normal upstream load exception is actionable without allowing unbounded stderr/stdout accumulation.

## Configuration surface

Existing:

- `AGORA_CORPUS_MIN_FREE_GB` — host-safety reserve; default 6 GiB.

New defaults (names may change only with tests/docs updated together):

- `AGORA_CORPUS_COMPILE_MAX_MULTIPLIER=16`;
- `AGORA_CORPUS_COMPILE_MIN_GB=0.25`;
- `AGORA_CORPUS_COMPILE_MAX_MINUTES=60`.

`load_corpus` adds optional positive values:

- `max_compile_gb: float | None`;
- `max_compile_minutes: float | None`.

Neither may disable `AGORA_CORPUS_MIN_FREE_GB`.

## Relationship to #38

#38 remains a separate metadata/description ticket.

Measured `load_cost` metadata answers "what is this likely to cost on a representative system?" and helps selection before materialization. #37 answers "can this particular Agora-triggered cold compile become unbounded or silently keep consuming the host?"

The runtime guard must not use #38's single-machine measurements as a hard guarantee, and #38 should not wait for the worker implementation.

## Rejected alternatives

### Preflight estimate only

Rejected. Future corpora may exceed the observed amplification range. Without a killable process boundary, underestimation can still continue after client timeout.

### In-process watchdog thread

Rejected. Python cannot safely terminate another thread inside the upstream compiler.

### Patch Context-Fabric with private callbacks/cancellation

Rejected for Agora. It would be a third-party behavioral fork. A public upstream cancellation/progress API would be welcome and could later replace this wrapper.

### Make `load_corpus` a fully asynchronous job API

Rejected for this ticket. It is a much larger public contract change. Preserve synchronous success semantics while exposing status/cancel only for the contained cold phase.

### Depend on #38 measurements for the hard threshold

Rejected. Those measurements are useful guidance, not portable safety guarantees.

### Treat polling as a filesystem quota

Rejected. Cross-platform portable Python cannot promise byte-perfect interception between writes. The design instead combines conservative preflight reservation, a killable worker, frequent observed-threshold checks, and a large explicit free-space reserve.

## TDD implementation gate

No production implementation should be committed before RED tests establish the Agora-owned contracts.

### RED contract tests

1. cold low-space preflight refuses before starting a worker;
2. source budget uses direct prepared `.tf` bytes, not `features=` or repository size;
3. default budget is `max(floor, source × multiplier)` and overrides validate positively;
4. valid current-format warm cache bypasses the worker and cold preflight;
5. worker invokes upstream loader with unchanged path/name/features;
6. observed output-threshold crossing terminates/kills worker and cleans incomplete current-format `.cfm`;
7. observed free-space threshold terminates worker and messages do not claim byte-perfect quota semantics;
8. timeout terminates worker;
9. `cancel_corpus_load` cancels an active worker and is idempotent;
10. `corpus_cache_status` exposes required live progress fields;
11. same-object local duplicate is fail-fast without a second spawn;
12. cross-process compile lock prevents duplicate compiler;
13. cold/warm race rechecks completion marker after compile-lock acquisition;
14. worker success without current-format `meta.json` fails before parent loader, preventing a main-process cold fallback;
15. successful cold worker with marker is followed by existing in-process loader and preserves `load_corpus` result shape;
16. cache lease/active reservation/compile lock are released on preflight, lock, spawn, worker, cancellation, timeout, cleanup, marker-verification, and parent warm-load failures;
17. failed cleanup reports residual output instead of claiming success;
18. cleanup removes only incomplete current-format `.cfm`; source `.tf`, other CFM versions, and valid pre-existing cache remain untouched;
19. cache-transition lock is not held during worker wait/monitor/warm load;
20. MCP registration/docs expose optional limits and cancellation without changing scholarly operations;
21. dependency/storage compatibility test binds the warm/cold helper to the installed Context-Fabric `CFM_VERSION`.

### GREEN gate

- focused safety tests pass;
- full unit suite passes;
- cache lifecycle and lock regressions pass on Linux/macOS/Windows;
- existing representative Context-Fabric load smoke passes;
- generated marketplace/runtime artifacts remain fresh;
- a tiny-fixture integration demonstrates cold worker -> current `.cfm` marker -> parent warm load without a large corpus in CI.

## Independent review gate

Before the implementation PR is ready, perform a logically independent skeptical review against this design and `ref-plugin-boundary.md`. Explicitly challenge:

1. whether the worker preserves upstream loader semantics;
2. whether any path can still trigger cold compilation in the main MCP process;
3. whether preflight/output/free-space measurements use the correct filesystem and byte units;
4. whether polling guarantees are described honestly;
5. whether worker death is confirmed before cleanup;
6. whether warm/cold and duplicate races are closed across threads/processes;
7. whether lock ordering can deadlock cache lifecycle operations;
8. whether every error path releases leases/locks/reservations;
9. whether cleanup can touch `.tf`, another CFM version, or a valid cache;
10. whether warm loads are accidentally subjected to cold-only policy;
11. whether tests validate Agora lifecycle/safety rather than upstream corpus semantics.

## Open upstream opportunity

A public Context-Fabric compile primitive with atomic output plus progress/cancellation callbacks would be cleaner long term. Propose that upstream separately. #37 should not depend on it because Agora can contain its own dynamic-load integration without changing upstream behavior.
