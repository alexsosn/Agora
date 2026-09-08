# Research: approved local materialization → Context-Fabric composition (#97)

## Question

What is the smallest safe Agora-owned architecture that turns the output of an already approved/installed materializer into a managed local artifact that Context-Fabric/cfabric-mcp can load without manual filesystem wiring, while preserving installation trust, sandboxing, provenance, cache safety, local-only licensing, and the materializer's execution semantics?

The cacheability/privacy findings in `P1-research-materialization-composition-97-determinism-amendment.md` are normative: reusable request-identity caching is permitted only after #103 defines an explicit reviewed cacheability contract. Unknown/legacy materializers remain executable but are not memoized/reused by request identity.

## Baseline inspected

- Agora `main`: `94bcddb45c9e1e7a1bcb766ce82a820f8be4209c`.
- Context-Fabric upstream `master`: `3a38ca80e617d872ce1664e0f0740486d0e7e8ac`.
- Agora Context-Fabric runtime pins `cfabric-mcp==0.1.7`; upstream `libs/mcp/pyproject.toml` is also `0.1.7` at the inspected commit.
- Burns Workbooks materializer: registered `ugarit-context-parsing` 0.2.0, local-only Burns-derived output.
- Dependency: the registered materializer-by-ID runner (#94/#95) must merge before production implementation here; reusable caching additionally depends on #103.

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

### Canonical artifact identity and cacheability are separate contracts

A stable artifact/receipt key can be a canonical JSON hash over at least:

- source identity: `type`, source `tree_sha256`, and immutable source revision when available;
- registered plugin id + immutable registry commit;
- installer `execution_identity_sha256`;
- materializer id;
- execution manifest SHA-256;
- explicit materializer options/arguments once the contract supports options;
- output format / composition schema version;
- the reviewed cacheability policy/attestation identity when request-identity reuse is allowed.

Timestamps, destination paths, cache roots, and other machine-local values must not affect the stable request identity. The current `plugin.code_sha256` remains valuable artifact provenance, but `execution_identity_sha256` is the stronger invalidation input because it explicitly binds dependency/runtime identity.

Crucially, identity equality does **not** by itself imply safe reuse. The current materializer-plugin v1 schema does not declare determinism/cacheability. A nondeterministic converter with identical known inputs may legitimately produce a fresh result on every execution. Therefore #103 must define the reviewed semantic cacheability contract before #99 serves request-identity cache hits. Exact output-tree hashing proves stored-byte integrity; it does not prove rerun determinism.

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

The receipt should bind the artifact key, source identity, plugin registry commit, execution identity, manifest/materializer identity, cacheability disposition/attestation where applicable, output tree hash, format, and local-only/redistribution policy.

### Publication/reuse must fail closed

A managed artifact must be validated before Context-Fabric receives it. Request-identity reuse additionally requires an explicit #103-approved reusable disposition.

Validation/reuse should require:

1. a complete receipt with the expected schema/version;
2. stable identity/key recomputation;
3. output tree hash match;
4. required materializer output paths still present;
5. materializer installation still current/approved against the selected registry before *new execution*;
6. no symlink/path escape inside managed artifact state;
7. for reuse, a current reviewed cacheability policy/attestation matching the receipt/key.

Unknown/legacy or explicitly non-cacheable materializers may still execute and produce managed one-shot artifacts, but they must not be served as request-identity cache hits.

A tampered/incomplete cache entry must not be passed to Context-Fabric. Repair/rebuild may be an explicit operation or an automatic *derived-artifact* rebuild, but it must never implicitly install/repair third-party Python.

Equivalent concurrent reusable requests need a per-artifact lock. Build into a private sibling staging directory, validate, write the cache receipt with protected creation semantics, and atomically rename into the final key. A losing process may validate/reuse the winner only where #103 permits request-identity reuse; non-cacheable executions must retain direct-execution semantics.

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

The current local materialization provenance records a source directory basename. That is acceptable for local audit state, but public MCP/tool projections must omit both the absolute local source path and basename by default because a basename can itself contain user-sensitive project/document naming. Public provenance should expose content identity/type/revision and approved converter identity instead.

### Script-level host should be refactored only as far as necessary

#95 adds a supported registry-ID execution seam but the core host remains under `scripts/`. Composition needs programmatic access to materialization results and identities, so a small Agora-owned library module may now be justified.

Do not migrate all script code pre-emptively. Extract only the stable functions/data structures needed for artifact identity/cache orchestration, with compatibility wrappers so existing script workflows/tests remain valid.

## Recommended implementation decomposition

The reviewed dependency sequence is:

1. **#103 cacheability contract** — define when a materializer may be reused and evidence Burns/Pseudepigrapha dispositions.
2. **#99 artifact cache/receipt primitive** — identity, validation, locking, transactional publication and policy-gated reuse; no Context-Fabric changes.
3. **#100 Context-Fabric managed-artifact load seam** — load/unload a validated artifact descriptor without canonical catalog mutation.
4. **#101 end-to-end composition** — approved installed materializer → managed artifact → Context-Fabric tool flow, with synthetic Burns and Pseudepigrapha coverage.

This produces smaller adversarial-review surfaces and avoids coupling cache correctness to MCP ergonomics.

## TDD implications

Before production changes, RED contracts across #103/#99/#100/#101 should cover at least:

- unspecified/legacy cacheability never produces a reusable request-identity hit while direct execution remains available;
- explicitly non-cacheable materializers execute rather than being memoized;
- same source + same execution identity/materializer/options/cacheability attestation -> same reusable key only for a reviewed cacheable materializer;
- source tree, execution identity, materializer options, or cacheability attestation change invalidates reuse;
- timestamps/absolute cache roots do not change stable request identity;
- incomplete/tampered cached artifact fails closed;
- concurrent equivalent cacheable builds publish one valid reusable artifact;
- failed conversion never exposes final artifact state;
- composition never invokes materializer fetch/install/repair implicitly;
- arbitrary filesystem paths cannot masquerade as managed artifacts;
- synthetic TF artifact loads through cfabric-mcp `CorpusManager`/Agora service without canonical catalog mutation;
- unload releases the local-artifact load cleanly;
- public responses omit sensitive local source path/basename;
- Burns synthetic CSV reaches queryable Context-Fabric through the real materializer sandbox, while no Burns-derived data are committed/uploaded and any reuse claim is backed by #103 evidence.

## Out of scope for first composition slice

- automatically choosing a materializer from arbitrary source content;
- executing uninstalled/unapproved materializers;
- putting executable converter fields into `registry/resources.yaml`;
- redistributing materialized artifacts;
- changing scholarly converter semantics;
- feature-module composition onto arbitrary derived corpora unless separately designed;
- making local materializations appear as permanent marketplace corpus resources.

## Conclusion

The smallest safe architecture is fully Agora-owned: use the approved registered materializer runner to create a managed local artifact; bind and verify that artifact in its own namespace with source + installer execution identity provenance; gate request-identity reuse on an explicit reviewed #103 cacheability disposition; then hand the validated artifact to Context-Fabric through a dedicated managed-artifact load API that reuses cfabric-mcp's existing local-directory loader without modifying the canonical Git-backed catalog.
