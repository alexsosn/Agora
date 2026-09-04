# Context-Fabric cache lifecycle

## Status

Normative architecture reference for issues #30/#10 and PR #31. It extends the revision-addressed source-snapshot contract in `ref-context-fabric-snapshot-cache.md`.

## Scope and ownership

Agora owns acquisition, local cache residency, provenance, load orchestration, and cache reclamation for registered Context-Fabric resources. This lifecycle layer must not change upstream Context-Fabric search/data semantics or mutate scholarly source data.

Cache eviction changes **local residency**, not source identity. A removed revision snapshot can be reconstructed from the same upstream revision using the #29 materialization contract.

## User requirements

1. A successfully loaded corpus remains usable until unload, replacement, or process exit, even when another Agora process sharing the cache is pruning.
2. Process death releases cache/repository ownership automatically; users must not repair stale lock sentinels manually.
3. Ordinary prepare/load calls do not perform unconditional full-cache pruning. Housekeeping may serialize only short cache-transition operations; recursive deletion I/O must not hold the global load-blocking transition lock.
4. Status makes cache pressure understandable: indexed managed bytes, unindexed cache bytes, object kind, recency, active use, configured soft target, free-space reserve, and current free space.
5. Prune/remove never force-delete an active object and never guess an independently evictable root from nested Text-Fabric files. Partial reclamation is a normal, explicit result.
6. Module-enabled loads participate in the same lifecycle without treating feature modules as corpora or requiring `otype.tf` in module snapshots.
7. Failure states are finite and actionable: live-object skips, transition contention, unindexed residency, target not met, and insufficient free space are distinguishable outcomes.

The executable acceptance criteria live in issue #30.

## Managed cache objects

The lifecycle layer recognizes three object classes.

### Corpus source snapshot

```text
snapshots/<resource>/<revision>/corpora/<relative-path>
```

A source/provenance object. Validity requires the corpus warp files expected by the #29 materializer.

### Feature-module source snapshot

```text
snapshots/<module-resource>/<revision>/feature-modules/<relative-path>
```

Also a source/provenance object, but with a different validity contract: it contains direct non-warp `.tf` feature files and must not contain parent warp files.

### Composed overlay

```text
overlays/<parent-resource>/<parent-revision>/<composition-digest>
```

An Agora-derived load artifact built from a parent snapshot plus selected feature-module snapshots. The digest includes the parent/module identities and ordering. It is not upstream provenance.

The layout identifies an object's **kind and semantic identity once its exact root is known**. It is not, by itself, enough to prove where an independently evictable object root begins inside an arbitrary pre-existing directory tree.

## Cache-object index and conservative migration

Eviction must know the exact root of an independently managed object. Agora records that root outside scholarly/source trees:

```text
object-meta/<object-id>.json
```

The sidecar stores the cache-relative path plus the identity derived from that exact path. `cache_entries()` accepts an object only when:

- the sidecar resolves to an existing managed path;
- the sidecar filename matches the deterministic object id for that path;
- the sidecar's kind/resource/revision/relative-path fields agree with the identity derived from the path;
- the object still passes the validity contract for its kind.

This index is intentionally authoritative for **evictability**. Agora does not recursively scan `snapshots/` or `overlays/` for `.tf` or `otype.tf` files and infer that each parent directory is a separate cache object. A nested source directory may legitimately contain Text-Fabric files, and guessing wrong would let pruning mutate an enclosing revision-addressed source snapshot in place.

Consequently, cache trees created before this index existed are handled conservatively:

- ambiguous/unindexed bytes remain resident;
- `corpus_cache_status()` includes them as `unindexed_cache_bytes` / `unindexed_cache_gb`;
- prune counts those bytes when deciding whether the logical cache is over target, but does not delete them by guesswork;
- a normal prepare/load/touch of an exact object root writes its deterministic sidecar and makes that root eligible for normal LRU management.

This is a safety-first migration policy. Temporary excess residency is preferable to destructive inference.

## Lock protocol

Agora uses `portalocker[win32]==4.3.0` for OS-backed advisory locks. On Windows, true shared locks require the `win32` extra/pywin32; this is therefore a runtime dependency rather than a development-only convenience.

Lock files are stable names and are intentionally not used as ownership sentinels. Ownership is the OS lock on the open file handle. Process death releases ownership automatically.

### Repository lock

```text
locks/repository-<cache-key>.lock
```

Held exclusively while cloning/fetching/updating one metadata repository. It replaces the crash-stale create/delete sentinel from #10.

