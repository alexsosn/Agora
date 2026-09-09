# Research: load verified managed artifacts in Context-Fabric (#100)

## Question

How should the installed Agora Context-Fabric plugin load a #99 managed Text-Fabric artifact by Agora artifact ID without accepting arbitrary filesystem paths, mutating the canonical catalog, duplicating producer authority, or allowing removal to race an active load?

## Baseline inspected

Agora `main`: `734e13fb946aeecf47b4d1b5b0fe69577c45ee63`.

Relevant current implementation:

- `plugins/context-fabric/pyproject.toml` is a standalone Python project and packages only `agora_context_fabric*` from its own `src/` tree.
- Canonical marketplace generation installs/launches Context-Fabric from `./plugins/context-fabric`.
  - Claude launches `uv run --locked --project ${CLAUDE_PLUGIN_ROOT} ...`.
  - Codex launches `uv run --locked --project . ...` from the plugin root.
- Therefore repository-level `scripts/` are not a portable import dependency of the installed Context-Fabric plugin.
- Current public `load_corpus` resolves only canonical catalog resources through `ContextFabricResolver`; `Catalog.ResourceSpec` represents upstream resources and requires repository/source semantics.
- `ContextFabricService.load()` ultimately delegates to `loader.load(str(prepared.path), name=prepared.logical_name, features=features)` and already has:
  - cold/warm compilation supervision;
  - exact-object compile locking for canonical cache objects;
  - transactional replacement of loaded leases only after a successful replacement load;
  - idempotent unload;
  - active-load status/cancellation.
- `PreparedCorpus` is a simple internal dataclass containing resource/logical identity, path, version/revision and modules. Its type does not itself require a catalog entry, but the current resolver is the only constructor on the public path.

## #99 contract consumed by this ticket

The current #99 design gives #100 a dedicated managed-artifact namespace and promises:

- artifact IDs generated/validated by Agora rather than caller paths;
- private object/payload/receipt layout;
- immutable receipt plus complete non-`.cfm` payload manifest/hash;
- required output revalidation;
- a public privacy-bounded descriptor with no source/cache absolute path or local basename;
- an internal payload-path resolver only after artifact ID + receipt + payload validation;
- `.cfm/` reserved for later Context-Fabric-owned mutable consumer state;
- artifact-ID-derived compile locks, distinct from canonical GitStore locks;
- no implicit materializer install/fetch/repair on artifact read.

Independent #100 research found one missing lifecycle primitive and recorded a normative #99 design amendment: a managed artifact also needs a long-lived **shared use lease** held for the complete consumer/load lifetime, with destructive removal taking the corresponding exclusive use lock. Compile locking stays a separate artifact-ID exclusive lock. This prevents removal of a loaded-but-not-currently-compiling artifact without serializing warm readers.

## Packaging finding: do not import repository `scripts/`

The tempting implementation is for `agora_context_fabric` to import #99's repository-level producer/store script. That is rejected.

The Context-Fabric plugin is installed as its own project root by both supported client launch paths. Depending on `../../scripts` would:

- work only from some Agora checkout layouts;
- break the plugin's current standalone packaging contract;
- make Claude/Codex behavior depend on host copy/install details outside the generated plugin root;
- create an undeclared executable dependency absent from the plugin lockfile;
- weaken the verified platform-startup contract.

A new shared Python distribution solely to avoid a small verification implementation is also premature. It would add package publication/versioning/lockfile lifecycle before #99's receipt contract exists and would broaden #100 beyond the user outcome.

## Trust seam: shared format contract, independent consumer verification

The shared authority between #99 and #100 should be the **versioned artifact ID / receipt / payload-manifest contract**, not a shared filesystem import.

#99 remains authoritative for:

- creating IDs;
- publication/staging;
- reusable vs one-shot creation disposition;
- producer-side receipt construction;
- publication-time payload manifest;
- mutation/removal APIs and artifact lock namespaces.

#100 independently verifies the already-published object as a consumer before dereferencing its payload. This is intentional defense in depth, not a second producer implementation. The consumer must not recreate request keys, decide cacheability, run materializers, repair objects, or rewrite receipts.

Cross-contract tests in the Agora source repository can instantiate a synthetic #99-produced object and require the packaged `agora_context_fabric` consumer verifier to accept it. Mutating every authority-bearing receipt/payload dimension must make the consumer fail closed. Receipt-version changes unsupported by the plugin must fail explicitly rather than be guessed.

This gives a stable distribution boundary: the plugin needs only the documented receipt format and managed-store root convention, not repository producer code.

## Store location and public input

Public/MCP input is only an `artifact_id`.

The service may receive/configure the managed-artifact store root internally, using the same Agora data-home convention as #99. Tests must support an injected temporary root. Neither the public tool nor its descriptor accepts/returns a caller-selected payload path.

Resolution sequence:

1. validate artifact ID syntax before filesystem access;
2. derive the contained object path from configured store root + ID;
3. acquire a shared artifact-use lease through the #99-defined lock convention/API contract;
4. re-open/revalidate receipt + immutable payload while the lease is held;
5. only then expose the internal payload path to Context-Fabric load logic.

Validation before the use lease is only a fast preflight. The trust decision is the validation performed after lease acquisition so removal/replacement cannot race the accepted payload.

## Catalog boundary

A managed artifact is not a canonical upstream resource and must not be inserted into `Catalog` or `registry/resources.yaml`.

The service should construct an internal prepared-load descriptor directly from the validated artifact. It may reuse `PreparedCorpus` or introduce a small sibling type if doing so avoids lying about `resource_id`, `relative_path` or `source_revision` semantics.

