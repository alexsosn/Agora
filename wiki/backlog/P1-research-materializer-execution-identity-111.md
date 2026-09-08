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

## Required negative control

Any canonical semantic execution identity must still change when actual execution behavior/closure changes. The focused test should mutate or vary one genuine installed runtime input—for example an installed module byte or controlled distribution/version—and prove the canonical identity changes while full-tree integrity continues to detect direct tampering.

## Decision direction

If RED confirms only `direct_url.json`'s local build URI differs between otherwise equivalent installations, prefer a narrow solution such as one of:

1. canonicalize the known local-project origin field when deriving the semantic execution-environment digest, while retaining raw `direct_url.json` in the full integrity tree;
2. derive the semantic execution identity from a canonical manifest of runtime files where `direct_url.json` is parsed and only its ephemeral local build-root component is normalized;
3. change installation topology so pip receives a deterministic local-origin URI while preserving private/transactional build staging, if that can be done portably and without path collisions.

Do not preselect until cross-platform and migration implications are checked.

## Rejected shortcuts

- Ignore all `.dist-info` directories.
- Drop environment-tree identity and trust only package names/versions.
- Hard-code one CI-generated execution digest in the registry despite unreproducible clean installs.
- Mark Burns reusable based only on upstream converter replay evidence.
- Treat random build provenance as scholarly/converter nondeterminism.

## Scope boundary

This is Agora-owned installer/receipt identity semantics. It does not change any third-party converter behavior, package dependency declarations, cache storage, materialization output, or explicit code-execution approval.

## Conclusion

The current design has a standards-backed reproducibility defect until disproven by the real two-install RED: Agora installs local projects from random absolute paths, the packaging standard records that origin in installed metadata, and the complete runtime tree participates in `execution_identity_sha256`.

#103's pure cacheability policy and trusted installed-runtime authorization can proceed, but no concrete reusable environment attestation should be committed until #111 makes equivalent clean installations share a meaningful execution identity or demonstrates a different evidence-backed model.
