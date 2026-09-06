# Context-Fabric cold-load safety

**State:** design gate for [#37](https://github.com/alexsosn/Agora/issues/37)  
**Related:** [#38](https://github.com/alexsosn/Agora/issues/38), [#46](https://github.com/alexsosn/Agora/issues/46)  
**Baseline:** Agora `main` at `fc300012900e563720e6dac9ae4ebaef0ead5b54`  
**Checked:** 2026-09-06

## Decision summary

Agora should contain cold Context-Fabric compilation in a **separate subprocess** and enforce a preflight disk budget, a hard compiled-size/free-space/time monitor, cross-process duplicate suppression, and an observable/cancellable load state.

The adapter must call the pinned upstream loader unchanged; it must not patch Context-Fabric compilation semantics. A successful worker compile is followed by the existing in-process upstream load, which should then be a warm `.cfm` load.

`#38` load-cost metadata is useful user-facing guidance but is **not a prerequisite** for `#37`. Runtime safety can be derived from the actual prepared `.tf` bytes plus conservative defaults and hard runtime caps. Future measured metadata may improve warnings without weakening the guard.

## Why this is Agora-owned

The underlying Context-Fabric compiler is allowed to be expensive. The Agora-specific failure is that Agora advertises dynamic `load_corpus`, materializes data into its own managed cache, and currently gives the client no integration-level resource boundary around the upstream synchronous load.

This change therefore belongs to Agora's process launch, cache management, lifecycle, and marketplace UX responsibilities. It does not change scholarly results, feature parsing, graph construction, or query semantics.

The selected design satisfies the normative plugin-boundary test:

- **necessary for integration:** Agora adds dynamic lazy corpus loading that upstream `cfabric-mcp` itself does not expose as a cancellable job;
- **semantics-preserving:** the child calls the same public `cfabric_mcp.corpus_manager.load(...)` operation with the same path/name/features;
- **public-boundary first:** no compiler monkey-patch or alternate corpus algorithm is introduced;
- **small/removable:** when upstream exposes safe cancellation/progress/budgeting, the subprocess wrapper can be deleted;
- **visible:** status/errors make the adaptation and limits explicit.

## Reproduced current boundary

### Agora already protects source materialization, not compilation

`plugins/context-fabric/src/agora_context_fabric/gitstore.py` currently defines:

- a 3 GiB snapshot soft target (`AGORA_CORPUS_CACHE_MAX_GB`), and
- a 6 GiB minimum free-space reserve (`AGORA_CORPUS_MIN_FREE_GB`).

`GitStore._ensure_free_reserve()` is called during Git snapshot export/materialization. `prune()` and `cache_status()` also report/enforce the reserve when explicitly pruning.

However `ContextFabricService.load()` performs `prepare_with_modules()`, acquires a cache lease, then calls the loader directly. There is no compile-specific preflight or monitor between preparation and `self.loader.load(...)`.

Therefore the existing reserve does not bound `.cfm` growth produced later by Context-Fabric.

### Exact pinned upstream versions

Agora pins `cfabric-mcp==0.1.7`; its current lock resolves Context-Fabric 0.5.7. The upstream monorepo commit inspected for both releases is:

`3a38ca80e617d872ce1664e0f0740486d0e7e8ac`

Primary source paths:

- `libs/mcp/pyproject.toml` — `cfabric-mcp` 0.1.7
- `libs/core/pyproject.toml` — `context-fabric` 0.5.7
- `libs/mcp/cfabric_mcp/corpus_manager.py`
- `libs/core/cfabric/core/fabric.py`
- `libs/core/cfabric/io/compiler.py`
- `libs/core/cfabric/core/config.py`

Stable source root:

<https://github.com/Context-Fabric/context-fabric/tree/3a38ca80e617d872ce1664e0f0740486d0e7e8ac>

### Upstream load is synchronous and has no cancellation/progress hook

`CorpusManager.load()` constructs `cfabric.Fabric` and synchronously calls either `CF.load(features, silent="deep")` or `CF.loadAll(silent="deep")`. It does not accept a cancellation token, progress callback, disk budget, output limit, or deadline.

That matters because a cancelled/timed-out MCP request cannot safely terminate an arbitrary in-process Python thread that is inside the upstream loader.

### Cold load auto-compiles `.cfm`

Context-Fabric `Fabric.load()` first checks for a valid current `.cfm/<CFM_VERSION>/meta.json`. If there is no usable cache, it loads `.tf` data and, after creating the API, automatically calls `self.compile(...)`.

The pinned runtime uses `CFM_VERSION = "1"`.

### Compilation writes directly into the corpus tree

`Compiler.compile()` defaults to:

`{source_dir}/.cfm/{CFM_VERSION}/`

It creates the target directories and writes arrays/features directly there. `meta.json` is written at the end of compilation. There is no transactional temporary output directory and no callback that Agora can use to stop at a byte threshold.

Consequences:

1. an interrupted compile can leave a large incomplete `.cfm/1` tree;
2. a preflight estimate alone cannot guarantee safety if amplification is underestimated;
3. a same-process watchdog cannot reliably kill the upstream work after an MCP cancellation;
4. a separate process is the clean containment boundary available without modifying upstream semantics.

### Feature selection does not solve cold compile cost

When `cfabric-mcp` is called with a feature subset, `Fabric.load(features)` still auto-compiles after the partial load. `Fabric._gather_precomputed_data()` deliberately returns `None` when not all `.tf` features are loaded, so `Compiler` falls back to reading and compiling all `.tf` files from disk.

Therefore `features=` may reduce the loaded API surface but **must not be treated as a cold-compile disk bound**.

### Measured amplification justifies a conservative default

Measurements already recorded on #37/#38 on one macOS x86_64 machine:

| Resource | Source `.tf` | Compiled `.cfm` | Amplification |
| --- | ---: | ---: | ---: |
| `cuc` | 3.1 MB | 20 MB | 6.5× |
| `bhsa` | 165 MB | 866 MB | 5.2× |
| `TLHdig-TF` | 388 MB | 4.6 GB | ~12× |

The ratio is not constant. These observations are not portable performance promises, but they are sufficient to reject a small fixed estimate and to choose a default cap above the largest observed multiplier.

## Requirements

### Safety requirements

1. A cold compile must not start when the configured free-space reserve plus the selected compile budget cannot be preserved.
2. Once started, Agora must terminate the compile worker before:
   - current `.cfm` output exceeds its hard byte cap;
   - free disk falls below the configured reserve; or
   - the compile exceeds its wall-time cap.
3. A timed-out/disconnected client must not remove those caps; the server-side worker remains bounded.
4. Retrying the same cold load must not start a second compiler for the same prepared cache object.
5. Cancellation must be possible while a cold compile is active.
6. Failed/cancelled cold compiles must release the Agora cache lease and reclaim the incomplete `.cfm` tree created by that attempt.
7. No safety override may silently bypass `AGORA_CORPUS_MIN_FREE_GB`; users who intentionally want a smaller host reserve must change that explicit configuration.

### UX requirements

1. `corpus_cache_status` must expose active cold loads and their observable progress.
2. An active load record must include enough information to explain what is consuming disk:
   - stable `load_id`;
   - resource/member/logical name;
   - phase;
   - elapsed time;
   - source bytes;
   - current compiled bytes;
   - hard compile budget;
   - current free bytes and configured reserve;
   - whether cancellation is currently possible.
3. Add a narrow `cancel_corpus_load(load_id)` tool. Cancellation is idempotent and only controls an Agora-owned active cold-load worker in this server process.
4. Guard failures must be actionable: report the measured free space/budget/reserve and point to `corpus_cache_status` / `prune_corpus_cache` or an explicit per-load budget override where appropriate.
5. Warm loads should retain the current direct behavior and should not pay the cold-worker cost when a valid current `.cfm` cache already exists.

## Selected design

### 1. Isolate the cold upstream load in a worker process

Add a small Agora worker module whose only substantive operation is:

```python
from cfabric_mcp.corpus_manager import corpus_manager
corpus_manager.load(path, name=name, features=features)
```

The worker uses the same installed/pinned environment as the MCP server. It does not return a scholarly result to the parent; success only proves that upstream completed and produced its normal current `.cfm` cache.

After worker success, the parent calls the existing `self.loader.load(...)` in-process. Because a valid `.cfm` now exists, this is the ordinary upstream warm-load path and populates the real server's global corpus manager exactly as today.

This deliberately accepts one additional warm-load pass after a cold compile in exchange for a killable cold phase.

### 2. Detect warm vs cold using the pinned runtime's CFM format version

Isolate the compatibility coupling in one helper that reads Context-Fabric's runtime `CFM_VERSION` and checks:

`prepared.path / ".cfm" / CFM_VERSION / "meta.json"`

Using the runtime's version constant is storage/integration compatibility, not a semantic fork. Keep this helper small and covered by a runtime-environment regression so a future Context-Fabric upgrade cannot silently invalidate the warm/cold decision.

If the valid current cache exists, skip the worker and call the existing loader directly.

### 3. Compute a cold compile budget from actual prepared `.tf` bytes

After `prepare_with_modules()` returns, sum direct `*.tf` file sizes in `prepared.path`; this is the source directory Context-Fabric compiles. Do not use repository size, Git metadata, collection size, or `features=`.

Default hard budget:

```text
max(256 MiB, source_tf_bytes × 16)
```

Rationale:

- 16× is above the largest currently measured ~12× amplification;
- 256 MiB avoids an unrealistically tiny cap for small corpora with fixed computed structures;
- the hard runtime monitor, not the multiplier, is the final safety boundary.

The multiplier/floor are integration policy, not claims about upstream performance. They should be named constants/config values and documented as conservative defaults.

Allow a per-call `max_compile_gb` override for unusual corpora. It changes the output cap and preflight requirement but never disables the free-space reserve.

### 4. Preflight free disk before spawning

For a cold load require:

```text
free_bytes >= min_free_bytes + hard_compile_budget_bytes
```

If not, fail before starting the worker with the measured values and remediation guidance.

This is intentionally conservative. A user with reliable measurements can provide a smaller explicit `max_compile_gb`, while still preserving the configured host reserve.

### 5. Enforce hard limits while the worker runs

Monitor at a short bounded interval (target: 0.5–1.0 s):

- current `.cfm/<version>` directory bytes;
- free bytes on the cache filesystem;
- elapsed monotonic time;
- cancellation event.

Terminate the worker when any guard is crossed. After a short termination grace period, kill it if necessary and wait for process exit before cleanup.

Default wall-time cap: **60 minutes**. Allow a smaller/larger explicit per-load `max_compile_minutes` value. The timeout does not bypass the disk reserve or byte cap.

### 6. Prevent duplicate cold compilers

Add a dedicated cross-process compile lock keyed by the exact managed prepared cache object. Do not overload the existing shared cache-object lease lock.

Behavior:

- source object remains leased so prune/remove cannot detach it;
- compile lock is exclusive across Agora server processes;
- a second cold-load attempt for the same object fails fast with a clear "compile already in progress" error instead of waiting through a client timeout or launching another compiler.

Within one service process, register the active load before spawning so duplicate retries are also rejected immediately rather than blocking on `_lifecycle_lock`.

### 7. Track active load state in the service

Maintain a thread-safe in-memory map keyed by `load_id` and an index by prepared path/logical name.

Phases:

- `preflight`
- `compiling`
- `warm-load`
- terminal states are removed from `active_loads` after the requesting call receives/raises; final error text remains in the tool exception.

`corpus_cache_status()` merges `active_loads` into the existing cache report. This makes a compile that outlives the initiating MCP request discoverable to another request handled by the same server.

### 8. Add explicit cancellation

`cancel_corpus_load(load_id)` sets the load's cancellation event. The monitor performs the process termination/cleanup so there is one owner of worker lifecycle.

Return a structured result:

- `found`
- `load_id`
- `cancellation_requested`
- current phase

Repeated cancellation is safe.

Do not attempt to cancel arbitrary upstream warm loads or a compiler owned by a different Agora process. Cross-process duplicate suppression prevents Agora from creating that second compiler; cancellation remains process-local and explicit.

### 9. Clean only derived output owned by the failed attempt

Before spawning, record whether a valid current `.cfm/<version>/meta.json` existed. A cold worker only starts when it did not.

After worker failure/cancel/limit termination:

- wait until the worker is dead;
- remove only `prepared.path/.cfm/<current-version>`;
- never delete `.tf` source data, other CFM format versions, repository metadata, or unrelated cache objects.

This both reclaims disk immediately and prevents a later upstream load from tripping over a partial current-format cache.

## Configuration surface

Existing:

- `AGORA_CORPUS_MIN_FREE_GB` — hard host reserve; default 6 GiB.

New defaults (names may be adjusted during implementation only if tests/docs are updated together):

- `AGORA_CORPUS_COMPILE_MAX_MULTIPLIER=16`
- `AGORA_CORPUS_COMPILE_MIN_GB=0.25`
- `AGORA_CORPUS_COMPILE_MAX_MINUTES=60`

`load_corpus` adds optional:

- `max_compile_gb: float | None`
- `max_compile_minutes: float | None`

Both must be positive when supplied. Neither may disable `AGORA_CORPUS_MIN_FREE_GB`.

## Relationship to #38

`#38` should remain a separate metadata/description ticket.

Measured `load_cost` metadata can answer "should I choose/load this corpus?" before materialization and can provide realistic time/size guidance. `#37` answers "can this particular cold compile damage the host or become an unbounded hidden job?"

The runtime guard should not trust single-machine `load_cost` measurements as a hard safety guarantee. Conversely `#38` should not be blocked on the worker implementation.

## Rejected alternatives

### Preflight estimate only

Rejected. A 16× estimate is conservative relative to current observations but cannot prove every future corpus stays below it. Without a killable worker, underestimation can still fill the disk.

### In-process watchdog thread

Rejected. Python cannot safely terminate another thread executing the upstream compiler. MCP request cancellation/timeouts therefore remain unable to bound the work.

### Patch Context-Fabric compiler with callbacks/cancellation

Rejected for Agora. That capability would be useful upstream, but carrying a monkey-patch/private shim would violate the marketplace ownership boundary. Agora may later delete its worker when an upstream public cancellation/progress API exists.

### Make `load_corpus` purely asynchronous/job-based

Rejected for this ticket. It would be a larger public contract change. Keeping synchronous success semantics plus status/cancel for the cold phase fixes the safety bug with a smaller adapter.

### Depend on #38 measurements for the hard limit

Rejected. The measurements are platform/version/workload observations, not portable guarantees. Runtime safety must remain independent.

## TDD implementation gate

No production implementation should be committed before RED tests establish these contracts.

### RED contract tests

1. cold low-space preflight refuses before starting a worker;
2. cold budget is based on direct prepared `.tf` bytes, not `features=` or repository size;
3. default budget is `max(floor, source × multiplier)` and explicit overrides validate correctly;
4. warm current-format cache bypasses the compile worker;
5. worker invokes the upstream loader with unchanged path/name/features;
6. output-cap crossing terminates/kills worker and cleans incomplete current-format `.cfm`;
7. free-space-reserve crossing terminates worker before the reserve is consumed;
8. timeout terminates worker;
9. `cancel_corpus_load` terminates an active worker;
10. `corpus_cache_status` exposes active-load progress fields;
11. duplicate same-object cold load is rejected before a second worker starts, including a cross-process lock regression;
12. cache lease is released on preflight, spawn, worker, cancellation, timeout, cleanup, and warm-load failures;
13. successful cold worker is followed by the existing in-process loader and preserves the existing `load_corpus` result shape;
14. partial current-format `.cfm` is removed after a failed attempt, but pre-existing valid cache/other CFM versions are not removed;
15. source snapshots and `.tf` bytes are never mutated/deleted by cleanup;
16. MCP registration/docs expose the new optional limits and cancellation tool without changing scholarly operations.

### GREEN gate

- focused new safety tests pass;
- full unit suite passes;
- cache lifecycle/lock regressions pass on Linux/macOS/Windows;
- existing representative Context-Fabric load smoke passes;
- generated marketplace/runtime artifacts remain fresh;
- one tiny-fixture cold-load integration test demonstrates worker -> `.cfm` -> warm parent load without requiring a large corpus in CI.

## Independent review gate

Before marking the implementation PR ready, perform a logically independent skeptical review against this document and the normative plugin boundary. The reviewer should explicitly challenge:

1. whether the subprocess adapter actually preserves upstream loader semantics;
2. whether any path still allows cold compilation in the main MCP process;
3. whether preflight and runtime limits use the same filesystem and byte units;
4. whether termination waits for worker death before deleting `.cfm`;
5. whether duplicate retries can race across threads/processes;
6. whether cancellation/status can deadlock the existing lifecycle/cache locks;
7. whether a cleanup path can touch `.tf` source or a valid cache;
8. whether warm loads are accidentally blocked by cold-only budget policy;
9. whether tests validate Agora lifecycle/safety rather than upstream corpus semantics.

## Open upstream opportunity

A public Context-Fabric compile API with an atomic output directory plus progress/cancellation callbacks would be a cleaner long-term primitive. That should be proposed upstream separately. Agora should not block #37 on that upstream enhancement because process containment can solve the integration safety failure without changing upstream behavior.
