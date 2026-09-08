# Research: reviewed materializer cacheability semantics (#103)

## Question

How can Agora safely reuse managed materialization artifacts without silently assuming that every third-party converter is deterministic for a given source and runtime?

## Baseline inspected

- Agora `main` at the start of this research: `94bcddb45c9e1e7a1bcb766ce82a820f8be4209c`.
- `registry/schema/materializer-plugin.schema.json` v1 declares acquisition, input, execution and output, but no determinism/cacheability field.
- `registry/materializers.yaml` binds approved plugin/source/materializer identities and already represents Agora-owned review/trust metadata.
- The installer records a complete `execution_identity_sha256` over immutable plugin source + managed dependency/runtime tree + Python runtime identity.
- The materialization host runs with a filtered environment and `network: deny`, records source content identity, manifest/code identity and output provenance, but it cannot prevent converter code from consulting time/randomness/local process state.
- Burns converter pinned by Agora: `alexsosn/ugarit-context-parsing@e1218b88d9d849c58ee25541339f32b0d8f5a7d3`.
- Pseudepigrapha reference converter remains a compatibility target but does not need to be declared reusable for the first Burns cache slice.

## Core finding: immutable code is not equivalent to deterministic output

An immutable plugin commit plus an immutable installed dependency tree proves *what code was run*. It does not prove that two runs with identical source bytes produce the same scholarly/content result.

A converter can legally use:

- current time;
- randomness;
- process-local state;
- host-specific nondeterminism not captured by the declared contract;
- an undeclared local data source;
- input ordering from a nondeterministic filesystem traversal.

`network: deny` removes one important external-state channel but does not establish determinism.

Therefore an artifact cache keyed only by source + execution identity changes semantics for an unreviewed nondeterministic materializer: a second request would return the first output instead of executing again.

## Authority decision: cache reuse is an Agora registry attestation

The authoritative cacheability decision should live in Agora's reviewed `registry/materializers.yaml`, not solely in the upstream `agora.materializer.json`.

Reasons:

1. Cache reuse is an Agora runtime behavior, not required for standalone converter execution.
2. A third-party self-assertion must not automatically authorize Agora to memoize results.
3. Existing immutable upstream manifests must remain directly executable without schema churn.
4. Agora already owns immutable pin review, installation trust, verification status and source/data licensing metadata.
5. Release pin changes can conservatively disable an old attestation until the new converter revision is reviewed.

An upstream determinism declaration may be useful future evidence, but it should be evidence, not the sole authorization.

## Recommended registry shape

Add an optional per-materializer mapping on a registered plugin. Exact schema naming may be adjusted during implementation, but the semantic shape should be equivalent to:

```yaml
cacheability:
  burns-workbooks-csv-text-fabric:
    mode: reusable
    reviewed_ref: <40-hex plugin commit>
    reviewed_environments:
      - execution_identity_sha256: <64-hex>
        evidence:
          - type: managed-replay
            repository: alexsosn/Agora
            ref: <40-hex commit>
            target: <stable replay/check target>
  burns-workbooks-pdf-text-fabric:
    mode: non-reusable
```

Semantics:

- **absent**: `unknown`; direct execution allowed, request-identity reuse forbidden.
- **mode: non-reusable**: direct execution allowed; managed one-shot artifacts may be retained/loaded, but a later equivalent request must execute again rather than return a request-identity cache hit.
- **mode: reusable**: request-identity reuse allowed only when `reviewed_ref == plugin.ref` **and** the current verified `execution_identity_sha256` is one of the separately reviewed environments with valid replay evidence.

The cacheability entry keys must be a subset of the plugin's exact registered `materializers` list. Unknown keys fail registry validation.

## Pin drift and release updates

A reusable attestation is valid only for the exact reviewed plugin commit and reviewed execution environment.

Do **not** make a new plugin release fail registry validation merely because its `reviewed_ref` is older. Agora's release-discovery workflow currently patches only `ref` and `version`; preserving that property is useful.

Instead:

- registry schema validates `reviewed_ref` as immutable 40-hex;
- runtime/cache policy treats `mode: reusable` as effectively `unknown` unless `reviewed_ref == current plugin.ref`;
- a release update therefore disables cache hits automatically until a human-reviewed cacheability update lands;
- the cache key/receipt records the cacheability attestation identity so old reusable entries cannot be mistaken for newly approved ones.

This is fail-closed without coupling automated release discovery to cache review.

## What “reusable” means

The useful contract is **semantic/content determinism under the declared identity boundary**, not necessarily byte-for-byte whole-directory determinism.

Agora itself writes `agora-materialization.json` with `created_at`, and converters may include non-semantic creation metadata. Two correct reruns can therefore differ in provenance bytes while representing the same corpus graph/content.

A `reusable` attestation means:

> For the exact reviewed plugin commit and exact reviewed managed execution identity, identical canonical source identity + materializer ID + declared execution arguments/options produce the same scholarly/content artifact, modulo explicitly identified non-semantic provenance fields.

The stored artifact receipt still hashes the exact published output tree for tamper detection. That exact tree hash is integrity evidence for the chosen cached artifact; it is not itself proof of rerun determinism.

## Identity boundary required by reusable mode

At minimum cache reuse must bind:

- canonical source content tree hash;
- immutable source revision when it is semantically passed/used or when the acquisition contract requires it;
- registered plugin id + exact immutable plugin commit;
- installer `execution_identity_sha256` (plugin source + dependency/runtime tree + Python runtime identity);
- materializer id;
- execution manifest hash;
- all explicit materializer options/arguments when options exist;
- cache/composition schema version;
- cacheability attestation identity/version.

