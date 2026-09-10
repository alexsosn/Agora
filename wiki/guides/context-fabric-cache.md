# Context-Fabric cache and cold-load safety

Agora acquires registered Text-Fabric corpora lazily into its managed Context-Fabric cache. A first load can require Context-Fabric to compile `.tf` source files into its current `.cfm` format; later loads of a valid current-format cache use the normal warm upstream loader path.

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

## Defaults

The server-side defaults are:

- `AGORA_CORPUS_MIN_FREE_GB=6` — minimum host free-space reserve. Per-load options cannot disable it.
- `AGORA_CORPUS_COMPILE_MAX_MULTIPLIER=16` — default compiled-output budget multiplier applied to direct prepared `.tf` bytes.
- `AGORA_CORPUS_COMPILE_MIN_GB=0.25` — minimum default compiled-output budget.
- `AGORA_CORPUS_COMPILE_MAX_MINUTES=60` — default cold-worker wall-time limit.

The default compiled-output budget is `max(0.25 GiB, source_tf_bytes × 16)`. All configured multiplier/minimum/time values must be positive finite numbers. `AGORA_CORPUS_MIN_FREE_GB` follows the cache lifecycle configuration and may be set to zero only through explicit server configuration; a `load_corpus` call cannot reduce it.

## Per-load controls

`load_corpus` accepts two optional positive values for cold loads:

- `max_compile_gb` — override the observed compiled-output budget for this load.
- `max_compile_minutes` — override the cold-worker wall-time limit for this load.

Omitting these fields keeps the server defaults. Warm current-format loads do not pay the cold-worker/preflight path.

## Status and cancellation

`corpus_cache_status` includes `active_loads` for cold work owned by the current Agora server process. Active records include the load ID, resource/member/logical name, phase, elapsed time, source bytes, observed compiled bytes, compile budget, observed free bytes, configured reserve, and cancellation state.

Call `cancel_corpus_load(load_id)` with a reported ID to request cancellation. Cancellation is process-local and idempotent while the load is cancellable. A separate Agora process cannot cancel another process's worker, but an OS-backed compile lock prevents it from starting a second cold compiler for the same exact managed cache object.

If a client disconnects or times out, the worker does not become unbounded background work: server-side disk and time monitoring continues until the worker exits or is stopped.

## Failure cleanup

After a failed, cancelled, or limited cold worker has died, Agora removes only incomplete `.cfm/<current-format-version>` derived output for that exact prepared cache object. It does not remove direct `.tf` source files or other `.cfm` format versions. A successful worker must leave the current-format `meta.json` completion marker before Agora invokes the normal in-process loader.

If the completion marker exists but the compiled cache is corrupt, the pinned Context-Fabric warm loader raises its own load error; Agora does not silently fall back to a main-process cold compile.

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
