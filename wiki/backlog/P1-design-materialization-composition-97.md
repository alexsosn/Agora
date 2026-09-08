# Plan: approved local materialization → Context-Fabric composition (#97)

## Goal

Move from an explicitly approved/installed registered materializer to a provenance-bound reusable local Text-Fabric artifact and then into Context-Fabric/cfabric-mcp without manual managed-runtime or artifact filesystem wiring.

This plan is based on `P1-research-materialization-composition-97.md` and deliberately splits production work into independent implementation/review surfaces.

## Preconditions

- #94/#95 registered materializer-by-ID runner is merged and its runtime-lock/registry-binding guarantees are stable.
- No implementation slice may silently fetch/install/repair a third-party materializer.
- Burns source/derived data stay local-only; CI uses synthetic fixtures.

## Architectural decisions

1. **Do not mutate the canonical Context-Fabric catalog.** It models Git-backed marketplace resources and requires an upstream repository. Derived local artifacts are a separate resource class.
2. **No cfabric-mcp upstream change for v1.** `cfabric-mcp==0.1.7` already loads arbitrary local TF directories through `CorpusManager.load(path, name, features)`.
3. **Artifact identity is source + approved execution identity, not path + timestamp.** Reuse Agora's existing materializer/source/manifest hashes and installer `execution_identity_sha256`.
4. **Derived artifacts get a dedicated Agora cache/receipt namespace.** Do not place them inside Context-Fabric's Git source/materialized-object cache.
5. **Public loading uses an Agora artifact ID, never a caller-supplied arbitrary path.** The managed receipt is the trust boundary.
6. **Keep the existing explicit materializer runner and Git-backed Context-Fabric tools compatible.** Composition is additive.

## Slice A — deterministic managed artifact cache (#99)

### Research/plan handoff

Use the parent research document as the baseline; add ticket-local research only where implementation uncovers filesystem/platform-specific details.

### RED 1: identity contract

Tests-only commit must fail before production implementation and freeze:

- canonical artifact key inputs and schema version;
- same content/execution identity -> same key;
- source content/revision or execution identity change -> different key;
- timestamps/absolute cache root/source spelling do not affect key;
- options are canonicalized and included when present.

### GREEN 1

Implement a small pure identity/receipt module. No materializer execution yet.

### RED 2: validation/reuse

Freeze receipt/output-tree verification, required paths, symlink/path containment, local-only policy, and tamper/incomplete failure.

### GREEN 2

Implement read-only lookup/validation of completed managed artifacts.

### RED 3: transaction/concurrency

Freeze equivalent concurrent build behavior, failed build cleanup, private staging, one final publisher, loser validates/reuses winner, and no implicit fetch/install/repair calls.

### GREEN 3

Add per-artifact locking and transactional publication around the existing registered runner. Prefer extraction of the minimum stable programmatic host seam; do not rewrite the materializer sandbox.

### Review/test gate

Cross-platform filesystem unit tests where relevant + live synthetic registered-materializer smoke. Independent adversarial review focuses on TOCTOU, symlinks, lock lifetime, cache poisoning, identity omissions, and license/privacy leakage.

## Slice B — Context-Fabric managed-artifact load seam (#100)

Starts only after Slice A merges.

### RED 1: descriptor trust

Freeze `ManagedArtifact`/equivalent descriptor validation by artifact ID/receipt and prohibit arbitrary-path public input.

### GREEN 1

Add a small reader/resolver over the managed artifact cache. No materializer execution.

### RED 2: service lifecycle

Freeze local TF load through the existing `CorpusManager`, stable logical names, feature passthrough, repeat-load replacement semantics, unload idempotency, provenance projection, and no canonical catalog mutation.

### GREEN 2

Add a dedicated Context-Fabric service method (and internal lifecycle bookkeeping if needed) that loads a validated managed artifact path. Reuse the existing loader rather than constructing a fake `ResourceSpec`.

### RED 3: MCP surface

Freeze public tool inputs/outputs: artifact ID only, minimal provenance, no unnecessary absolute paths, existing `load_corpus` unchanged.

### GREEN 3

Register dedicated managed-artifact load/describe/unload tools only as needed. Do not overload canonical resource-id semantics if that makes trust ambiguous.

### Review/test gate

Run existing Git-backed Context-Fabric Foundation/cache lifecycle suites plus synthetic local TF load/query. Independent review focuses on arbitrary-path bypass, lifecycle leaks, name collisions, cold-compile assumptions, provenance/privacy and catalog isolation.

## Slice C — end-to-end composition (#101)

Starts only after A and B merge.

### RED 1: orchestration contract

Freeze composition requiring a current already-installed registered plugin/materializer and forbidding fetch/install/repair side effects.

### GREEN 1

Compose registered runner + managed artifact cache + managed-artifact loader through programmatic APIs.

### RED 2: user/MCP UX

Freeze response shape (`artifact_id`, load identity, bounded provenance), cache reuse signaling, and source/materializer error behavior without exposing internal runtime/artifact paths.

### GREEN 2

Expose a public composition operation/tool. Keep explicit materializer-runner and explicit managed-artifact loading available for inspectable two-step workflows.

### RED 3: live Burns acceptance

Synthetic Workbook CSV -> registered `ugarit-context-parsing` -> required real sandbox/network denial -> managed artifact -> Context-Fabric load -> representative query/feature check. No copyrighted Burns fixture or workflow artifact upload.

Also keep a generic/Pseudepigrapha path so orchestration does not hard-code Burns IDs or schema semantics.

### GREEN 3

Only integration/ergonomics adjustments necessary to satisfy the live contract.

### Review/test gate

Exact-head Foundation + materializer install/sandbox + Context-Fabric lifecycle + live synthetic composition. Independent review focuses on trust-boundary composition, implicit installation, cache key correctness, local-only data policy, error atomicity, and accidental corpus-specific coupling.

## Provenance contract direction

The managed artifact receipt should expose at least:

- artifact schema/key;
- source identity (`type`, content tree hash, immutable revision when available; local absolute path omitted from public projection);
- plugin registry id/version/immutable commit;
- installer execution identity;
- materializer id;
- execution manifest hash;
- canonical materializer options;
- output format + output tree hash;
- converter/Agora materialization provenance reference/digest;
- redistribution policy (`local-only` for Burns);
- creation metadata excluded from identity.

The public Context-Fabric response may expose a bounded subset plus artifact ID; detailed local receipt inspection can remain a separate local operation.

## Cache/lifecycle direction

- Default root under Agora data/cache home, not Context-Fabric GitStore directories.
- Key-addressed immutable artifact directories.
- Persistent advisory lock per key, using the same conservative migration/symlink philosophy as materializer/cache locks.
- Private sibling staging; validate before atomic rename.
- Recompute output tree hash on reuse before handing to consumers.
- Failed/tampered entries are never loaded.
- Initial retention may be explicit/manual rather than inventing an unreviewed automatic eviction policy; if meaningful eviction semantics are independent, file a follow-up ticket rather than blocking safe v1 composition.

## Dependency graph

```text
#95 registered run-by-ID
          |
          v
#99 managed artifact cache/receipt
          |
          v
#100 Context-Fabric managed-artifact load
          |
          v
#101 end-to-end composition + Burns acceptance
```

## Definition of done for #97

#97 can close once this research/design is reviewed/merged and the three implementation tickets are correctly scoped/dependency-linked. User-facing composition is complete only when #99, #100, and #101 all merge; do not describe #97's design merge alone as delivering the final feature.