Machine-local cache paths, output paths and timestamps must not affect request identity.

## Evidence standard

A reusable attestation requires reproducible semantic replay tied to both the exact reviewed commit and the exact managed execution identity.

The replay should:

1. construct/use a synthetic legally redistributable input;
2. execute the same materializer twice in fresh output locations under the same managed dependency/runtime identity;
3. record the exact `execution_identity_sha256` from the verified managed installation;
4. reload/normalize the produced artifact at the semantic layer appropriate to the output format;
5. compare all scholarly/content node/edge/features and converter report fields that are semantically meaningful;
6. explicitly enumerate ignored volatile provenance fields, if any;
7. fail if output ordering, source traversal, generated identifiers or normalized reports drift.

An upstream repeated-run test can define/provide semantic comparison evidence, but a repository/ref/test target alone is insufficient authorization for an Agora environment that was never replayed. A code inspection alone is also insufficient.

## Adversarial review amendment: plugin-ref stability does not imply environment stability

Independent review of the first design found that exact plugin-ref binding still left one unsafe reuse path.

Agora's installer resolves third-party dependency ranges and records the resulting environment separately. At the inspected Burns commit, `pyproject.toml` contains ranges including `text-fabric>=13.1,<14` and `pdfplumber>=0.11`; therefore the same immutable Burns commit can legitimately acquire a different dependency closure later or on another platform. Agora detects such change through `execution_identity_sha256`.

Merely including that execution identity in a future artifact cache key would prevent artifacts from different environments colliding, but it would not prove that the converter is deterministic in the *new* environment. A commit-only `reusable` attestation would still authorize memoization among requests inside an environment whose dependency behavior was never tested.

Therefore effective reuse must require both:

1. current plugin ref equals the reviewed plugin ref; and
2. current verified managed-installation `execution_identity_sha256` is explicitly present in the reviewed environment set backed by replay evidence.

If the dependency resolver, Python runtime, ABI/platform, or installed dependency tree changes enough to alter that identity, reuse fails closed to `unknown`; direct execution remains available. Each additional environment can be reviewed independently rather than assuming cross-platform/cross-dependency determinism.

The cacheability helper must consume the verified execution identity from the existing installer/registered-runner trust path. It must not accept an unverified caller-supplied string as sufficient authority and must not perform installation/fetch as a side effect.

## Burns disposition at the inspected commit

### CSV materializer

The Burns converter has strong deterministic building blocks:

- Workbook CSV discovery is sorted;
- records and structural nodes are built deterministically from source order;
- source tree hashing is deterministic;
- the conversion report is deterministic and contains no wall-clock field;
- real Text-Fabric save/reload is tested on synthetic input.

However `tests/test_text_fabric_integration.py` currently executes the synthetic CSV materializer only once. There is no explicit repeated-run semantic equivalence test at `e1218b88...`, and no managed replay tied to an exact Agora execution identity.

Conclusion: **do not attest reusable yet**. Add repeated-run semantic evidence and an exact-environment managed replay before attesting the CSV materializer.

### PDF materializer

The PDF path additionally depends on extraction behavior from the packaged Workbook PDF parser/pdfplumber. Existing tests exercise adapter/CLI behavior but do not provide repeated real PDF semantic equivalence evidence.

Conclusion: remain `unknown` or explicitly `non-reusable` for v1 until a legal synthetic PDF determinism fixture/test and exact-environment managed replay exist. Direct PDF materialization remains supported.

## Pseudepigrapha disposition

No explicit repeated-run semantic determinism contract or managed exact-environment replay was found during this bounded research pass. It does not block composition: Pseudepigrapha can remain directly executable and composition-compatible while request-identity cache reuse is disabled.

A separate evidence ticket is only necessary if Pseudepigrapha cache hits become a user requirement.

## One-shot managed artifacts for unknown/non-reusable materializers

Cacheability governs *reuse*, not whether Agora may manage the produced artifact.

For `unknown` or `non-reusable` materializers, #99 may still publish a validated managed artifact for later Context-Fabric loading in the same/user-selected workflow. Its artifact ID must not be a reusable request-identity key that causes future equivalent requests to skip execution.

A safe design is to distinguish:

- deterministic request/cache key for `reusable` mode;
- unique build/artifact identity (plus exact output tree hash and provenance) for one-shot/non-reusable mode.

#99 owns the exact storage representation after this policy lands.

## Privacy interaction

Materialization provenance currently records the basename of a local source directory. Cacheability evidence/keys must use content identity, never the basename. Public MCP/composition projections must omit local source path and basename by default as recorded in the #97 determinism/privacy amendment.

## Implementation boundary

#103 should modify only Agora registry schema/validation/policy helpers/tests/docs and cacheability dispositions supported by evidence. It should not implement the artifact cache itself.

If Burns reusable evidence requires upstream converter work, file/complete that upstream ticket independently before setting `mode: reusable` in Agora.

## Conclusion

Agora should treat cache reuse as a reviewed, exact-commit **and exact-managed-environment** registry capability. Legacy/unknown converters remain runnable but non-memoized. A new plugin release or a changed managed execution identity automatically loses effective reuse until its determinism evidence is replayed/reviewed. Burns CSV, Burns PDF and Pseudepigrapha remain non-reused until equivalent evidence exists.
