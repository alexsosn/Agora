# Plan: approved local materialization → Context-Fabric composition (#97)

## Goal

Move from an explicitly approved/installed registered materializer to a provenance-bound managed local Text-Fabric artifact and then into Context-Fabric/cfabric-mcp without manual managed-runtime or artifact filesystem wiring.

This plan is based on `P1-research-materialization-composition-97.md` and deliberately splits production work into independent implementation/review surfaces. The cacheability/privacy amendment in `P1-design-materialization-composition-97-determinism-amendment.md` and the Context-Fabric compile-state amendment in `P1-design-materialization-composition-97-cfm-amendment.md` are normative and are integrated below.

## Preconditions

- #94/#95 registered materializer-by-ID runner is merged and its runtime-lock/registry-binding guarantees are stable.
- #103 must define reviewed materializer cacheability semantics before #99 may implement request-identity reuse; unknown/legacy materializers remain executable but are not reusable.
- No implementation slice may silently fetch/install/repair a third-party materializer.
- Burns source/derived data stay local-only; CI uses synthetic fixtures.

## Architectural decisions

1. **Do not mutate the canonical Context-Fabric catalog.** It models Git-backed marketplace resources and requires an upstream repository. Derived local artifacts are a separate resource class.
2. **No cfabric-mcp upstream change for v1.** `cfabric-mcp==0.1.7` already loads arbitrary local TF directories through `CorpusManager.load(path, name, features)`.
3. **Artifact identity is source + approved execution identity, not path + timestamp.** Reuse Agora's existing materializer/source/manifest hashes and installer `execution_identity_sha256`. Request-identity reuse is allowed only for materializers whose reviewed #103 cacheability contract permits it, and that attestation/policy identity must participate in cache validity.
4. **Derived artifacts get a dedicated Agora cache/receipt namespace.** Do not place them inside Context-Fabric's Git source/materialized-object cache.
5. **Converter payload and Context-Fabric compile state have distinct ownership.** The materializer-owned payload is immutable and fully manifest/hash-bound at publication. Top-level `.cfm/` is reserved, rejected as materializer output, and may only appear later as Context-Fabric-owned disposable compile state without changing artifact/payload identity. No generic hidden-file exemption exists.
6. **Public loading uses an Agora artifact ID, never a caller-supplied arbitrary path.** The managed receipt is the trust boundary.
7. **Managed artifacts need artifact-ID–scoped compile locking.** Canonical `GitStore.compile_lock(path)` is intentionally limited to GitStore snapshots/overlays and must not be widened for external managed-artifact paths. The managed-artifact lock identity comes from validated `artifact_id`, never public path spelling.
8. **Keep the existing explicit materializer runner and Git-backed Context-Fabric tools compatible.** Composition is additive.
9. **Public provenance is privacy-bounded.** Local absolute source paths, local source basenames, and `.cfm` byte/path details are not exposed as materializer provenance by default.

## Slice A — managed artifact cache (#99)

Starts only after #103 merges.

### Research/plan handoff

Use the parent research plus both amendments as the baseline; add ticket-local research only where implementation uncovers filesystem/platform-specific details.

### RED 1: identity contract

Tests-only commit must fail before production implementation and freeze:

- canonical artifact key inputs and schema version;
- same content/execution identity/cacheability attestation -> same key for a reviewed reusable materializer;
- source content/revision, execution identity, or cacheability attestation change -> different key or invalid reuse;
- timestamps/absolute cache root/source spelling do not affect identity;
- options are canonicalized and included when present;
- unknown/legacy cacheability cannot produce a reusable request-identity hit.

### GREEN 1

Implement a small pure identity/receipt module that consumes #103 metadata. No materializer execution yet.

### RED 2: payload validation/reuse

Freeze:

- a deterministic converter-payload manifest binding every materializer-produced path by relative path, type and content hash (plus an optional aggregate digest over that manifest);
- required output paths as a subset of the manifested payload;
- symlink/path containment and tamper/incomplete failure;
- top-level `.cfm` rejected at publication as a reserved consumer namespace;
- post-publication `.cfm/<version>/...` tolerated only outside converter-payload integrity;
- modified/deleted manifested payload rejected even when `.cfm` exists;
- unrelated unmanifested files rejected rather than silently ignored;
- local-only policy and cacheability-attestation binding;
- exact stored-payload integrity distinguished from semantic rerun determinism.

