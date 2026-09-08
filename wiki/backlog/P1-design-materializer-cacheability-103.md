# Plan: reviewed materializer cacheability semantics (#103)

## Goal

Add an Agora-owned, exact-commit **and exact-execution-environment** cache-reuse attestation so future managed artifact caching can memoize only materializers whose semantic determinism has been reviewed and evidenced for the environment actually executing them. Preserve direct execution for all existing materializers.

## Scope boundary

This ticket owns registry schema/validation, policy resolution, evidence metadata, tests and documentation. It does **not** implement artifact storage/reuse (#99), Context-Fabric loading (#100), or end-to-end composition (#101).

## Preconditions/evidence

- Parent research: `P1-research-materializer-cacheability-103.md`.
- #95 registered execution must remain compatible; cacheability is orthogonal to direct execution.
- Burns CSV cannot be marked reusable until repeated-run semantic determinism evidence exists for the exact plugin commit **and the exact managed execution identity Agora authorizes**.
- A plugin commit does not uniquely determine its installed environment: dependency ranges can resolve differently later or on another runtime/platform, and Agora intentionally records that distinction as `execution_identity_sha256`.

## RED 1 — registry compatibility and fail-closed semantics

Tests-only commit before production/schema change must freeze:

1. current registry without cacheability metadata remains schema-valid and directly executable;
2. absence resolves to effective `unknown` / reuse denied;
3. `non-reusable` resolves to reuse denied;
4. `reusable` requires immutable `reviewed_ref` plus at least one reviewed execution identity with non-empty structured evidence;
5. reviewed execution identities are full SHA-256 values and duplicate identities are rejected;
6. cacheability keys must refer to exact registered materializer IDs;
7. malformed mode/ref/environment/evidence/additional fields fail schema/semantic validation;
8. direct materializer install/run tests do not require cacheability metadata.

Expected RED: schema rejects the new metadata and no cacheability policy helper exists.

## GREEN 1 — optional registry schema + policy helper

Add the smallest optional schema, conceptually:

```yaml
cacheability:
  <materializer-id>:
    mode: reusable | non-reusable
    reviewed_ref: <40-hex plugin commit>        # required for reusable
    reviewed_environments:                      # required, non-empty for reusable
      - execution_identity_sha256: <64-hex>
        evidence:
          - type: managed-replay
            repository: owner/repo
            ref: <40-hex>
            target: <stable test/check target>
```

Implementation may use a semantically equivalent normalized shape if JSON Schema clarity requires it.

Add a pure read-only policy helper returning an explicit state, e.g. `unknown`, `non-reusable`, `reusable` plus the attestation identity. It receives the **already resolved current** `execution_identity_sha256`; it must not install, fetch or import a plugin itself.

Effective authorization is fail-closed:

- `reviewed_ref != plugin.ref` -> `unknown` / reuse denied;
- no current execution identity supplied -> `unknown` / reuse denied;
- current execution identity absent from `reviewed_environments` -> `unknown` / reuse denied;
- exact plugin ref + exact reviewed execution identity -> eligible for `reusable`.

Direct execution remains independent of this lookup.

No cache code yet.

## RED 2 — pin/environment drift, binding and attestation identity

Tests-only commit freezes:

- exact reviewed ref + exact reviewed execution identity -> reusable;
- plugin ref drift -> effective unknown without modifying direct execution;
- dependency/runtime drift that changes `execution_identity_sha256` -> effective unknown even when plugin ref is unchanged;
- two separately reviewed platform/runtime execution identities may each authorize reuse without authorizing a third identity;
- changing evidence/ref/mode/reviewed execution identities changes a deterministic attestation digest/identity;
- registry materializer-list drift cannot leave a cacheability entry authoritative for a removed ID;
- release candidate mutation of only plugin ref/version remains structurally valid but disables old reusable attestation;
- cacheability policy lookup is side-effect-free and performs no plugin fetch/install/import;
- a caller cannot substitute an execution identity that disagrees with the verified managed-installation receipt used for execution.

## GREEN 2

Add semantic cross-validation and deterministic attestation digest helper. Integrate only with registry validation/read APIs needed by #99 later. The helper consumes an execution identity already verified by the registered-runner/installer trust path; do not make cacheability a precondition for direct execution.

## Evidence contract

A reusable environment attestation is stronger than an upstream self-declaration. The evidence chain must identify the exact managed execution identity in which replay was observed.

For v1, evidence should be a deterministic managed replay/check that:

1. uses legally redistributable synthetic input;
2. installs/resolves the exact registered plugin ref and records the resulting `execution_identity_sha256`;
3. executes the same materializer twice in fresh output locations under that same managed environment;
4. reloads/normalizes the produced artifact at the semantic layer appropriate to the output format;
5. compares all scholarly/content node/edge/features and semantically meaningful report fields;
6. explicitly enumerates ignored volatile provenance fields such as Agora's run-specific `created_at`;
7. fails on output ordering, source traversal, generated-identifier or normalized-report drift;
8. records the exact plugin ref, execution identity and stable replay target/check in the evidence used by the registry attestation.

An upstream repeated-run test may be part of that evidence and may define the semantic comparison contract, but an upstream repository/ref/test target **alone** does not authorize reuse in an Agora-managed dependency/runtime closure that was never replayed.

Because `execution_identity_sha256` includes the resolved runtime/dependency tree and Python runtime identity, a dependency resolver or platform change fails closed until that new identity is replayed and separately reviewed.

## RED 3 — evidence-backed Burns disposition

After upstream Burns semantic determinism coverage exists and Agora has a managed replay for the exact environment being attested, commit tests first that require:

- Burns CSV has `reusable` attestation tied to the exact pinned commit, exact reviewed `execution_identity_sha256`, and replay evidence;
- Burns PDF remains absent/unknown or explicitly non-reusable until equivalent real synthetic-PDF evidence exists for a managed execution identity;
- Pseudepigrapha remains valid/executable with absent/unknown reuse unless independent managed replay evidence is added;
- CI/registry metadata contain no Burns-derived restricted fixture/artifact.

If the evidence is still blocked, finish #103 with no reusable Burns attestation and leave RED 3 for the dependent upstream/re-pin/replay subloop; do **not** fabricate evidence to unblock #99. In that case #99 can still implement one-shot managed artifacts but must not claim Burns cache hits.

## GREEN 3

Add only the evidence-backed registry disposition(s). If Burns upstream ref or its resolved execution identity changes, run the registered install/sandbox/replay gates for the new identity before any reusable attestation is accepted.

## Documentation

Update materializer registry docs to explain:

- cacheability is Agora-reviewed runtime policy, not an upstream self-trust claim;
- absent = direct execution allowed, reuse denied;
- non-reusable = execute every equivalent request;
- reusable = exact reviewed plugin commit **and exact reviewed managed execution identity** only;
- release pin drift or dependency/runtime drift disables reuse until re-review/replay;
- byte-level provenance differences may be ignored by semantic replay evidence, while the exact cached artifact tree is still hash-verified for integrity;
- a platform/runtime without a reviewed execution identity remains fully executable but non-memoized.

## Test gates

Before merge:

- Foundation full registry/unit suite;
- materializer install smoke unchanged/green;
- release-update regression suite proving ref/version updates remain valid and stale reuse fails closed;
- managed replay gate for every new reusable execution identity;
- any new Burns pin live sandbox smoke if applicable;
- exact-head logically independent adversarial review.

## Independent review focus

Review without relying on implementation notes:

- Does any path infer reusable from immutable code/network denial alone?
- Can stale `reviewed_ref` still authorize a hit?
- Can a new dependency/runtime closure reuse an attestation from an older `execution_identity_sha256`?
- Can a caller spoof an execution identity instead of consuming the verified installation receipt?
- Can cacheability metadata refer to/remove/reorder unregistered materializer IDs?
- Can release automation accidentally preserve effective reuse across a new commit?
- Does direct execution regress for legacy/unknown materializers?
- Is evidence exact-commit **and exact-environment** bound and reproducible?
- Does evidence confuse bit-identical provenance with semantic content determinism?
- Is any local source name/path incorporated into cacheability identity or public metadata?

Any blocker becomes a new RED regression before its fix.

## Definition of done

#103 is complete when Agora has a backward-compatible, fail-closed reviewed cacheability contract that #99 can consume without assuming converter determinism across either code or environment drift. Burns request-identity cache reuse is complete only when its semantic replay evidence and exact-pinned/exact-environment Agora attestation are both present.
