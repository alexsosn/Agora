# Research: managed local materialization artifact cache (#99)

## Question

How should Agora turn the already-approved registered materializer runner into a private, tamper-evident managed artifact store without assuming converter determinism, leaking local source names, weakening installation/runtime trust, or confusing Context-Fabric's later `.cfm` compile state with converter output?

## Baseline inspected

Baseline: Agora `main@c875cc388984774ae015784f4fc49b6127c129b3` plus the merged #97 composition research/design and its cacheability/privacy and `.cfm` amendments.

#99 remains implementation-blocked on #103. This research intentionally does not assume the in-flight #103 branch is merged; implementation must consume the final reviewed #103 API/semantics rather than copying an intermediate helper.

Current materialization behavior:

- `scripts/agora_materialize_registered.py` resolves only a current registered, already-installed materializer and holds the installer runtime lock across final installation/binding verification and converter execution;
- it never fetches, installs, or repairs implicitly;
- `scripts/agora_materialize.py` validates input, runs the converter under the required OS sandbox, stages output privately next to the requested destination, validates required paths, writes `agora-materialization.json`, then publishes via same-filesystem `os.replace`;
- the staging root and publishable output child are private (`0700` on POSIX);
- user-local source provenance already has a content tree SHA-256 and may have a resolved Git commit, but it also contains the local basename, which is not suitable for public managed-artifact identity;
- current publication is caller-directory oriented. There is no Agora-owned artifact namespace, durable receipt, request-key lookup, or payload validation after publication.

## Constraints inherited from #97/#103

1. **Unknown is not deterministic.** An absent/unknown cacheability policy permits direct execution but can never produce a request-identity cache hit.
2. **`non-reusable` is terminal.** It may produce a managed one-shot artifact but equivalent requests must not be collapsed/reused.
3. **Reusable authority is exact.** A reusable hit requires the final #103 trusted authorization for the current registry ref and the exact integrity-verified managed execution identity. A caller-supplied digest is never authority.
4. **Policy identity is part of cache validity.** The #103 attestation digest must participate in a reusable request key/receipt so policy/evidence drift invalidates lookup.
5. **Converter payload and `.cfm` have different owners.** Materializer publication must reject top-level `.cfm`. Context-Fabric may create `.cfm/<version>/...` later without changing converter payload/artifact identity. No other hidden/unknown namespace receives an exemption.
6. **Managed artifacts are not canonical resources.** Do not mutate the Context-Fabric Git-backed catalog or widen `GitStore._managed_path()`.
7. **Public APIs use artifact IDs, not caller paths.** Absolute cache/source paths are internal details.
8. **All managed materialization artifacts are local-only in v1.** Do not infer redistribution permission from a license string. The host policy is conservatively `local-only`; no workflow/upload path may publish payload bytes.

## New finding: authorization/execution identity must be one consistency domain

A naïve #99 flow would:

1. call #103 to authorize reusable identity A;
2. compute a deterministic request key;
3. later call `materialize_registered()`.

Those calls acquire the installer runtime lock separately. An explicit repair/registry change could occur between them. The converter could then execute under identity B while #99 publishes under a key containing identity A.

Therefore a cache miss needs a minimum registered-runner programmatic seam that re-verifies the runtime **inside the execution lock** and checks that the actual execution identity and current cacheability attestation still equal the expected values used to derive the request key before converter execution/publish. A mismatch fails closed; do not silently publish under a different key.

This expected-value check is consistency, not authorization. Authorization itself still comes only from #103's verified installed-runtime path.

A cache hit likewise resolves current #103 authorization first. If the materializer is no longer installed/current/reviewed, request-key reuse is denied even if an old artifact remains loadable later by its explicit artifact ID.

## New finding: user-local source identity has its own TOCTOU window

The current host hashes a user-local source before execution and mounts it read-only inside the sandbox, but a non-cooperating host process can still mutate the underlying source tree while the converter reads it. A pre-run digest alone is therefore insufficient for durable cache identity.

For #99 managed builds:

- compute the canonical source identity before execution;
- run the converter with required sandbox only;
- recompute source identity after converter completion and before artifact publication;
- if any identity input changed (tree SHA-256 or resolved revision when semantically passed), discard staging and fail closed.

Tests should mutate a source file during a controlled synthetic converter run and require no final managed artifact.

