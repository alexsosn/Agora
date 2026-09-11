# Context-Fabric cache and cold-load safety

Agora acquires registered Text-Fabric corpora lazily into its managed Context-Fabric cache. A first load can require Context-Fabric to compile `.tf` source files into its current `.cfm` format; later loads of a valid current-format cache use the normal warm upstream loader path.

## Recommended first-load workflow

For an unfamiliar or potentially large resource, use `describe_available_corpus` → `prepare_corpus` → `load_corpus` rather than jumping directly to load. `describe_available_corpus` exposes the registered resource and historical `load_cost` evidence when one exists. `prepare_corpus` separates source resolution/acquisition from the Text-Fabric load and, for module combinations, exposes `load_preflight` before a cold compile is attempted.

Long `prepare_corpus` and `load_corpus` calls yield the MCP event loop. When the client requested MCP progress, Agora reports coarse stage names rather than invented ETAs:

- `resolving` — validate the request and choose the registered source/member/revision;
- `acquiring/materializing` — refresh/read Git metadata and create or reuse immutable source snapshots/overlays;
- `loading/compiling` — enter the Text-Fabric load boundary, including a contained cold compile when needed;
- `ready` — the operation completed and the result can be used.

Acquisition/materialization and cold compilation have separate limits. The default acquisition/materialization wall-clock budget is **15 minutes**, controlled by `AGORA_CORPUS_ACQUISITION_MAX_MINUTES`. The default contained cold-compile wall-clock limit is **60 minutes**, controlled by `AGORA_CORPUS_COMPILE_MAX_MINUTES`. Both are safety limits, not expected durations or ETAs.

If a cold load already appears in `corpus_cache_status.active_loads`, **do not retry** the same load blindly. Inspect that record instead. It exposes the exact active object, phase and limits; use `cancel_corpus_load` with its `load_id` if cancellation is appropriate. A duplicate local cold load is deliberately rejected rather than spawning a second compiler.

Protocol cancellation of a long MCP request is bridged to Agora-owned acquisition/materialization work and to the contained cold compiler. The handler waits until its owned worker has stopped before unwinding, so cancellation does not intentionally leave a mutating background thread behind. The final in-process upstream warm-loader call is a non-preemptible boundary: if cancellation arrives while that call is already running, Agora waits for it to return rather than killing arbitrary upstream Python state. After an interrupted request, inspect `corpus_cache_status` (including `loaded_corpora` and `active_loads`) before deciding whether to retry.

Historical `load_cost` observations are environment-specific evidence, not predictions. For example, the recorded BHSA release measurement reports roughly 165 MB of source, 866 MB compiled, about 1.1 GB total cache and about 630 seconds for the measured first load. Different corpus revisions, Context-Fabric versions, machines, filesystems and module combinations can differ materially.

## Source resolution and offline use

Acquisition-bearing tools (`list_collection_members`, `prepare_corpus`, and `load_corpus`) accept an optional `source_mode`:

- `prefer-fresh` — the default. Agora tries to refresh the configured upstream Git selection. If that refresh fails for a narrowly recognized connectivity reason, it may reuse the previous local selection, but the remainder of that operation becomes cached-only.
- `offline` — deterministic zero-network acquisition. Agora does not clone, fetch, lazily retrieve Git blobs, or create a source snapshot through the export-fetch path. The exact metadata selection, collection index where applicable, and source snapshots required by the operation must already be resident.
- `require-fresh` — requires a successful upstream refresh. Refresh failure is returned as an error and cached state is not substituted.

Prepared/loaded results report the immutable `source_revision` together with `source_resolution` (`remote`, `cached`, or `explicit-revision`) and `source_revision_verified`. The verification flag describes whether current upstream freshness was established during that operation; an immutable cached SHA remains the source identity even when freshness is unverified.

An explicit immutable collection `source_revision` pins historical identity. It can be combined with `offline` when the required revision/index/snapshot state is resident. Combining an explicit `source_revision` with `require-fresh` is rejected because the two controls request incompatible resolution semantics.

A cached Git commit is not by itself enough for offline materialization. Agora publishes revision-addressed corpus and feature-module source snapshots; those published snapshots are the offline source-byte boundary. If a required snapshot was pruned or evicted, reconnect and run a network-enabled prepare/load once to publish it again before using `offline`.

Collection discovery also needs an installed or previously generated member index matching the exact selected revision. Offline mode refuses to regenerate a missing index from a partial Git clone because reading missing metadata blobs could otherwise trigger an implicit network request.