### GREEN 2

Implement read-only lookup/validation of completed managed artifacts from the payload manifest, not an undifferentiated recursive directory hash. Only #103-approved reusable materializers may be returned as request-identity cache hits; non-cacheable/unknown artifacts may still be represented as one-shot managed outputs without memoized reuse.

### RED 3: transaction/concurrency/lock identity

Freeze equivalent concurrent build behavior for cacheable requests, failed build cleanup, private staging, one final publisher, loser validates/reuses winner when reuse is permitted, and no implicit fetch/install/repair calls. Explicitly non-cacheable materializers must not be collapsed into a request-identity cache hit.

Also freeze a stable managed-artifact lock namespace/helper keyed by canonical validated `artifact_id`, independent of cache-root or absolute path spelling, so #100 can use an artifact-scoped compile lock without widening `GitStore` path authority.

### GREEN 3

Add per-artifact publication locking and transactional publication around the existing registered runner. Prefer extraction of the minimum stable programmatic host seam; do not rewrite the materializer sandbox. Document lock ordering so payload validation/publication completes before potentially long Context-Fabric cold compilation and no cycle is introduced.

### Review/test gate

Cross-platform filesystem unit tests where relevant + live synthetic registered-materializer smoke. Independent adversarial review focuses on TOCTOU, symlinks, lock lifetime/order, reserved `.cfm` smuggling, payload-manifest completeness, cache poisoning, omitted identity inputs, cacheability-attestation drift, license/privacy leakage, and accidental reuse of unknown/non-cacheable materializers.

## Slice B — Context-Fabric managed-artifact load seam (#100)

Starts only after Slice A merges.

### RED 1: descriptor trust

Freeze `ManagedArtifact`/equivalent descriptor validation by artifact ID/receipt and prohibit arbitrary-path public input. Validation must establish payload integrity before entering a potentially long Context-Fabric compile lock.

### GREEN 1

Add a small reader/resolver over the managed artifact cache. No materializer execution.

### RED 2: service lifecycle and compile state

Freeze:

- local TF load through the existing `CorpusManager`;
- stable logical names and feature passthrough;
- repeat-load replacement semantics and unload idempotency;
- converter provenance projection and no canonical catalog mutation;
- cold loading may create `.cfm/<CFM_VERSION>/...` without changing artifact ID or payload identity;
- the same artifact validates after cold compile;
- deleting/rebuilding `.cfm` leaves payload identity unchanged;
- two processes cannot cold-compile the same artifact ID concurrently;
- different artifact IDs do not block one another;
- process death releases the artifact compile lock;
- canonical `GitStore.compile_lock` behavior remains unchanged;
- publication/validation/compile lock ordering is acyclic and a waiting compile does not hold a publication lock unnecessarily.

### GREEN 2

Add a dedicated Context-Fabric service method (and internal lifecycle bookkeeping if needed) that loads a validated managed artifact path. Reuse the existing loader rather than constructing a fake `ResourceSpec`. Use a dedicated cross-process compile lock keyed by validated `artifact_id`; do **not** pass the managed-artifact path to canonical `GitStore.compile_lock()` or widen `GitStore._managed_path()`.

### RED 3: MCP surface

Freeze public tool inputs/outputs: artifact ID only, minimal converter/artifact provenance, no absolute path, local source basename, or `.cfm` consumer-cache leakage, existing `load_corpus` unchanged.

### GREEN 3

Register dedicated managed-artifact load/describe/unload tools only as needed. Do not overload canonical resource-id semantics if that makes trust ambiguous.

### Review/test gate

Run existing Git-backed Context-Fabric Foundation/cache lifecycle suites plus synthetic local TF load/query. Independent review focuses on arbitrary-path bypass, lifecycle leaks, name collisions, compile-lock authority/order, CFM ownership, provenance/privacy and catalog isolation.

## Slice C — end-to-end composition (#101)

Starts only after A and B merge.

### RED 1: orchestration contract

Freeze composition requiring a current already-installed registered plugin/materializer and forbidding fetch/install/repair side effects.