Absolute source path and local basename are deliberately not identity inputs. They are not visible to the sandboxed converter (`/input` is stable) and must not leak into a public artifact descriptor. A detected `resolved_commit` **is** an identity input because manifests may use `{source_revision}` and therefore output may depend on it.

## Identity model: request key vs artifact instance ID

The old issue wording assumes one deterministic artifact key for every materializer. That is unsafe after #103.

Use two concepts:

### Reusable request key

Exists only when #103 returns `reuse_allowed: true`.

Canonical JSON (versioned and sorted) should bind at least:

- key schema/version;
- plugin ID, repository, immutable registry ref and registered version;
- materializer ID;
- exact verified `execution_identity_sha256`;
- exact #103 cacheability `attestation_sha256`;
- source type, source tree SHA-256, and resolved source commit when present;
- materializer manifest digest / selected materializer contract digest;
- output format;
- canonical options object (currently `{}` but reserved now);
- required sandbox policy;
- Agora managed-artifact host/key contract version.

SHA-256 of this canonical document is the reusable request key. Cache root, timestamps, absolute source/output paths and local basenames are excluded.

### Artifact instance ID

Every published managed artifact gets an opaque path-safe ID.

- for reusable builds, the deterministic request key may be embedded/used as the artifact ID because the per-key lock guarantees one published object;
- for unknown/non-reusable builds, generate a unique opaque ID and **never perform request-key lookup**. Identical one-shot executions must remain distinct even if their bytes happen to match.

Do not use output equality as evidence that an unknown/non-reusable converter became deterministic.

## Storage layout

Use a dedicated private namespace outside Context-Fabric Git snapshots/overlays, for example semantically:

```text
<Agora data>/materialized-artifacts/
  v1/
    objects/<artifact-id>/
      receipt.json
      payload/
        ... converter + Agora provenance output ...
    locks/publish/<request-key>.lock
    locks/compile/<artifact-id>.lock
    tmp/...
```

Exact names may follow repository conventions, but invariants are:

- object directory is the unit atomically published;
- receipt is outside `payload/`, so later Context-Fabric `.cfm` writes cannot overwrite it;
- staging is on the same filesystem as `objects/`;
- POSIX object/staging directories are private (`0700`) and receipts are private (`0600`);
- no symlink is accepted for store root, object, receipt, payload or manifested descendants;
- artifact ID and lock names are validated opaque IDs, never caller-supplied paths.

## Payload manifest and `.cfm`

A whole-directory hash cannot remain the integrity primitive because Context-Fabric deliberately mutates `.cfm` after publication.

At publication:

1. require top-level `.cfm` to be absent; a converter attempting to produce it fails;
2. scan **every** path under payload (converter output plus Agora-owned `agora-materialization.json`);
3. reject symlinks/path escapes;
4. record a canonical payload manifest with every relative path, kind (`file`/`dir`) and SHA-256 for files;
5. record an aggregate SHA-256 over that canonical manifest;
6. revalidate declared required output paths.

On later validation:

- every manifested path must still exist with the same kind/hash;
- required output paths must still satisfy the materializer contract recorded in the receipt;
- unknown extra paths are invalid **except** descendants of the one reserved top-level `.cfm/` namespace;
- `.cfm` itself/descendants must still be nonsymlink-contained consumer state;
- missing/changed converter or Agora provenance payload fails closed even when `.cfm` exists;
- deleting/rebuilding `.cfm` does not change payload digest, artifact ID or reusable request key.

Manifesting directories as well as files prevents an attacker from adding otherwise-empty unknown directory structure and getting it silently ignored.

## Receipt trust boundary

Receipt schema v1 should be immutable after publication and bind:

- artifact ID and whether it was `reusable` or `one-shot` at creation;
- reusable request key when applicable, otherwise null/absent;
- plugin registration coordinates;
- materializer ID and selected manifest/contract digest;
- verified execution identity actually used for the build;
- #103 mode/attestation digest actually used (or explicit unknown/non-reusable disposition);
- privacy-bounded source identity (type/tree digest/resolved commit only; no basename/absolute path);
- output format and required paths;
- payload manifest + aggregate digest;
- sandbox policy/backend observation;
- host artifact/key schema versions;
- fixed host redistribution policy `local-only`;
- creation/observation timestamps only as non-identity metadata.

The existing `agora-materialization.json` remains payload provenance. The durable managed receipt is a separate host/cache trust object and should not be synthesized from path names.

## Reusable lookup algorithm

For a user request:

1. validate source and derive pre-run source identity;
2. resolve #103 current installed cacheability authorization;
3. if reusable, derive request key and acquire its cross-process publish lock;
4. after lock acquisition, recompute current authorization/source identity because both may have changed while waiting;
5. if key/attestation no longer matches, release/fail/restart from a fresh request decision rather than using the stale key;
6. if final object exists, validate receipt + complete payload manifest + required paths and return it;
7. if object exists but is invalid/tampered, fail closed; do not silently delete/repair it;
8. if absent, execute via the registered-runner consistency seam requiring the expected execution identity/attestation;
9. recompute source identity after execution;
10. build receipt/payload manifest in private staging;
11. atomically publish one object under the lock.

Equivalent losers wait on the same request-key lock, then validate/reuse the winner rather than executing again.

For unknown/non-reusable policy:

- skip deterministic request-key lookup/collapse entirely;
- allocate a unique instance ID;
- execute normally through the current registered runner (no cacheability prerequisite);
- perform the same source-stability, payload-manifest, receipt, staging and atomic-publication checks;
- return the one-shot managed artifact ID.

## Locks and #100 handoff

#99 must establish a stable artifact-ID lock helper/namespace suitable for #100's later Context-Fabric cold compile. It must be:

- cross-process and OS-backed/crash-safe;
- keyed by validated artifact ID, not filesystem path;
- independent across different artifacts;
- finite-timeout;
- separate from long publication work unless an explicit ordering proves otherwise.

Required lock order:

1. installer/runtime verification/execution lock is held only where the registered runner already needs it;
2. reusable publish lock may surround cache check/build orchestration, but code must avoid acquiring locks in the opposite order elsewhere;
3. publication/receipt validation completes before #100 later enters the managed-artifact compile lock;
4. waiting compile must never retain a publication lock.

The final plan/tests must make the order explicit and prove no cycle.

## Failure and cleanup semantics

- converter failure, source drift, output validation failure, manifest failure or receipt construction failure leaves no final object;
- publish is one same-filesystem atomic rename of a completed object directory;
- a process crash may leave private `tmp/` staging but never a valid final object;
- cleanup of abandoned staging is explicit/bounded housekeeping, not a constructor/startup recursive sweep;
- a pre-existing invalid final object is reported as tampered/incomplete and requires explicit removal/maintenance rather than implicit replacement.

## Retention boundary

Automatic cross-cache LRU is not required to prove #99's trust contract and should not be entangled with Context-Fabric snapshot/overlay quota semantics. #99 should provide enough store primitives for later lifecycle integration:

- enumerate/describe validated artifact metadata without exposing local paths;
- validate by artifact ID;
- explicit remove by artifact ID under an artifact mutation lock;
- size/created/last-access observations may be sidecar metadata but are never artifact identity.

If automatic artifact LRU is desired, file/implement it as a separately reviewed cache-lifecycle slice rather than silently counting these bytes inside existing Context-Fabric `cache_bytes`.

## Tests that research adds beyond the old issue text

The implementation plan must include RED contracts for:

- unknown and `non-reusable` never producing a request-identity hit;
- cacheability attestation drift invalidating reuse;
- authorization/execution identity race failing closed;
- source mutation during execution failing before publication;
- reserved materializer-produced `.cfm` rejection;
- post-publication `.cfm` creation/deletion tolerance with unchanged payload identity;
- unknown unmanifested non-`.cfm` additions rejected;
- directory + file manifest completeness;
- stable artifact-ID compile-lock identity independent of path spelling;
- tampered existing object not being silently repaired;
- no absolute source path/basename in public descriptor/receipt identity fields;
- no implicit fetch/install/repair;
- one-shot artifacts remaining distinct for identical unknown/non-reusable requests;
- reusable concurrent losers validating winner instead of executing;
- private modes and symlink/path-escape failures on POSIX plus portable behavior elsewhere.

## Conclusion

#99 should not be implemented as a generic deterministic output cache. It is a private managed-artifact store with two modes: evidence-authorized request reuse and fail-closed one-shot publication. The core trust objects are the final #103 authorization, a stable source identity checked before/after execution, an atomic object receipt, and an explicit payload manifest that excludes only Context-Fabric's later `.cfm` consumer namespace. This preserves direct materialization for unreviewed converters while giving #100 a path-safe artifact ID and lock namespace without weakening canonical Context-Fabric resource semantics.