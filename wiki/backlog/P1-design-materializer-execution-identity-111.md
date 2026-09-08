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
2. **canonical execution-environment identity** must identify executable/package/dependency/runtime behavior and must not change solely because pip recorded a different random Agora build pathname.

The preferred implementation shape, if RED confirms the predicted `direct_url.json` cause, is to preserve the existing raw environment tree hash and add a narrowly canonicalized execution-environment hash used by `execution_identity_sha256`.

Do not ignore complete `.dist-info` directories or reduce identity to package names/versions.

## RED 1 — prove current clean-install non-reproducibility

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
4. current raw environment tree hashes are **different** on the pre-fix implementation;
5. current `execution_identity_sha256` values are **different** on the pre-fix implementation;
6. a deterministic runtime-tree diff helper identifies the exact differing relative files;
7. the diff includes the installed plugin's `*.dist-info/direct_url.json` and proves the semantic difference is the random `agora-materializer-build-*` absolute source URI;
8. all other differing paths, if any, are reported and must be researched before GREEN rather than silently added to an ignore list.

The committed RED should express the desired post-fix contract (equal canonical execution identities) and therefore fail on current code, while diagnostic assertions/logging preserve evidence of the current raw-tree cause.

If current pip behavior unexpectedly produces equal raw trees, stop: revise research based on the observed result rather than implementing speculative normalization.

## GREEN 1 — separate raw integrity from canonical execution environment

Only after RED evidence identifies the path-dependent metadata, add the smallest canonical execution-environment hashing primitive.

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
- canonical execution hashing walks the same runtime tree and hashes every path/type/content except for explicitly normalized fields established by RED evidence;
- for the plugin-local `direct_url.json` case, parse JSON and normalize only the Agora-generated ephemeral local build-origin URI; preserve all other keys/values so VCS/archive/origin changes remain visible;
- malformed or unexpected direct-url metadata fails closed rather than being dropped;
- dependency distributions' own provenance is not normalized unless an independent RED proves equivalent Agora-generated path noise there too;
- `execution_identity_sha256` uses the canonical execution tree hash plus immutable source tree and runtime identity.

## Receipt compatibility

Do not silently reinterpret existing schema-v2 receipts.

Implementation must explicitly choose and test one compatible strategy. Preferred direction:

- v3 receipts use raw integrity + canonical execution identity;
- v2 receipts remain verifiable for existing direct execution under their historical formula where feasible;
- reviewed reusable-cache authorization must not claim a v2 identity is the new reproducible identity merely because its 64-hex digest happens to match configured metadata;
- repair/reinstall upgrades a v2 installation to v3 through the existing explicit repair path, not background mutation.

If supporting v2 in `_environment_current()` would materially complicate security guarantees, document an explicit fail-closed migration requiring repair instead; do not accidentally accept stale receipts.

## RED 2 — negative identity and integrity controls

Before finalizing GREEN, freeze:

1. changing an installed Python module byte changes raw integrity and makes `_environment_current()` fail;
2. changing that module in an independently rebuilt fixture changes canonical execution identity;
3. changing a distribution/version/entry-point or other execution-bearing metadata changes canonical identity;
4. changing only the random Agora build directory spelling does **not** change canonical identity;
5. changing non-ephemeral fields inside `direct_url.json` does change canonical identity or fails validation;
6. two clean equivalent installs now have equal canonical execution identities but distinct raw tree hashes if raw provenance paths differ.

## GREEN 2

Implement only normalization/migration behavior required by the negative controls. No registry disposition yet.

## #103 integration gate

After #111 GREEN:

- update #103 trusted authorization tests to consume the reproducible receipt contract if needed;
- no `reusable` Burns environment is committed until Burns is installed under the new receipt identity and the upstream semantic replay is executed successfully in that exact managed runtime;
- evidence must record the exact canonical `execution_identity_sha256` produced by that managed replay.

## Test gates

Before final review:

- focused real two-install reproducibility tests;
- complete Foundation suite;
- Linux/macOS/Windows materializer installation lock + migration regressions;
- Registered materializer install smoke;
- Materialization sandbox E2E if receipt/runner paths are touched;
- release-update tests remain unaffected;
- exact-head only.

## Independent adversarial review focus

Review the frozen patch from scratch and challenge:

1. whether raw runtime integrity was weakened to make identities equal;
2. whether normalization ignores more than the exact proven ephemeral field;
3. whether malicious/tampered `direct_url.json` can be normalized into a trusted equivalent state;
4. whether dependency/package/version/entry-point changes still affect canonical identity;
5. whether v2/v3 receipt handling can authorize stale or ambiguously interpreted installations;
6. whether absolute user/install/source paths leak into the canonical identity;
7. whether the two-install test really rebuilds twice rather than hitting installer idempotency;
8. whether the fixture uses real pip local-project installation without network dependence;
9. whether repair/concurrent install locking semantics regress;
10. whether any third-party converter behavior slipped into scope.

Every blocker becomes a focused RED before its fix.

## Definition of done

#111 is complete when two fresh equivalent managed installs on one runtime/platform produce the same canonical `execution_identity_sha256`, raw full-tree integrity remains tamper-sensitive, path normalization is limited to evidence-proven installer provenance, receipt compatibility is explicit, ordinary install/sandbox/lock suites are green, and a fresh logically independent adversarial review finds no blocker.
