# Context-Fabric cache lifecycle

## Status

Normative architecture reference for issues #30/#10 and PR #31. It extends the revision-addressed source-snapshot contract in `ref-context-fabric-snapshot-cache.md`.

## Scope and ownership

Agora owns acquisition, local cache residency, provenance, load orchestration, and cache reclamation for registered Context-Fabric resources. This lifecycle layer must not change upstream Context-Fabric search/data semantics or mutate scholarly source data.

Cache eviction changes **local residency**, not source identity. A removed revision snapshot can be reconstructed from the same upstream revision using the #29 materialization contract.

## User requirements

1. A successfully loaded corpus remains usable until unload, replacement, or process exit, even when another Agora process sharing the cache is pruning.
2. Process death must release cache/repository ownership automatically; users must not repair stale lock sentinels manually.
3. Ordinary prepare/load calls must not perform unconditional full-cache pruning or turn housekeeping contention into unrelated load failures.
4. Status must make cache pressure understandable: object kind, bytes, recency, active use, configured soft target, free-space reserve, and current free space.
5. Prune/remove must never force-delete an active object. Partial reclamation is a normal, explicit result.
6. Module-enabled loads must participate in the same lifecycle without treating feature modules as corpora or requiring `otype.tf` in module snapshots.
7. Failure states must be finite and actionable: lock timeout, partial reclamation, target not met, and insufficient free space are distinguishable outcomes.

The executable acceptance criteria live in issue #30.

## Managed cache objects

The lifecycle layer recognizes three object classes:

### Corpus source snapshot

```text
snapshots/<resource>/<revision>/corpora/<relative-path>
```

A source/provenance object. Validity requires the corpus warp files expected by the #29 materializer.

### Feature-module source snapshot

```text
snapshots/<module-resource>/<revision>/feature-modules/<relative-path>
```

Also a source/provenance object, but its validity contract is different: it contains direct non-warp `.tf` feature files and must not contain parent warp files.

### Composed overlay

```text
overlays/<parent-resource>/<parent-revision>/<composition-digest>
```

An Agora-derived load artifact built from a parent snapshot plus selected feature-module snapshots. The digest includes the parent/module identities and ordering. It is not upstream provenance.

This explicit layout lets cache status and resource/revision removal work without guessing object semantics from the presence of `otype.tf`.

## Lock protocol

Agora uses `portalocker[win32]==4.3.0` for OS-backed advisory locks. On Windows, true shared locks require the `win32` extra/pywin32; this is therefore a runtime dependency rather than a development-only convenience.

Lock files are stable names and are intentionally not used as ownership sentinels. Ownership is the OS lock on the open file handle. Process death releases ownership automatically.

### Repository lock

```text
locks/repository-<cache-key>.lock
```

Held exclusively while cloning/fetching/updating one metadata repository. It replaces the crash-stale create/delete sentinel from #10.

### Cache-transition lock

```text
locks/cache-transition.lock
```

A short-lived reader/writer coordination point:

- prepare/materialize/module composition and final lease acquisition use it shared;
- prune/remove use it exclusive.

For `load_corpus`, Agora keeps this transition protected from the start of resolution/materialization through acquisition of the final cache-object lease. This closes both races that matter:

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

`prepare_corpus` materializes/cache-warms an object but does not hold a lifetime lease after the call returns. Its response therefore reports `cache_residency: evictable`.

`load_corpus` reports `cache_residency: leased`.

This distinction avoids hidden indefinitely-held leases while making the public behavior explicit.

## Recency and metadata

Source snapshot trees remain free of Agora metadata. Cache-management state lives outside them:

```text
access/<object-id>.stamp
object-meta/<object-id>.json
locks/cache-objects/<object-id>.lock
```

Access timestamps drive LRU ordering. Sidecar object metadata is advisory/rebuildable; physical cache discovery remains capable of finding existing objects after an upgrade or sidecar loss.

Persistent lock files are not deleted during eviction. Removing a lock pathname while another process still owns the old inode/handle can create split-brain locking if a replacement file is created at the same name.

## Pruning policy

`AGORA_CORPUS_CACHE_MAX_GB` is a soft logical cache target (default 3 GiB).

`AGORA_CORPUS_MIN_FREE_GB` is a materialization/free-space guardrail (default 6 GiB).

Prune walks managed objects in least-recently-used order and attempts deletion only after obtaining the global exclusive transition lock and each object's exclusive lock. Active objects are skipped.

The result reports:

- bytes before/after;
- removed entry/byte counts;
- active entries skipped;
- whether the requested target was actually met;
- whether the free-space guardrail is currently met.

A soft target is not a promise that every individual corpus fits beneath it. Hard-linked overlays also mean deleting one logical cache object does not necessarily free its full apparent byte count at the filesystem level. Free-space success is therefore checked from actual filesystem free space, not inferred from logical object sizes.

## Explicit removal

`remove_cached_corpus` accepts a registered resource and optional source revision/member selector.

For a parent corpus, resource/revision matching also includes its unused composed overlays because overlays are laid out under parent resource + parent revision. Active matches are skipped and reported.

For a feature-module resource, explicit removal targets that module's source snapshots. Existing parent overlays are independent derived objects and remain valid after source-module eviction.

## UX and failure semantics

- Lock acquisition uses finite timeouts; contention never means an unbounded hang.
- An active object's exclusive lock failure during prune/remove is a skip, not an exception and not forced deletion.
- Failure to acquire the global transition lock within the operation timeout is an explicit `TimeoutError`, indicating cache housekeeping is currently blocked by an active prepare/composition transition.
- Prune can succeed partially; callers must inspect `target_met`, `free_space_met`, and `skipped_in_use` rather than infer success from a non-error return.
- Ordinary prepare/load does not automatically run a full LRU sweep.

## Platform boundary

The protocol coordinates cooperating Agora processes that share the same filesystem cache. On POSIX systems these locks are advisory; unrelated processes that ignore the protocol can still mutate/delete files directly. This PR does not introduce a distributed lock service for independent machines/filesystems.

## Tests

The contract requires process-level tests for:

- live repository-lock contention;
- abrupt process death and lock recovery;
- active corpus-snapshot protection;
- active overlay protection;
- reclamation after lease release;
- transition protection during composition;
- module-aware cache discovery/pruning.

Service tests additionally cover failed-reload lease preservation, module/version logical names, idempotent unload, and cache-status/prune/remove result UX.
