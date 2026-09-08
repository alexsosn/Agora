# Research: reproducible managed materializer execution identity (#111)

## Question

Can Agora's current `execution_identity_sha256` serve as an exact reviewed cacheability environment identity across two clean installs of the same immutable plugin/dependency/runtime inputs, or does installer-local ephemeral provenance make the digest one-off?

## Baseline inspected

Agora `main@9dfca8bb90d7e5b31aa7a31131c84f22487b7411`.

Relevant installer behavior in `scripts/agora_install_materializer.py`:

1. fetched immutable plugin source is copied into a fresh `tempfile.mkdtemp(prefix="agora-materializer-build-")` directory;
2. the project is installed with pip from that local copied project path into the managed `runtime/` tree;
3. the managed environment tree hash is `_tree_hash(runtime, excludes=RUNTIME_TREE_EXCLUDES)`;
4. the exclude set removes transient VCS/Python/test cache directories but does **not** exclude installed `.dist-info` metadata such as `direct_url.json`;
5. `execution_identity_sha256` hashes the immutable source tree hash, the complete managed environment tree hash, and the Python runtime identity;
6. `_environment_current()` recomputes those same source/environment/runtime identities to detect installation tampering.

The real registered Burns install smoke on 2026-09-08 shows pip processing a randomized path of the form:

```text
Processing /tmp/agora-materializer-build-47ngvkf6/source
```

so the ephemeral path is not merely an internal Python variable; it is the actual local-project requirement pip sees.

## Packaging-standard finding

The current Python Packaging `direct_url.json` specification (PEP 610 / PyPA Direct URL Origin) says installers must create `direct_url.json` for installation from a local project such as `pip install ./app`. For local directories, the recorded URL uses the `file` scheme with an absolute path.

Therefore Agora's current installation method is expected to place the random `agora-materializer-build-*` absolute path in the installed distribution's `.dist-info/direct_url.json`.

Because `.dist-info` is currently part of `_tree_hash(runtime)`, this creates a direct path from random build-directory spelling to `environment.tree_sha256` and therefore to `execution_identity_sha256`.

This is sufficiently grounded to require a regression, but production normalization must still wait for an Agora-local two-install experiment that identifies the exact differing files/bytes.

## Security/trust distinction

Agora currently uses one environment tree hash for two related but distinct jobs:

- **integrity:** detect mutation of the installed managed runtime after installation;
- **semantic execution identity:** identify an execution environment for cacheability authorization.

An absolute temporary build-source URI is useful installation provenance but does not change the executable/plugin/dependency/runtime behavior after installation. Requiring cacheability attestations to match that random URI would make equivalent clean installations receive different semantic execution identities.

Conversely, simply excluding all `.dist-info` content would be unsafe. Distribution metadata contains names, versions, entry points, dependency/install records, and potentially executable-impacting metadata. The fix must remove or canonicalize only provenance that is both known and demonstrably path-ephemeral, or explicitly separate integrity and semantic-environment identity if the two contracts need different byte domains.

## Expected current failure mechanism

For two clean installations performed in one process/runtime with identical immutable source and dependency resolution:

```text
source_tree_sha256             equal
runtime identity               equal
resolved distributions         equal
runtime executable/package files equal
<plugin>.dist-info/direct_url.json different
    file:///tmp/agora-materializer-build-AAAA/source
    file:///tmp/agora-materializer-build-BBBB/source

environment_tree_sha256        different
execution_identity_sha256      different
```

The TDD RED must verify this rather than assuming the exact filename/content shape.

## Interaction with receipts and repair

Installation receipt schema v2 currently stores:

- source tree SHA-256;
- environment tree SHA-256;
- runtime descriptor/distributions;
- pip-report SHA-256;
- execution identity SHA-256.

`_environment_current()` validates the recorded environment tree against the complete current runtime tree. Any change to how semantic execution identity is computed must preserve this strong full-tree integrity check unless an explicit receipt migration proves an equivalent or stronger replacement.

A promising architecture is therefore to keep a full byte-integrity tree hash and derive a **separate canonical execution-environment identity** over integrity-relevant runtime content with only explicitly normalized ephemeral provenance. Exact design waits for RED evidence.

Repair also matters: reinstalling the same immutable plugin after a local integrity failure should not silently create a new cacheability identity merely because a new random build directory was used. A stable identity improves both review and repair semantics.

## TDD experiment required

Use the existing real synthetic installer fixture rather than mocking pip metadata.

Perform two fresh `install_materializer()` calls for the same synthetic plugin using:

- same process/Python runtime;
- same plugin metadata/ref/source bytes;
- same dependency resolution inputs;
- two distinct managed install roots so both installations are rebuilt from scratch.

