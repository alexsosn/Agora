# Plan: reproducible managed materializer execution identity (#111)

## Goal

Make the execution identity used by reviewed materializer cacheability reproducible across clean equivalent installations without weakening Agora's existing full managed-runtime integrity verification.

Research: `P1-research-materializer-execution-identity-111.md`.

## Scope boundary

This ticket owns Agora installer/receipt identity semantics and tests. It does not implement artifact caching, alter converter semantics, change dependency declarations, or relax explicit code-execution approval.

#103's pure policy/trusted authorization work may proceed independently. No concrete `reusable` registry environment should be added until this ticket lands and the reviewed materializer is reinstalled/replayed under the new identity contract.

## Design invariant

Do not conflate two byte domains:

1. **full runtime integrity identity** must continue to detect mutation of every managed installed file that Agora currently protects, including raw installer provenance;
2. **canonical execution-environment identity** must identify executable/package/dependency/runtime behavior and must not change solely because pip or Agora recorded an equivalent installation under a different ephemeral staging/target pathname.

The implementation shape must be selected only after RED classifies the complete set of differing installed bytes. Preserving the existing raw environment tree hash and adding a narrowly canonicalized execution-environment hash is preferred only if the experiment proves that all differences can be safely and explicitly transformed.

Do not ignore complete `.dist-info` directories, `RECORD` files, generated script directories, or reduce identity to package names/versions.

## RED 1 — prove and classify current clean-install non-reproducibility

Commit tests before production changes.

Use a synthetic local Python materializer whose build backend and dependency setup require no network. The fixture must still pass through the real production `_install_python()`/pip local-project path so pip writes exactly the metadata production installs produce.

Perform two clean `install_materializer()` operations in the same test process with:

- identical registry plugin metadata/ref;
- identical source tree bytes;
- identical Python runtime/platform;
- two different Agora install roots;
- no reuse of the first managed installation.

Freeze these assertions:

1. source tree hashes are equal;
2. runtime identity objects are equal;
3. resolved distribution lists are equal;
4. current raw environment tree hashes are **different** on the pre-fix implementation if path-sensitive metadata exists;
5. current `execution_identity_sha256` values are **different** on the pre-fix implementation under the same condition;
6. a deterministic runtime-tree diff helper identifies the **complete** set of differing relative files and concise byte/text diagnostics;
7. the experiment checks whether the installed plugin's `*.dist-info/direct_url.json` contains differing `agora-materializer-build-*` absolute source URIs;
8. the experiment parses `*.dist-info/RECORD` and identifies rows/digests derived from every differing canonicalization candidate;
9. every generated script/launcher present under the managed target is compared byte-for-byte and inspected for build-root, install-root, runtime-root, and interpreter-path dependence;
10. differing textual files are scanned for both random build roots and both managed install roots even when their filenames were not predicted;
11. each differing file is classified as direct ephemeral staging provenance, derived metadata from a proven ephemeral field, generated target/interpreter-path material, or unexplained/execution-significant;
12. any unexplained/execution-significant difference blocks GREEN and updates research rather than being silently added to a transform/ignore list.

The committed RED should express the desired post-fix contract (equal canonical execution identities for equivalent installations) and therefore fail on current code, while diagnostics preserve the complete current raw-tree evidence.

If current pip behavior unexpectedly produces equal raw trees, stop: revise research based on the observed result rather than implementing speculative normalization.

## GREEN 1 — separate raw integrity from a complete canonical execution environment

Only after RED has classified **every** path-dependent runtime difference may production code add a canonical execution-environment hashing primitive.

Conceptual receipt v3 shape:

```json
{
  "schema_version": 3,
  "environment": {
    "tree_sha256": "<raw full runtime tree>",
    "execution_tree_sha256": "<canonical execution runtime tree>",
    "...": "existing fields"
  },
  "execution_identity_sha256": "<source + execution_tree + runtime identity>"
}
```

Exact naming may differ if a clearer compatible schema emerges.

Requirements:

- `environment.tree_sha256` remains the raw full byte-integrity hash and `_environment_current()` continues to recompute/check it;
- canonical execution hashing walks the same runtime tree and hashes every path/type/content unless an explicit RED-proven transformation applies;
- direct local-origin metadata may normalize only the exact Agora-generated ephemeral URI/path component; all unrelated keys/values remain byte-sensitive;
- if a transformed file is represented by a cryptographic row in `RECORD`, the canonical representation must recompute that row from the canonical file bytes rather than ignore the row or the whole `RECORD` file;
- unrelated `RECORD` rows, sizes, hashes, entry-point metadata, package metadata, and generated executable content remain execution-sensitive;
- generated scripts/launchers are never normalized merely because they contain an absolute path. RED must prove whether the path is semantically relocatable; otherwise installation topology must produce stable executable bytes or the bytes remain identity-bearing;
- malformed or unexpected provenance/record metadata fails closed rather than being dropped;
- dependency distributions' provenance is not normalized unless RED independently proves Agora-generated equivalent path noise there;
- the canonical transform set is explicit, auditable, and fails closed on an unexpected path-sensitive file;
- `execution_identity_sha256` uses the canonical execution tree hash plus immutable source tree and runtime identity.

