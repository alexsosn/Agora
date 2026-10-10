# Issue #135 RED3d — bundled Context-Fabric resolver construction

## Research

Prior gates introduced `resolve_managed_parent(materializer, resolver)` and `materialize_managed_feature_module(..., resolver=...)` (RED3a–3c). They deliberately accept injected resolvers so tests can use fake immutable TF snapshots. But an *arbitrary caller-supplied resolver is not a security proof*: it can return a fabricated `PreparedCorpus`, malicious catalog or cache root, even with `ParentBinding.trusted=True`.

Audited actual code: `plugins/context-fabric/src/agora_context_fabric/server.py:build_runtime` builds `Catalog.from_plugin_root(plugin_root)`, `GitStore(cache_dir)`, and `ContextFabricResolver(catalog, store)` (with separate `LocalImports` if importing local files); default plugin root and default cache path come from `server.py`. The repository-bundled `plugins/context-fabric/resources/catalog.yaml` identifies CUC as a corpus, pinning upstream `DT-UCPH/cuc` revision `0408967b1808c1f22c69e299d302b1e7b5e26354` and version `tf/0.2.8`. `resolve_managed_parent` already refuses wrong resource/version and paths outside immutable snapshot cache. `GitStore.acquire_cache_lease` now wraps registered execution.

## Scope / implementation plan

1. Preserve low-level injected-resolver API **for internal testing** without adding a user-facing `--parent-path`, `--resolver`, or `--plugin-root` option.
2. Add a separate internally constructed resolver/facade whose catalog path derives from Agora's own installed/bundled code, *not* caller input. Cache directory may be configured, because it is a cache location and not a parent corpus locator. Keep it consistent with Context-Fabric server's documented cache default.
3. Reuse the parent validation and lease path from RED3a–3c; do not duplicate these checks, acquire data without user opt-in, or add third-party plugin code to Agora. Keep registered plugin installation/integrity checks intact.
4. RED tests: cannot inject resolver or catalog path via facade; constructor uses exact bundled catalog and selected cache; delegates a real resolver/store to existing lease-wrapped method; invalid source constraints fail closed; no arbitrary path accepted as trusted.
5. GREEN implementation, exact-head Foundation, independent source-level adversarial review. No claim of secure published/user-facing composition until module publication and real CUC + Burns load/query acceptance.

## Deferred security and product work

Untrusted `--parent-path` override needs explicit `untrusted` provenance and different sandbox semantics; never silently mark paths trusted. Need share/deduplicate parent snapshots between multiple feature modules, verify module features target existing CUC node identities, publish to Context-Fabric local module cache with provenance, and test actual data interoperability. A local user who can tamper with their own Agora installation or cache is outside the guarantees of the `trusted` metadata bit; the model here is not a cryptographic attestation of filesystem contents.
