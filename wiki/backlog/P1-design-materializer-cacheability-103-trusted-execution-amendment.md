# Design amendment: bind cacheability to a verified installed runtime (#103)

## Review finding

Independent adversarial review found a second trust-boundary ambiguity after the exact-environment amendment.

The current plan says the cacheability policy helper receives an already resolved `execution_identity_sha256`, while RED 2 also requires that a caller cannot substitute an execution identity that disagrees with the verified managed-installation receipt used for execution. A bare digest parameter cannot establish both properties by itself: any caller that can choose the string could present the digest of a reviewed environment even when the installed/runtime bytes about to execute are different.

Current Agora already has the correct authority boundary in the registered materializer runner: it resolves the registered installation, acquires the per-runtime lock, verifies the managed environment/receipt against current registry and runtime state, verifies registry↔manifest/materializer binding, and only then executes the converter. Cacheability authorization must consume that verified state rather than creating a parallel caller-trust path.

This amendment is normative and supersedes any wording in the parent plan that could be read as allowing an untrusted caller-supplied execution digest to authorize reuse.

## Required API boundary

Implementation may retain a pure internal comparison function of the conceptual form:

```text
compare_cacheability(plugin_metadata, materializer_id, verified_execution_identity)
```

for deterministic policy logic and unit testing. That primitive is **not** an authorization boundary.

The reusable-authorization API consumed by #99 must instead obtain the execution identity from one of these equivalent trusted shapes:

1. a typed/structured verified installed-runtime descriptor produced by Agora only after the existing installation integrity checks succeed under the runtime lock; or
2. an internal call made inside the registered-runner/installer locked verification path, where the installation receipt and runtime bytes have just been revalidated and the digest is read from that verified receipt.

The descriptor/authorization result must bind at least:

- registered plugin id and current immutable `plugin.ref`;
- selected materializer id and current registry binding;
- managed installation path/runtime identity;
- verified installation `execution_identity_sha256`;
- cacheability mode/effective disposition;
- deterministic cacheability-attestation identity when reusable.

It must not fetch, install, repair, or import third-party code as a side effect. A missing or invalid installation yields no reusable authorization; direct execution retains its existing explicit-install behavior.

## Lock/race requirement

The identity used for a cacheability decision must describe the same managed runtime whose integrity/binding was checked for the operation. A repair or registry-target change must not be able to replace the runtime between verification and the authorization decision.

For the existing registered-runner path, perform verification and cacheability resolution while holding the same per-runtime lock already used from final integrity verification through converter execution. If #99 later evaluates reuse without executing the converter, it must obtain an equivalent read-only verified-runtime snapshot under that lock; it must not trust a stale receipt copied earlier by the caller.

## RED additions before implementation

Add tests before production changes that prove:

- supplying the digest of a reviewed environment while the actual managed installation/receipt verifies to a different digest cannot authorize reuse;
- a tampered/stale installation receipt cannot be used to manufacture a reusable authorization;
- cacheability resolution for the registered path reads the identity from the integrity-verified managed installation, not a CLI/API string;
- registry pin/materializer binding changes while waiting for the runtime lock fail closed exactly as registered execution already does;
- an installation/runtime replacement cannot race between integrity verification and cacheability authorization;
- policy lookup remains read-only: no fetch, install, repair, packaging execution, or implicit import occurs;
- the lower-level pure comparison helper, if exposed at all, is named/documented as non-authoritative and is not the API #99 uses to decide whether to return a cache hit.

## GREEN implication

#103 should expose a small verified-runtime/cacheability resolver that composes with the existing registered-runner lock/integrity machinery rather than duplicating environment validation. The deterministic attestation digest still binds the reviewed commit, reviewed execution identity, materializer and evidence; this amendment changes **where the current execution identity comes from**, not the exact-environment evidence model.

## Review focus

Final review must attempt to authorize reuse by:

- passing a reviewed digest for a different installed environment;
- editing only the installation receipt;
- changing the registry pin/materializer set while a caller waits for the runtime lock;
- replacing the managed environment between verification and decision;
- calling the cacheability API before installation exists.

Every path must fail closed to no reusable cache hit, while ordinary explicit direct execution remains backward-compatible.