Authentication, authorization, repository-not-found, missing-ref, and unclassified Git refresh failures are not treated as ordinary offline connectivity failures. They remain explicit errors instead of silently serving stale state.

## Cold compilation guardrails

Agora runs cold Context-Fabric compilation in a separate worker process. The worker calls the pinned public `cfabric_mcp.corpus_manager.load(...)` operation with the same corpus path, logical name, and requested features. Agora does not replace or modify Context-Fabric's corpus semantics.

Before starting a cold worker, Agora measures the direct `*.tf` files in the prepared corpus directory and requires enough free space for the selected compile budget while preserving the configured host reserve. While the worker runs, Agora polls compiled output size, free disk space, elapsed time, and cancellation state. If an observed threshold is crossed, Agora stops and reaps the worker before cleaning incomplete current-format derived output.

These are polling guardrails, not filesystem quotas. Writes can occur between observations. The minimum-free-space reserve is retained as safety headroom rather than advertised as an exact residual-byte guarantee.

## Feature-module overlays

Selecting feature modules creates a derived overlay for that exact parent revision and ordered module combination. The overlay is a complete Text-Fabric source directory, so a small module does not imply a proportionally small compile. A previously unseen combination can require a **parent-scale** cold compile and its own current-format `.cfm` cache.

Call `prepare_corpus(..., modules=[...])` before an unfamiliar or potentially expensive combination. Its `load_preflight` object reports:

- `cache_kind="overlay"`;
- `module_order` and `module_order_semantics="ordered-last-wins"`;
- `exact_combination_warm` and `full_compile_required` for the current CFM version;
- direct overlay `source_bytes`;
- the default `compile_budget_bytes` and `compile_timeout_seconds` that would govern a cold load unless the caller supplies stricter per-load overrides;
- the configured `min_free_bytes` host reserve;
- `cost_expectation="parent-scale-possible"`;
- `parent_historical_load_cost` when the parent resource has a measured historical record.

The warm/cold fields are a point-in-time observation. Another process may compile or evict the exact overlay after prepare returns, so `load_corpus` rechecks the current-format marker after taking the exact-object compile lock before deciding whether to start a worker.

Module order is semantic. Agora overlays module feature files in caller order, and if two modules expose the same feature filename the later module replaces the earlier one. The same module set in another order can therefore intentionally produce a different overlay; Agora must not sort module IDs merely to increase cache reuse.

Historical BHSA release investigation for issue #46 observed that adding two small feature modules (about 6 MB each) could add roughly **1.14 GB** of cache and about **7.5 minutes** of cold compilation on the measured machine. Those numbers are evidence of possible parent-scale amplification, not a guaranteed estimate for another machine, Context-Fabric version, corpus revision, or module combination. The canonical parent `load_cost` record is likewise historical context, not a promise of current runtime cost.

Recommended expensive-module workflow:

1. `prepare_corpus(..., modules=[...])`;
2. inspect `load_preflight` and, when disk pressure matters, `corpus_cache_status`;
3. call `load_corpus` only if the disclosed cold/warm state and limits are acceptable, optionally with stricter `max_compile_gb` / `max_compile_minutes`;
4. use `corpus_cache_status` while a cold worker runs and `cancel_corpus_load` when cancellation is needed;
5. after unload, use `prune_corpus_cache` or `remove_cached_corpus` to reclaim unused overlays.

Derived overlays are indexed as independent `kind="overlay"` cache objects. Their bytes are attributable in `corpus_cache_status`, active overlays are protected by leases, and unused overlays can be evicted without deleting the immutable parent or module source snapshots.

## Defaults

The server-side defaults are:

- `AGORA_CORPUS_MIN_FREE_GB=6` — minimum host free-space reserve. Per-load options cannot disable it.
- `AGORA_CORPUS_ACQUISITION_MAX_MINUTES=15` — wall-clock budget for request-owned Git/source acquisition and materialization before cold compilation.
- `AGORA_CORPUS_COMPILE_MAX_MULTIPLIER=16` — default compiled-output budget multiplier applied to direct prepared `.tf` bytes.
- `AGORA_CORPUS_COMPILE_MIN_GB=0.25` — minimum default compiled-output budget.
- `AGORA_CORPUS_COMPILE_MAX_MINUTES=60` — default cold-worker wall-time limit.

The default compiled-output budget is `max(0.25 GiB, source_tf_bytes × 16)`. All configured multiplier/minimum/time values must be positive finite numbers. `AGORA_CORPUS_MIN_FREE_GB` follows the cache lifecycle configuration and may be set to zero only through explicit server configuration; a `load_corpus` call cannot reduce it.