Compare:

1. source tree hashes;
2. runtime identity objects;
3. sorted distribution sets;
4. full environment tree hashes;
5. execution identity hashes;
6. relative runtime file inventories/hashes.

When they differ, report the exact relative file paths and small textual differences needed to establish cause. The regression must specifically establish whether `direct_url.json` contains differing `agora-materializer-build-*` paths.

## Adversarial-review correction: path dependence can propagate

The first research draft treated `direct_url.json` as the likely primary differing file. That is not a sufficient model for GREEN.

A local-install path can be copied or hashed into other installed artifacts. In particular:

- wheel/distribution `RECORD` may contain the digest of `direct_url.json`, so changing or canonicalizing the origin file without accounting for the corresponding `RECORD` row can leave a second path-derived byte difference;
- console-entry scripts or wrappers may contain absolute interpreter, target, or installation paths in shebangs or generated launcher content;
- other backend- or pip-generated metadata may derive from the local source/target path even when it does not literally contain the path string.

Therefore RED must build a deterministic **complete runtime diff inventory**, not stop after finding the first expected file. For every differing relative path it must classify the difference as one of:

1. direct ephemeral Agora staging provenance;
2. derived metadata whose value changes only because of an already-proven ephemeral field (for example a `RECORD` digest row for such a field);
3. target/interpreter path material generated by the installer;
4. unexplained or execution-significant difference.

The test/research record must inspect `*.dist-info/RECORD`, every generated script/launcher directory present in the managed target, and any other differing file. GREEN is blocked while category (4) exists.

Normalization must be dependency-aware. If an ephemeral field is canonicalized, any cryptographic record derived from that field may be recomputed from the canonical bytes, but unrelated `RECORD` rows and metadata must remain byte-sensitive. A whole-file or whole-directory ignore is not acceptable.

Generated scripts require an explicit semantic decision from RED evidence. If their absolute path is needed at execution time, it belongs in execution identity or installation topology must be changed so equivalent installations produce equivalent executable bytes. It must not be erased merely to make hashes equal.

The two-install experiment should also scan differing textual files for both random build roots and both managed install roots, so path leakage is detected even when the filename was not predicted in advance.

## Required negative control

Any canonical semantic execution identity must still change when actual execution behavior/closure changes. The focused test should mutate or vary one genuine installed runtime input—for example an installed module byte or controlled distribution/version—and prove the canonical identity changes while full-tree integrity continues to detect direct tampering.

Negative controls must also cover derived metadata: changing a non-ephemeral `RECORD` row, entry-point definition, generated executable wrapper, distribution/version metadata, or non-ephemeral `direct_url.json` field must change canonical identity or fail closed.

## Decision direction

If RED proves that the complete differing set consists only of a small graph of Agora-generated path provenance plus its deterministic derived metadata, prefer a narrow solution such as one of:

1. canonicalize the proven local-project origin field and recompute only directly-derived canonical metadata such as its `RECORD` digest while retaining the raw files for full integrity;
2. derive the semantic execution identity from a canonical manifest of runtime files with explicit per-file transformations for every RED-proven ephemeral field and dependency;
3. change installation topology so pip receives deterministic source/target identities and generated executable bytes are stable, if this can be done portably without weakening private/transactional staging.

Do not preselect until the complete two-install diff, generated scripts, cross-platform implications, and receipt migration are checked.

## Rejected shortcuts

- Ignore all `.dist-info` directories.
- Ignore all `RECORD` files or all generated scripts.
- Normalize only `direct_url.json` while leaving path-derived metadata unexplained.
- Drop environment-tree identity and trust only package names/versions.
- Hard-code one CI-generated execution digest in the registry despite unreproducible clean installs.
- Mark Burns reusable based only on upstream converter replay evidence.
- Treat random build provenance as scholarly/converter nondeterminism.

## Scope boundary

This is Agora-owned installer/receipt identity semantics. It does not change any third-party converter behavior, package dependency declarations, cache storage, materialization output, or explicit code-execution approval.

## Conclusion

The current design has a standards-backed reproducibility defect until disproven by the real two-install RED: Agora installs local projects from random absolute paths, the packaging standard records that origin in installed metadata, and the complete runtime tree participates in `execution_identity_sha256`.

The defect investigation must cover all direct and derived path-sensitive installed bytes, not only the expected origin file. #103's pure cacheability policy and trusted installed-runtime authorization can proceed, but no concrete reusable environment attestation should be committed until #111 makes equivalent clean installations share a meaningful execution identity or demonstrates a different evidence-backed model.
