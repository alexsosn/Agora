# Research: approved local materialization → Context-Fabric composition (#97)

## Question

What is the smallest safe Agora-owned architecture that turns the output of an already approved/installed materializer into a reusable local artifact that Context-Fabric/cfabric-mcp can load without manual filesystem wiring, while preserving installation trust, sandboxing, provenance, cache safety, and local-only licensing?

## Baseline inspected

- Agora `main`: `94bcddb45c9e1e7a1bcb766ce82a820f8be4209c`.
- Context-Fabric upstream `master`: `3a38ca80e617d872ce1664e0f0740486d0e7e8ac`.
- Agora Context-Fabric runtime pins `cfabric-mcp==0.1.7`; upstream `libs/mcp/pyproject.toml` is also `0.1.7` at the inspected commit.
- Burns Workbooks materializer: registered `ugarit-context-parsing` 0.2.0, local-only Burns-derived output.
- Dependency: the registered materializer-by-ID runner (#94/#95) must merge before production implementation here.

## Findings

### cfabric-mcp already accepts arbitrary local Text-Fabric directories

`cfabric_mcp.corpus_manager.CorpusManager.load(path, name, features)` resolves a local directory and directly calls `cfabric.Fabric(locations=...)`. No canonical Git catalog entry is required by cfabric-mcp itself.

Therefore no upstream cfabric-mcp change is required for the first composition slice. The missing work is Agora-owned orchestration and lifecycle.

### Agora's current Context-Fabric public tools are catalog-ID-only

`prepare_corpus` and `load_corpus` accept a canonical `resource_id` and delegate through `ContextFabricResolver.prepare_with_modules(...)`.

The resolver manufactures `PreparedCorpus` only from registered Git-backed corpus/collection resources. `Catalog.ResourceSpec` itself requires an upstream repository. Treating a materialized local artifact as an ordinary canonical resource would therefore be artificial and would risk mixing executable/materialization state into the static Git-backed corpus registry.

The existing service ultimately loads a `PreparedCorpus.path` via the same `corpus_manager.load(path, name, features)` call. This is the useful seam: composition should introduce an Agora-owned *prepared local artifact* path, not mutate the canonical catalog.

### Existing materialization provenance already supplies most artifact-identity inputs

`scripts/agora_materialize.py` already records:

- local source `tree_sha256` (and Git commit when applicable);
- plugin id/version;
- materializer id;
- managed runtime/plugin code digest;
- materializer manifest SHA-256;
- output format;
- sandbox backend;
- transactional staging and atomic publication.

The registered installer additionally records `execution_identity_sha256`, binding immutable plugin source, the complete installed environment/dependency tree, and Python/runtime identity.

Composition should reuse these identities rather than introduce a second incompatible hashing model.

### Recommended canonical artifact identity

For the first supported version, the deterministic artifact key should be a canonical JSON hash over at least:

- source identity: `type`, source `tree_sha256`, and immutable source revision when available;
- registered plugin id + immutable registry commit;
- installer `execution_identity_sha256`;
- materializer id;
- execution manifest SHA-256;
- explicit materializer options/arguments once the contract supports options;
- output format / composition schema version.

Timestamps, destination paths, cache roots, and other machine-local values must not affect the key.

The current `plugin.code_sha256` remains valuable artifact provenance, but `execution_identity_sha256` is the stronger cache invalidation input because it explicitly binds dependency/runtime identity.

### Cache ownership should remain Agora-wide, not Context-Fabric's Git cache

The materialized TF artifact is a derived result, not a Git source snapshot. It should live in a dedicated Agora materialization-artifact namespace rather than inside Context-Fabric's repository/materialized-object layout.

Proposed ownership shape (exact names are design-stage, not yet contract):

```text
<Agora data/cache root>/materialized-artifacts/
  <artifact-key>/
    artifact/                 # immutable published TF output
      *.tf
      agora-materialization.json
      conversion-report.json  # converter-owned when present
    agora-artifact.json        # Agora composition/cache receipt
```

The receipt should bind the artifact key, source identity, plugin registry commit, execution identity, manifest/materializer identity, output tree hash, format, and local-only/redistribution policy where relevant.

### Publication/reuse must fail closed

Reuse should require:

1. a complete receipt with the expected schema/version;
2. deterministic key recomputation;
3. output tree hash match;
4. required materializer output paths still present;
5. materializer installation still current/approved against the selected registry before *new execution*;
6. no symlink/path escape inside managed artifact state.

A tampered/incomplete cache entry must not be passed to Context-Fabric. Repair/rebuild may be an explicit operation or an automatic *derived-artifact* rebuild, but it must never implicitly install/repair third-party Python.

Equivalent concurrent requests need a per-artifact lock. Build into a private sibling staging directory, validate, write the cache receipt with protected creation semantics, and atomically rename into the final key. A losing process should validate/reuse the winner rather than publish competing output.

### Context-Fabric hand-off should be a dedicated local-artifact API

The least invasive service design is an Agora Context-Fabric operation that receives a validated managed artifact descriptor/path and loads it through the existing loader lifecycle without adding it to `Catalog`.

Possible internal shape:

```text
PreparedLocalArtifact(
  artifact_id,
  logical_name,
  path,
  provenance,
  cache_residency,
)
```

The service can share the existing `loader.load(path, name, features)` and unload semantics. If it should participate in Context-Fabric cache leases/cold compilation, that should be explicit design work rather than pretending the derived artifact is a GitStore object.

For the first Burns slice, generated TF is already ordinary Text-Fabric and cfabric-mcp can load it directly; no source-Git acquisition is needed after materialization.

### Public MCP/API shape should not accept arbitrary artifact paths

A new public tool should take an Agora-owned artifact ID/key (or a composition request that returns one), not an unrestricted filesystem path. Otherwise the new tool would recreate the same self-authenticating-path problem that registry-ID materializer execution is removing.

A plausible staged public flow is:

```text
materialize_local_corpus(plugin_id, materializer_id, source, ...)
  -> {artifact_id, provenance, format}

load_materialized_corpus(artifact_id, features=...)
  -> normal loaded-corpus response + materialization provenance
```

A later convenience operation may compose both steps, but keeping them separable makes cache reuse, inspection, and trust decisions explicit.

### Licensing/privacy policy must be metadata and behavior, not documentation only

Burns-derived outputs must remain local because of the upstream CC BY-NC-ND 2.5 boundary used by the project. CI must use synthetic fixtures and must not upload Burns-derived workflow artifacts.

The managed artifact receipt should record a redistribution policy/classification derived from the registered materializer/data-license metadata where available. The first implementation does not need a universal license reasoner, but it must at least preserve `local-only` for Burns and avoid treating cache entries as marketplace-distributable resources.

### Script-level host should be refactored only as far as necessary

#95 adds a supported registry-ID execution seam but the core host remains under `scripts/`. Composition needs programmatic access to materialization results and identities, so a small Agora-owned library module may now be justified.

Do not migrate all script code pre-emptively. Extract only the stable functions/data structures needed for artifact identity/cache orchestration, with compatibility wrappers so existing script workflows/tests remain valid.

## Recommended implementation decomposition

This ticket is large enough to split if review independence benefits:

1. **Artifact cache/receipt primitive** — deterministic identity, validation, locking, transactional publication/reuse; no Context-Fabric changes.
2. **Context-Fabric managed-artifact load seam** — load/unload a validated artifact descriptor without canonical catalog mutation.
3. **End-to-end composition** — approved installed materializer → cache → Context-Fabric tool flow, with synthetic Burns and Pseudepigrapha coverage.

Research recommends filing these as separate implementation tickets if the plan confirms they can be logically independent. That produces smaller adversarial-review surfaces and avoids coupling cache correctness to MCP ergonomics.

## TDD implications

Before production changes, RED contracts should cover at least:

- same source + same execution identity/materializer/options -> same artifact key and reuse;
- source tree or execution identity change -> different artifact key;
- timestamps/absolute cache roots do not change identity;
- incomplete/tampered cached artifact fails closed;
- concurrent equivalent builds publish one valid artifact;
- failed conversion never exposes final artifact state;
- composition never invokes materializer fetch/install/repair implicitly;
- arbitrary filesystem paths cannot masquerade as managed artifacts;
- synthetic TF artifact loads through cfabric-mcp `CorpusManager`/Agora service without canonical catalog mutation;
- unload releases the local-artifact load cleanly;
- Burns synthetic CSV reaches queryable Context-Fabric through the real materializer sandbox, while no Burns-derived data are committed/uploaded.

## Out of scope for first composition slice

- automatically choosing a materializer from arbitrary source content;
- executing uninstalled/unapproved materializers;
- putting executable converter fields into `registry/resources.yaml`;
- redistributing materialized artifacts;
- changing scholarly converter semantics;
- feature-module composition onto arbitrary derived corpora unless separately designed;
- making local materializations appear as permanent marketplace corpus resources.

## Conclusion

The smallest safe architecture is fully Agora-owned: use the approved registered materializer runner to create a deterministic managed local artifact; cache and verify that artifact in its own namespace with source + installer execution identity provenance; then hand the validated artifact to Context-Fabric through a dedicated managed-artifact load API that reuses cfabric-mcp's existing local-directory loader without modifying the canonical Git-backed catalog.