Failed/timed-out acquisition releases the attempted lock handle before raising `TimeoutError`. The persistent lock pathname remains; deleting it during normal unlock would risk splitting the lock domain if another process still held the old inode/handle.

### Cache-transition lock

```text
locks/cache-transition.lock
```

A short-lived reader/writer coordination point:

- prepare/materialize/module composition and final lease acquisition use it shared;
- eviction uses it exclusive only long enough to prove an indexed object unused and atomically detach its served pathname.

For `load_corpus`, Agora keeps transition protection from the start of resolution/materialization through acquisition of the final cache-object lease. This closes both races that matter:

1. parent/module source snapshots cannot disappear while an overlay is being composed;
2. the final returned path cannot disappear between `prepare_with_modules()` returning and Context-Fabric obtaining lifetime protection.

The transition lock is released **before** the potentially expensive upstream Context-Fabric load. The object-specific lease then provides lifetime protection without globally blocking unrelated pruning.

### Cache-object lease

Each managed path maps to a deterministic persistent lock file under:

```text
locks/cache-objects/<sha256-of-cache-relative-path>.lock
```

A loaded corpus holds this lock shared for its lifetime. Eviction requires the same object lock exclusively.

The leased object is always the **final path passed to Context-Fabric**:

- plain load -> corpus snapshot;
- module-enabled load -> composed overlay.

Once an overlay has been completed and leased, its parent/module source snapshots can be evicted independently. The overlay uses hard links where possible and copies where necessary, so removing a source directory does not invalidate the completed overlay.

`CacheLease.release()` is idempotent, and the lease also performs best-effort finalizer cleanup so embeddings that drop a service without explicit unload do not accumulate file descriptors. Process/file-descriptor death remains the cross-process crash-safety guarantee.

## Eviction transaction

Recursive deletion of a multi-gigabyte corpus must not hold the global transition lock. For each indexed unused object, eviction therefore has two phases.

### Phase 1 — atomic detach

Under the exclusive cache-transition lock and the object's exclusive lock:

1. verify that the candidate is explicitly indexed;
2. re-check that the object still exists and is not leased;
3. create a unique `tmp/evict-*` quarantine directory;
4. atomically rename the managed object to `tmp/evict-*/data` on the same cache filesystem;
5. remove external access/object sidecars and empty managed parent directories;
6. release the object and transition locks.

After the rename the original served pathname is gone atomically. A subsequent prepare/load can immediately enter the transition lock and re-materialize the same source identity if needed.

### Phase 2 — recursive delete

Only after all cache-transition/object locks have been released does Agora measure and recursively delete the detached quarantine tree. Slow filesystem deletion therefore does not block normal prepare/load operations.

If a process dies after detaching but before deletion finishes, the detached tree is not a served cache object and cannot be loaded accidentally. Later `GitStore` instances best-effort remove `tmp/evict-*` directories older than a grace period, avoiding both permanent disk leakage and races with a live process that has only just detached an object.

## Load/reload transaction

`load_corpus` follows this order:

1. shared cache-transition lock;
2. prepare/materialize/compose;
3. acquire shared lease on the final load path;
4. release cache-transition lock;
5. call upstream `CorpusManager.load()`;
6. publish the new lease for the returned logical name;
7. only then release a previous lease for that same logical name.

This ordering deliberately does **not** unload the old corpus before trying the replacement. `cfabric-mcp==0.1.7` replaces its same-name registry entry only after a new load succeeds. If the replacement load fails, the previous upstream corpus and previous lease remain intact.

`unload_corpus(logical_name)` first asks upstream to unload and releases the lease only after that operation succeeds. Repeated unload is idempotent.

The logical name returned by `load_corpus` is the unload handle. Agora does not re-resolve a resource/version/module selection over the network just to identify an already loaded object.

## Prepare semantics

`prepare_corpus` materializes/cache-warms an object but does not hold a lifetime lease after the call returns. Its response reports `cache_residency: evictable` when the production cache store is present.

`load_corpus` reports `cache_residency: leased`.

This distinction avoids hidden indefinitely-held leases while making the public behavior explicit.

## Recency and external metadata

Source snapshot trees remain free of Agora metadata. Cache-management state lives outside them:

```text
access/<object-id>.stamp
object-meta/<object-id>.json
locks/cache-objects/<object-id>.lock
```

Access timestamps drive LRU ordering for indexed objects. Concurrent touches use unique temporary sidecar files followed by atomic replacement, so readers cannot collide on one shared `.tmp` pathname. Sidecar loss never alters source bytes; the exact object is re-indexed on a later normal access.