Public provenance should identify at least:

- artifact ID;
- managed-artifact kind/disposition (`one-shot` or `reusable` as observed in receipt);
- producer plugin ID + immutable ref/version;
- materializer ID;
- output format;
- privacy-bounded source identity/digest;
- verified execution identity and cacheability attestation/disposition when present;
- artifact receipt/schema version;
- local-only redistribution policy.

It must not expose the internal store path, original user-local source path or basename.

## Logical name

The loaded corpus needs a stable process-local logical name that cannot collide with canonical catalog loads.

Use a reserved managed-artifact namespace derived only from validated artifact ID, e.g. conceptually `managed-artifact:<artifact_id>` (exact delimiter may follow existing loader constraints). Do not derive the logical name from user filenames or plugin/materializer display names.

Repeated load of the same artifact logical name follows existing replacement semantics: acquire/validate a new use lease, complete compile/load, install the new lease, then release the previous lease. A failed replacement keeps the previous loaded corpus + lease.

## `.cfm` ownership and integrity boundary

#99 owns immutable materializer payload integrity and rejects materializer-produced top-level `.cfm` at publication. After publication, Context-Fabric owns `.cfm/` as mutable derived compile state.

#100 must therefore:

- validate the immutable non-`.cfm` payload before load under the shared use lease;
- use the existing cold-load supervisor/marker semantics for `.cfm` rather than adding `.cfm` bytes to the #99 artifact identity;
- acquire the managed artifact compile lock (not canonical `GitStore.compile_lock`) before mutating/rebuilding `.cfm`;
- recheck the warm marker after compile-lock acquisition;
- retain the shared use lease across compilation and loaded lifetime;
- never treat `.cfm` presence alone as proof that immutable payload is valid.

## Existing service logic that should be reused

Do not duplicate the mature cold-load machinery. Refactor only as needed so both canonical `PreparedCorpus` and validated managed-artifact descriptors can flow through the same:

- source byte budget calculation;
- cold compile supervisor;
- completion-marker check/cleanup;
- loader invocation;
- loaded-name replacement/unload lifecycle;
- active load reporting/cancellation.

The lock provider differs:

- canonical resource: existing `GitStore` cache lease + `GitStore.compile_lock(path)`;
- managed artifact: #99 shared artifact-use lease + artifact-ID compile lock.

A small internal load-handle/protocol abstraction is preferable to branching the entire load function twice.

## Feature selection and modules

`features` passes through to `CorpusManager.load` unchanged as today.

Registered Context-Fabric feature modules are catalog/upstream objects tied to canonical parent corpus versions. They must **not** be automatically composable onto arbitrary managed artifacts in #100. `modules` is rejected/not accepted on the artifact load surface unless a later reviewed ontology/module-compatibility design defines safe binding.

## MCP/API shape

Add a separate managed-artifact surface rather than overloading `load_corpus(resource_id=...)` and making one string namespace ambiguous.

Candidate service methods:

- `describe_managed_artifact(artifact_id)` — validate and return privacy-bounded descriptor;
- `load_managed_artifact(artifact_id, features=None, max_compile_gb=None, max_compile_minutes=None)`;
- existing `unload_corpus(logical_name)` can remain the common unload surface if logical names are collision-safe;
- cache/status may expose loaded managed artifacts by artifact ID without internal path.

Candidate MCP tools mirror the first two methods. Exact names must be frozen by RED tests and update the existing exact-tool-set contract deliberately.

Do not expose `payload_path`, `load_path`, or generic local-path arguments.

## Failure semantics

Fail before `CorpusManager.load` on:

- malformed/unknown artifact ID;
- unsafe/symlinked store/object/receipt/payload path;
- unsupported receipt schema;
- receipt semantic mismatch;
- immutable payload manifest/hash mismatch;
- required output missing;
- output format other than supported Text-Fabric;
- exclusive removal winning before shared use lease acquisition;
- failure to acquire the use/compile lock within bounded policy;
- cold compile failure/timeout/budget violation.

No failure path runs a materializer, installs/repairs a plugin, fetches source data, mutates the catalog, or silently deletes a bad artifact.

## CI/runtime scope

Synthetic Text-Fabric artifacts only. No Burns-derived source/output may be committed or uploaded.

Required runtime evidence should cover:

- unit cross-contract producer→consumer verification;
- real small Text-Fabric load/query through `cfabric-mcp==0.1.7`;
- Linux/macOS/Windows packaging/startup where the new packaged module/tool surface changes launch behavior;
- cross-process use/compile lock behavior from #99;
- canonical resource load regressions unchanged.

## Rejected alternatives

1. **Import Agora repository `scripts/` from the plugin** — non-portable checkout coupling.
2. **Add managed artifacts as fake catalog resources** — lies about upstream/repository semantics and contaminates canonical discovery.
3. **Accept a local filesystem path** — bypasses Agora artifact receipt/integrity/lease authority.
4. **Create a new shared PyPI package now** — lifecycle/versioning cost exceeds the small stable receipt-consumer contract and is not required for #100.
5. **Keep compile lock for the whole loaded lifetime** — over-serializes readers and still conflates mutation with use lifetime.
6. **Trust producer validation without consumer revalidation** — leaves a race/tamper window between publication/description and actual load.

## Conclusion

#100 should add a packaged Context-Fabric consumer for #99's versioned managed-artifact contract. It resolves only artifact IDs under an internally configured store root, acquires a shared use lease, independently revalidates receipt + immutable payload under that lease, reuses the existing cold-load/loader lifecycle with an artifact-ID compile lock, and keeps the lease until unload. The canonical catalog and GitStore path authority remain unchanged.