## Per-load controls

`load_corpus` accepts two optional positive values for cold loads:

- `max_compile_gb` — override the observed compiled-output budget for this load.
- `max_compile_minutes` — override the cold-worker wall-time limit for this load.

Omitting these fields keeps the server defaults. Warm current-format loads do not pay the cold-worker/preflight path. The acquisition/materialization budget is server-side in v1 and is intentionally separate from these per-load compile controls.

## Status and cancellation

`corpus_cache_status` includes `active_loads` for cold work owned by the current Agora server process. Active records include the load ID, resource/member/logical name, phase, elapsed time, source bytes, observed compiled bytes, compile budget, observed free bytes, configured reserve, and cancellation state.

Call `cancel_corpus_load(load_id)` with a reported ID to request cancellation. Cancellation is process-local and idempotent while the load is cancellable. A separate Agora process cannot cancel another process's worker, but an OS-backed compile lock prevents it from starting a second cold compiler for the same exact managed cache object.

Acquisition/materialization happens before a cold `active_loads` record exists, so its live visibility is the MCP progress stage rather than a durable job record. Agora deliberately does not introduce a background task queue for v1. If the MCP client does not request progress notifications, the same acquisition and compile guardrails still apply even though the progress UI is absent.

## Failure cleanup

After a failed, cancelled, or limited cold worker has died, Agora removes only incomplete `.cfm/<current-format-version>` derived output for that exact prepared cache object. It does not remove direct `.tf` source files or other `.cfm` format versions. A successful worker must leave the current-format `meta.json` completion marker before Agora invokes the normal in-process loader.

If the completion marker exists but the compiled cache is corrupt, the pinned Context-Fabric warm loader raises its own load error; Agora does not silently fall back to a main-process cold compile.

Acquisition timeout/cancellation stops the request-owned Git subprocess before the operation returns. Temporary snapshot-export trees are cleaned by the existing materialization `finally` path; published immutable snapshots are replaced atomically only after validation. A retry therefore reuses complete published state or starts materialization again rather than treating a partial temporary tree as a valid corpus.

## Persistent Git metadata repositories

Agora keeps partial/promisor Git repositories internally so it can resolve source revisions and lazily obtain metadata or blobs needed to create immutable source snapshots. These repositories are **not** the served corpus snapshots, and their non-checkout `git status` is not a corpus-integrity signal.

`corpus_cache_status` reports this repository storage separately from the logical snapshot/overlay cache. `repository_cache_bytes`, pack counts, Git-recognized garbage, per-repository inspection status, and `maintenance_needed` describe metadata-repository debt; they are not folded into `cache_bytes`, the snapshot soft limit, or snapshot/overlay LRU accounting. If the status budget expires or a repository cannot be inspected, the corresponding completeness fields remain false/null rather than reporting a misleading zero.

`maintenance_needed` is advisory and is derived from Git's own metadata: it becomes true when Git reports garbage or when pack fragmentation exceeds Agora's documented maintenance threshold. A busy repository may be reported as busy rather than blocking status indefinitely.

Persistent lazy `git show` operations participate in the same repository-use lock domain as source selection and maintenance. Readers use a shared lock; repository mutation and maintenance use an exclusive lock. This prevents explicit maintenance from racing a lazy promisor-object fetch while allowing independent safe readers to coexist.

Git maintenance is **not** run during server startup, describe, prepare, or load. In v1 it is attempted only as part of an explicit `prune_corpus_cache` operation, and only for repositories that currently need it. The maintenance phase has one global time budget plus a bounded per-repository `git gc --prune=now` timeout, so a collection of slow repositories cannot multiply an interactive timeout without bound.

Maintenance results are best-effort and reported separately from ordinary snapshot/overlay pruning. A Git maintenance failure or timeout does not cancel logical cache reclamation. Before/after byte, garbage, and pack deltas are reported only when the corresponding measurements actually completed; successful `git gc` followed by an incomplete measurement is not presented as a fabricated exact saving. Running prune again after debt has been cleared is expected to skip healthy repositories.

## Reclaiming cache space

Use `corpus_cache_status` to inspect cache usage, active leases, and persistent Git metadata debt. `prune_corpus_cache` reclaims unused managed cache objects while respecting active leases and the configured free-space guardrail; it also performs the bounded metadata-repository maintenance described above. `remove_cached_corpus` removes matching unused objects for a selected registered resource.

Agora's cache is deliberately managed independently from conventional user Text-Fabric data directories. Clearing Agora's cache therefore discards Agora-managed compiled artifacts; another Text-Fabric installation does not implicitly share them.
