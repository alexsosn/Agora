# Issue #252 — fail closed on acquisition strategy drift

## Real research, 2026-10-11
- Both `registry/resources.yaml` and `registry/feature-modules.yaml` use `registry/schema/resources.schema.json` via `scripts/validate_registry.py`. The schema currently accepts any strategy string, although catalog loader `Catalog._resources_from_document` merely forwards it and no generic dynamic release-archive strategy exists.
- Canonical resource strategies are **repository**, **collection**; canonical feature modules additionally include **local-module** (the registered `cuc-burns` produced feature module). This must be preserved; do not accidentally reject CUC Burns or Greek collections.
- `service_source_modes.py` references dynamic `user-local` provenance, but user-local imports are not declared in canonical catalog YAML; dynamic resource instances must not be unintentionally prohibited by changes to static schema.
- #251/#226 are future release ZIP acquisition features. A string like `github-release-archive` passing validation before runtime/installer support is dishonest discovery, not functional support.

## RED / GREEN / verification gates
1. **RED:** an isolated unit test mutates an actual registered resource and a feature module to unknown acquisition strategies, expecting JSON schema rejection and early `Catalog._resources_from_document` fail-closed error; also test valid canonical data and pinned CUC Burns local-module remain accepted.
2. **GREEN:** narrow schema enum to exactly `repository`, `collection`, `local-module` and check explicitly provided runtime strategy against the same set. Retain implicit runtime default `repository` for legacy in-memory synthetic fixture compatibility, but schema already requires a declared strategy on stored records.
3. **Review:** skeptical independent pass tests real registry examples, code path from registry to generated plugin catalog, and refusal to advertise hypothetical release ZIP loading.
4. **CI:** generator freshness, `validate_registry`, runtime/catalog tests, exact-head all seven Foundation jobs; merge only green. Keep #252 separate from #249 Git partial clone diagnostics and #251 ZIP integration.