Persistent lock files are not deleted during eviction.

## Pruning policy

`AGORA_CORPUS_CACHE_MAX_GB` is a soft logical cache target (default 3 GiB).

`AGORA_CORPUS_MIN_FREE_GB` is a materialization/free-space guardrail (default 6 GiB).

Prune measures the whole `snapshots/ + overlays/` tree for its before/after logical cache size, but only indexed managed objects are eligible for LRU deletion. Indexed candidates are attempted in least-recently-used order. Each candidate is independently detached under the short exclusive transition/object-lock section described above; recursive deletion occurs after those locks are released. Active objects are skipped.

The result reports:

- `before_bytes` / `after_bytes` for the complete cache tree;
- removed entry/byte counts;
- `skipped_in_use`;
- `blocked_by_transition`;
- `unindexed_cache_bytes` remaining after the pass;
- `target_met`;
- `free_space_met` plus actual/current free bytes.

An indexed prune may therefore finish with `target_met: false` even when no indexed unused object remains, because unindexed bytes are deliberately retained. That is an explicit safe outcome, not silent success.

A soft target is not a promise that every individual corpus fits beneath it. Hard-linked overlays also mean deleting one logical cache object does not necessarily free its full apparent byte count at the filesystem level. Free-space success is checked from actual filesystem free space, not inferred from logical object sizes.

## Cache status UX

`corpus_cache_status()` reports both total and indexed residency:

- `cache_bytes` / `cache_gb` — complete `snapshots/ + overlays/` logical size;
- `indexed_cache_bytes` / `indexed_cache_gb` — sum of explicitly indexed managed objects;
- `unindexed_cache_bytes` / `unindexed_cache_gb` — conservative remainder;
- configured soft limit and minimum-free guardrail;
- actual free bytes/GiB;
- over-limit / below-free-space booleans;
- totals by managed object kind;
- per-object path, kind, resource, revision, size, recency, and `in_use` state.

The service augments this with `loaded_corpora`, mapping logical load handles to their leased paths.

## Explicit removal

`remove_cached_corpus` accepts a registered resource and optional source revision/member selector.

For a parent corpus, resource/revision matching also includes its **indexed** unused composed overlays because overlays are laid out under parent resource + parent revision. Active matches are skipped and reported.

For a feature-module resource, explicit removal targets that module's indexed source snapshots. Existing parent overlays are independent derived objects and remain valid after source-module eviction.

Removal is best-effort over the matching indexed set. The result distinguishes `skipped_in_use` from `blocked_by_transition`; `complete` is true only when neither condition prevented a matching object from being reclaimed.

Direct low-level removal of an unindexed path is rejected with an actionable error telling the caller to prepare/load it first so Agora records the exact root.

## UX and failure semantics

- Lock acquisition uses finite timeouts; contention never means an unbounded hang.
- An active object's exclusive lock failure during prune/remove is a skip, not an exception and not forced deletion.
- User-facing batch prune/remove returns transition contention as `blocked_by_transition` and can succeed partially instead of discarding already-completed reclamation behind a late timeout exception.
- Prune callers inspect `target_met`, `free_space_met`, `skipped_in_use`, `blocked_by_transition`, and `unindexed_cache_bytes` rather than infer success from a non-error return.
- Insufficient materialization space explicitly points callers to `corpus_cache_status` and `prune_corpus_cache`.
- Ordinary prepare/load does not automatically run a full LRU sweep.
- Ambiguous pre-index data is reported, not destroyed to satisfy a quota.

## Platform boundary

The protocol coordinates cooperating Agora processes that share the same filesystem cache. On POSIX systems these locks are advisory; unrelated processes that ignore the protocol can still mutate/delete files directly. This PR does not introduce a distributed lock service for independent machines/filesystems.

## Verification contract

Process-level regressions cover:

- live repository-lock contention;
- abrupt process death and lock recovery;
- active corpus-snapshot protection;
- active overlay protection;
- reclamation after lease release;
- transition protection during composition;
- recursive eviction I/O outside the global transition lock;
- conservative cache discovery for nested TF trees.

Service/MCP regressions cover failed-reload lease preservation, module/version logical names, idempotent unload, lifecycle tool registration, and cache-status/prune/remove result UX.

Verified PR #31 head `7eb5de82daf990d98fad3086e63844add8936a76` passed Foundation run #293 and Context-Fabric source-audit run #52 with no unresolved review threads.