### GREEN 1

Compose registered runner + managed artifact cache + managed-artifact loader through programmatic APIs.

### RED 2: user/MCP UX

Freeze response shape (`artifact_id`, load identity, bounded provenance), cache reuse signaling, and source/materializer error behavior without exposing internal runtime/artifact paths, local source basenames, or `.cfm` implementation details.

### GREEN 2

Expose a public composition operation/tool. Keep explicit materializer-runner and explicit managed-artifact loading available for inspectable two-step workflows.

### RED 3: live Burns acceptance

Synthetic Workbook CSV -> registered `ugarit-context-parsing` -> required real sandbox/network denial -> managed artifact -> Context-Fabric load -> representative query/feature check. No copyrighted Burns fixture or workflow artifact upload. Cache reuse may only be asserted if Burns has an explicit reviewed reusable disposition from #103.

Also keep a generic/Pseudepigrapha path so orchestration does not hard-code Burns IDs or schema semantics; its reuse assertions likewise follow #103 rather than inference.

### GREEN 3

Only integration/ergonomics adjustments necessary to satisfy the live contract.

### Review/test gate

Exact-head Foundation + materializer install/sandbox + Context-Fabric lifecycle + live synthetic composition. Independent review focuses on trust-boundary composition, implicit installation, cache key correctness, cacheability-policy drift, converter/CFM ownership, local-only data policy, error atomicity, and accidental corpus-specific coupling.

## Provenance contract direction

The managed artifact receipt should bind at least:

- artifact schema/key;
- deterministic converter-payload manifest and aggregate digest;
- source identity (`type`, content tree hash, immutable revision when available; local absolute path omitted from public projection);
- plugin registry id/version/immutable commit;
- installer execution identity;
- materializer id;
- execution manifest hash;
- canonical materializer options;
- reviewed cacheability policy/attestation identity where reuse is permitted;
- output format;
- converter/Agora materialization provenance reference/digest;
- redistribution policy (`local-only` for Burns);
- creation metadata excluded from request identity.

`.cfm/` is consumer-owned compile state and is not part of the converter payload manifest, artifact request identity, cacheability attestation, or public materializer provenance.

The public Context-Fabric response may expose a bounded subset plus artifact ID; it must omit local source paths/basenames and consumer-cache paths by default. Detailed local receipt inspection can remain a separate local operation.

## Cache/lifecycle direction

- Default root under Agora data/cache home, not Context-Fabric GitStore directories.
- Key-addressed immutable converter payload plus narrowly reserved Context-Fabric-owned `.cfm/` consumer state.
- Persistent advisory publication lock per artifact key, using the same conservative migration/symlink philosophy as materializer/cache locks.
- Dedicated finite-timeout cold-compile lock keyed by validated artifact ID; it does not reuse/widen canonical `GitStore.compile_lock(path)`.
- Private sibling staging; validate payload and reject preexisting top-level `.cfm` before atomic rename.
- Revalidate the recorded converter-payload manifest on reuse/load. Ignore only the explicitly reserved post-publication `.cfm/` namespace for payload integrity; reject unknown unmanifested additions.
- Failed/tampered entries are never loaded.
- Unknown/legacy/non-cacheable materializers are not served as request-identity cache hits; direct execution remains available.
- Payload validation/publication locks are released before long cold compilation; lock ordering must remain acyclic.
- Initial retention may be explicit/manual rather than inventing an unreviewed automatic eviction policy; if meaningful eviction semantics are independent, file a follow-up ticket rather than blocking safe v1 composition.

## Dependency graph

```text
#95 registered run-by-ID
          |
          v
#103 reviewed cacheability semantics
          |
          v
#99 managed artifact cache/receipt + artifact lock namespace
          |
          v
#100 Context-Fabric managed-artifact load + artifact-ID compile lock
          |
          v
#101 end-to-end composition + Burns acceptance
```

## Definition of done for #97

#97 can close once this research/design is reviewed/merged and #103/#99/#100/#101 are correctly scoped/dependency-linked. User-facing composition is complete only when the cacheability prerequisite and all three implementation slices merge; do not describe #97's design merge alone as delivering the final feature.
