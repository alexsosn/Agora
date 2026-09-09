# Materializer cacheability

Agora treats materializer cache reuse as a reviewed runtime policy, not as an inference from immutable source code or as a claim a third-party plugin can make about itself.

The optional `cacheability` map in `registry/materializers.yaml` is keyed by a materializer ID already registered by that plugin. It affects only whether a future managed artifact cache may reuse a prior result. It never determines whether the materializer may be installed or executed directly.

## Effective states

- **Absent metadata** means cacheability is `unknown`: direct execution remains allowed, but reuse is denied.
- **`mode: non-reusable`** means equivalent requests must execute again; no reviewed-environment or evidence fields are permitted in that policy shape.
- **`mode: reusable`** is eligible for reuse only when both the current immutable plugin commit and the current integrity-verified managed execution identity exactly match reviewed metadata.

A reusable policy records `reviewed_ref` plus one or more `reviewed_environments`. Each environment binds a full `execution_identity_sha256` to non-empty structured managed-replay evidence. Duplicate reviewed execution identities and cacheability keys for unregistered materializer IDs are rejected.

## Authorization boundary

The pure policy comparator in `scripts/agora_install_materializer.py` is intentionally non-authoritative. A digest supplied by an API/CLI caller is not sufficient authority to return a cache hit.

The authoritative read-only path is `resolve_cacheability_authorization()` in `scripts/agora_materialize_registered.py`. It:

1. requires an already-installed managed materializer; it does not fetch, install, repair, import, or execute plugin code;
2. acquires the materializer runtime lock;
3. integrity-verifies the managed source/runtime/environment and consumes the exact parsed installation receipt accepted by that verification;
4. rechecks the current registry target, exact contained manifest path, registry-to-manifest binding, and selected materializer ID while the lock is held;
5. reads `execution_identity_sha256` from that verified receipt snapshot and only then compares it with reviewed cacheability policy.

A missing/tampered installation, plugin-ref drift, manifest/materializer binding drift, or an unreviewed execution identity therefore fails closed to no reusable authorization. Direct execution remains a separate contract.

## Environment and release drift

A plugin commit does not uniquely determine its managed environment. Dependency resolution, Python/runtime/platform changes, or other installed-runtime changes can produce a different `execution_identity_sha256` even when source code is unchanged. Such a new identity is non-memoized until it has its own reviewed managed replay evidence.

Likewise, changing the registered plugin ref invalidates an attestation tied to the old `reviewed_ref`. Release-update automation must not carry effective reuse across a new commit merely because other cacheability metadata stayed textually unchanged.

## Evidence and provenance

Managed replay evidence is intended to establish repeatable scholarly/content output for one exact managed execution identity using legally redistributable synthetic input. It is stronger than an upstream self-declaration or a claim that network access is denied.

Semantic replay may explicitly ignore run-specific Agora provenance fields such as a creation timestamp when those fields are not converter content. That does not weaken integrity of a cached artifact tree: future cache storage/reuse must still hash-verify the exact stored artifact separately.

A `reusable` registry entry must therefore identify the exact plugin commit, reviewed execution identity, and stable managed-replay evidence target. Platforms or environments without a reviewed identity remain fully executable but non-memoized.

## Current scope

This registry contract does not itself implement artifact storage, cache lookup, or memoization. Those consumers must use the authoritative verified-runtime authorization path above rather than calling the pure comparator with caller-provided identity data.
