# Plan: reviewed materializer cacheability semantics (#103)

## Goal

Add an Agora-owned, exact-commit cache-reuse attestation so future managed artifact caching can memoize only materializers whose semantic determinism has been reviewed and evidenced. Preserve direct execution for all existing materializers.

## Scope boundary

This ticket owns registry schema/validation, policy resolution, evidence metadata, tests and documentation. It does **not** implement artifact storage/reuse (#99), Context-Fabric loading (#100), or end-to-end composition (#101).

## Preconditions/evidence

- Parent research: `P1-research-materializer-cacheability-103.md`.
- #95 registered execution must remain compatible; cacheability is orthogonal to direct execution.
- Burns CSV cannot be marked reusable until a new upstream repeated-run semantic determinism test exists on the exact commit Agora reviews.

## RED 1 — registry compatibility and fail-closed semantics

Tests-only commit before production/schema change must freeze:

1. current registry without cacheability metadata remains schema-valid and directly executable;
2. absence resolves to effective `unknown` / reuse denied;
3. `non-reusable` resolves to reuse denied;
4. `reusable` requires immutable `reviewed_ref` + non-empty structured evidence;
5. cacheability keys must refer to exact registered materializer IDs;
6. malformed mode/ref/evidence/additional fields fail schema/semantic validation;
7. direct materializer install/run tests do not require cacheability metadata.

Expected RED: schema rejects the new metadata and no cacheability policy helper exists.

## GREEN 1 — optional registry schema + policy helper

Add the smallest optional schema, conceptually:

```yaml
cacheability:
  <materializer-id>:
    mode: reusable | non-reusable
    reviewed_ref: <40-hex>        # required for reusable
    evidence:                     # required for reusable
      - type: upstream-test
        repository: owner/repo
        ref: <40-hex>
        target: <stable test target>
```

Implementation may use a semantically equivalent normalized shape if JSON Schema clarity requires it.

Add a pure read-only policy helper returning an explicit state, e.g. `unknown`, `non-reusable`, `reusable` plus the attestation identity. The helper must treat `mode: reusable` with `reviewed_ref != plugin.ref` as **effective unknown/reuse denied**, not as a registry-schema error.

No cache code yet.

## RED 2 — pin drift / binding / attestation identity

Tests-only commit freezes:

- exact reviewed ref -> reusable;
- plugin ref drift -> effective unknown without modifying direct execution;
- changing evidence/ref/mode changes a deterministic attestation digest/identity;
- registry materializer-list drift cannot leave a cacheability entry authoritative for a removed ID;
- release candidate mutation of only plugin ref/version remains structurally valid but disables old reusable attestation;
- cacheability policy lookup is side-effect-free and performs no plugin fetch/install/import.

## GREEN 2

Add semantic cross-validation and deterministic attestation digest helper. Integrate only with registry validation/read APIs needed by #99 later. Do not call it from direct materializer execution as an execution precondition.

## RED 3 — evidence-backed Burns disposition

After upstream Burns semantic determinism evidence lands and Agora is repinned to that reviewed commit, commit tests first that require:

- Burns CSV has `reusable` attestation tied to the exact pinned commit and the exact upstream repeated-run test target;
- Burns PDF remains absent/unknown or explicitly non-reusable until equivalent real synthetic-PDF evidence exists;
- Pseudepigrapha remains valid/executable with absent/unknown reuse unless independent evidence is added;
- CI/registry metadata contain no Burns-derived fixture/artifact.

If the upstream Burns evidence is still blocked, finish #103 with no reusable Burns attestation and leave RED 3 for the dependent upstream/re-pin subloop; do **not** fabricate evidence to unblock #99. In that case #99 can still implement one-shot managed artifacts but must not claim Burns cache hits.

## GREEN 3

Add only the evidence-backed registry disposition(s). If Burns upstream ref changes, run the existing registered install/sandbox smoke at the new immutable pin before any reusable attestation is accepted.

## Documentation

Update materializer registry docs to explain:

- cacheability is Agora-reviewed runtime policy, not an upstream self-trust claim;
- absent = direct execution allowed, reuse denied;
- non-reusable = execute every equivalent request;
- reusable = exact reviewed commit only;
- release pin drift disables reuse until re-review;
- byte-level provenance differences may be ignored by upstream semantic evidence, while the exact cached artifact tree is still hash-verified for integrity.

## Test gates

Before merge:

- Foundation full registry/unit suite;
- materializer install smoke unchanged/green;
- release-update regression suite proving ref/version updates remain valid;
- any new Burns pin live sandbox smoke if applicable;
- exact-head logically independent adversarial review.

## Independent review focus

Review without relying on implementation notes:

- Does any path infer reusable from immutable code/network denial alone?
- Can stale `reviewed_ref` still authorize a hit?
- Can cacheability metadata refer to/remove/reorder unregistered materializer IDs?
- Can release automation accidentally preserve effective reuse across a new commit?
- Does direct execution regress for legacy/unknown materializers?
- Is evidence exact-commit bound and reproducible?
- Does evidence confuse bit-identical provenance with semantic content determinism?
- Is any local source name/path incorporated into cacheability identity or public metadata?

Any blocker becomes a new RED regression before its fix.

## Definition of done

#103 is complete when Agora has a backward-compatible, fail-closed reviewed cacheability contract that #99 can consume without assuming converter determinism. Burns request-identity cache reuse is complete only when its upstream semantic evidence and exact-pinned Agora attestation are both present.