A canonicalizer must be dependency-aware: changing a transformed source field can require deterministic transformation of metadata cryptographically derived from it. It must not canonicalize the first differing file while leaving its descendants inconsistent.

## Receipt compatibility

Do not silently reinterpret existing schema-v2 receipts.

Implementation must explicitly choose and test one compatible strategy. Preferred direction:

- v3 receipts use raw integrity + canonical execution identity;
- v2 receipts remain verifiable for existing direct execution under their historical formula where feasible;
- reviewed reusable-cache authorization must not claim a v2 identity is the new reproducible identity merely because its 64-hex digest happens to match configured metadata;
- repair/reinstall upgrades a v2 installation to v3 through the existing explicit repair path, not background mutation.

If supporting v2 in `_environment_current()` would materially complicate security guarantees, document an explicit fail-closed migration requiring repair instead; do not accidentally accept stale receipts.

## RED 2 — negative identity, derivation, and integrity controls

Before finalizing GREEN, freeze:

1. changing an installed Python module byte changes raw integrity and makes `_environment_current()` fail;
2. changing that module in an independently rebuilt fixture changes canonical execution identity;
3. changing a distribution version, entry point, package metadata, or other execution-bearing metadata changes canonical identity;
4. changing only a RED-proven ephemeral Agora staging pathname does **not** change canonical identity;
5. changing a non-ephemeral field inside `direct_url.json` changes canonical identity or fails validation;
6. changing an unrelated `RECORD` row/hash/size changes canonical identity or fails validation;
7. the canonical `RECORD` representation for any transformed file matches the digest/size of that file's canonical bytes;
8. changing generated console script or launcher executable content changes canonical identity;
9. an unexpected absolute build/install path in any unclassified runtime file fails the reproducibility test rather than being silently normalized;
10. two clean equivalent installs have equal canonical execution identities while raw tree hashes may remain distinct where raw provenance differs.

## GREEN 2

Implement only normalization/migration behavior required by the negative controls. No registry disposition yet.

## Cross-platform evidence gate

Path-sensitive installation metadata differs by platform and installer behavior. Before declaring #111 complete:

- run the two-install classification on Linux, macOS, and Windows when the platform supports the managed installer path;
- record the complete differing relative-file set per platform;
- do not assume a transformation proven on POSIX applies to Windows launchers or vice versa;
- platform-specific canonicalization is acceptable only when it is explicit and evidence-backed while yielding stable identities for equivalent installs on that same runtime/platform;
- cross-platform identities do not need to be equal because `runtime_identity()` intentionally distinguishes platform/ABI/runtime.

## #103 integration gate

After #111 GREEN:

- update #103 trusted authorization tests to consume the reproducible receipt contract if needed;
- no `reusable` Burns environment is committed until Burns is installed under the new receipt identity and the upstream semantic replay is executed successfully in that exact managed runtime;
- evidence must record the exact canonical `execution_identity_sha256` produced by that managed replay.

## Test gates

Before final review:

- focused real two-install reproducibility/classification tests;
- complete Foundation suite;
- Linux/macOS/Windows materializer installation lock + receipt migration regressions;
- platform-specific runtime-diff evidence for generated scripts/metadata;
- Registered materializer install smoke;
- Materialization sandbox E2E if receipt/runner paths are touched;
- release-update tests remain unaffected;
- exact-head only.

## Independent adversarial review focus

Review the frozen patch from scratch and challenge:

1. whether raw runtime integrity was weakened to make identities equal;
2. whether normalization ignores more than the exact proven ephemeral field graph;
3. whether `RECORD` or another derived metadata file still changes because a canonicalized input changed;
4. whether malicious/tampered `direct_url.json` can be normalized into a trusted equivalent state;
5. whether generated scripts/shebangs/launchers carry path-sensitive executable semantics that were erased;
6. whether dependency/package/version/entry-point changes still affect canonical identity;
7. whether v2/v3 receipt handling can authorize stale or ambiguously interpreted installations;
8. whether absolute user/install/source paths leak into the canonical identity outside classified transforms;
9. whether the two-install test really rebuilds twice rather than hitting installer idempotency;
10. whether the fixture uses real pip local-project installation without network dependence;
11. whether the test enumerates the complete runtime diff rather than asserting only expected files;
12. whether repair/concurrent install locking semantics regress;
13. whether platform-specific launcher behavior is tested rather than inferred;
14. whether any third-party converter behavior slipped into scope.

Every blocker becomes a focused RED before its fix.

## Definition of done

#111 is complete when two fresh equivalent managed installs on one runtime/platform produce the same canonical `execution_identity_sha256`, raw full-tree integrity remains tamper-sensitive, the complete path-sensitive runtime diff and its derived metadata are classified, normalization is limited to evidence-proven installer provenance/derivations, generated executable semantics remain identity-bearing unless made reproducible by installation topology, receipt compatibility is explicit, ordinary install/sandbox/lock suites are green, and a fresh logically independent adversarial review finds no blocker.
