# Design amendment: managed artifact use leases (#99 / #100)

## Status

This amendment is normative for #99 and overrides any wording in the initial #99 plan that could be read as making the artifact compile lock sufficient to protect a loaded artifact from explicit removal.

It was discovered while researching #100's Context-Fabric load lifecycle against the current `ContextFabricService` lease/unload semantics and #99's planned remove-by-artifact-ID API.

## Problem

#99 currently plans an artifact-ID compile lock and says explicit removal must refuse active/busy artifacts. That is insufficient to represent the important state **loaded but not compiling**.

A Context-Fabric load may keep using a managed artifact for minutes or days after cold compilation has finished. If #99 removal can acquire only a compile/mutation lock, it may delete the payload while `CorpusManager` still has the corpus loaded. Conversely, holding the exclusive compile lock for the whole loaded lifetime would unnecessarily serialize independent readers and make the lock mean two different things.

The same distinction already exists conceptually in Agora's canonical Context-Fabric cache: object lifetime/lease protection is separate from exact-object cold-compilation serialization. Managed artifacts need the same separation without widening canonical `GitStore` path authority.

## Required lock domains

#99 must provide two artifact-ID-derived, path-independent lock/lease roles:

1. **Artifact use lease**
   - shared for every active consumer/load;
   - held for the complete lifetime in which a consumer may dereference the payload;
   - exclusive for destructive removal/replacement of an already published artifact;
   - keyed only from a validated artifact ID, never from a caller-supplied filesystem path.

2. **Artifact compile lock**
   - exclusive for mutation of Context-Fabric-owned `.cfm/` state for one exact artifact;
   - keyed only from the same validated artifact ID;
   - independent of the use lease so multiple warm readers need not serialize on compilation state.

Publication locks/request-key locks remain separate. Publication finishes before an artifact can be leased or compiled.

## Lock ordering

The allowed consumer order is:

```text
validate artifact id / open immutable receipt metadata
    -> acquire shared artifact-use lease
    -> revalidate receipt + immutable payload while lease is held
    -> if cold: acquire artifact compile lock
    -> recheck warm marker
    -> compile / validate completion
    -> release compile lock
    -> load corpus while retaining shared use lease
    -> unload corpus
    -> release shared use lease
```

Destructive removal is:

```text
validate artifact id
    -> acquire exclusive artifact-use lock with bounded timeout
    -> revalidate target identity/containment
    -> remove
    -> release
```

Removal never waits for or acquires the compile lock while holding the exclusive use lock. A compiler necessarily already holds a shared use lease, so the exclusive removal acquisition cannot overlap compilation. This prevents a use-lock/compile-lock cycle.

Reusable publication/request-key locking must be released before #100 begins use/compile locking. No path may hold an installer runtime lock or publication lock across a potentially long Context-Fabric compile/load lifetime.

## Required RED additions to #99 Slice 3 / Slice 7

Before implementing the lifecycle seam, tests must require:

1. two processes can hold shared use leases for the same artifact concurrently;
2. exclusive remove waits/refuses while any shared use lease is live;
3. process death releases a use lease;
4. different artifact IDs do not block one another;
5. use-lock identity is invariant under cache-root relocation and cannot be chosen by path spelling;
6. invalid/traversal artifact IDs fail before lock-path access;
7. a compile lock may be acquired while the same process owns a shared use lease;
8. a second compile for the same artifact is excluded while warm readers remain allowed;
9. exclusive remove does not acquire/wait on the compile lock and therefore cannot deadlock with a compiler holding shared use;
10. publication/request-key locks are not held while acquiring a use or compile lock;
11. explicit remove reports in-use/busy truthfully rather than deleting or silently waiting without bound;
12. after the final use lease is released, explicit removal can proceed and no stale in-process lease record is required for correctness.

Use the existing cross-process OS-backed lock conventions. Windows/macOS/Linux semantics must be tested wherever the repository's lock dependency supports shared/exclusive operation; if a platform cannot provide the required shared mode, the plan must choose and test a conservative platform-specific fallback rather than silently weakening removal safety.

## Required #100 consumption contract

#100 must not construct these lock paths itself. It consumes #99's artifact-ID lease/compile-lock API or a format-compatible packaged seam exposed specifically for the Context-Fabric plugin.

The service lifecycle must:

- acquire a fresh shared use lease before trusting the payload path;
- revalidate immutable artifact receipt/payload under that lease;
- retain the lease after successful `CorpusManager.load`;
- replace/release a prior lease only after a replacement load succeeds, matching existing service semantics;
- release the newly acquired lease on every pre-load/compile/load failure;
- release the installed lease only after `CorpusManager.unload` succeeds or according to an explicitly tested failure policy;
- make repeated unload idempotent;
- never expose the internal artifact path as the public trust input.

## Adversarial review checklist

Final #99/#100 reviews must independently challenge:

- remove racing after validation but before lease acquisition;
- removal during cold compile;
- removal after compile but during warm load;
- failed replacement load leaking the new lease or releasing the old one early;
- process death leaving permanent false in-use state;
- shared-lock portability on Windows;
- a lock-order cycle among installer, publication, use and compile locks;
- arbitrary path values selecting a lock object;
- `.cfm` mutation accidentally being treated as immutable payload tampering while the scholarly/materializer payload remains protected.

Any blocker gets its own focused RED before correction.
