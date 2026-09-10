# Research: parent-resource inputs for materializers (#135)

## Problem

Agora materializer manifests currently model one primary source plus one output. Execution arguments may interpolate only `{source}`, `{output}`, and `{source_revision}`. That is sufficient for standalone converters but cannot represent a feature-module materializer such as Burns -> CUC, which needs two independent read-only inputs at execution time:

1. a user-local Burns CSV/PDF source;
2. an already-acquired, exact CUC Text-Fabric parent corpus.

The registry already models Text-Fabric feature modules with a logical `parent` resource and `compatibility.parent_versions`, but that relationship is not available to materializer execution.

## Current implementation audit

Baseline: Agora `111d36ec8473a696fe2fec01b46b5e3be4e29218`.

### Manifest / generic host

`registry/schema/materializer-plugin.schema.json`:

- requires one `input` contract and one `acquisition` list;
- permits execution placeholders only for `{source}`, `{output}`, `{source_revision}`;
- has no resource/dependency binding.

`scripts/agora_materialize.py`:

- acquires and validates the primary source itself;
- represents it as `PreparedSource(path, provenance, cleanup_root)`;
- mounts only plugin, source (`/input`) and output in the Linux sandbox;
- grants macOS sandbox read access only to plugin/source/output/work directories;
- renders only the three current placeholders;
- writes provenance for plugin/materializer/source/output/sandbox/manifest;
- stages and atomically publishes output.

The generic host should remain catalog-agnostic. It is a converter execution boundary, not a resource resolver.

### Registered runner

`scripts/agora_materialize_registered.py`:

- resolves only an already-installed plugin;
- holds the plugin runtime lock while rechecking registry/manifest binding and executing;
- explicitly never fetches, installs, or repairs the plugin during execution;
- delegates to `host.materialize(...)` after all trust checks;
- currently has no resource-input resolver or dependency parameter.

This is the correct seam for passing already-resolved resource inputs into the generic host, but not for embedding Context-Fabric Git/catalog mechanics directly.

### Context-Fabric resource resolver

`plugins/context-fabric/src/agora_context_fabric/resolver.py` already has the desired resolved-resource representation:

- `PreparedCorpus.resource_id` — logical registry identity;
- `PreparedCorpus.path` — concrete local Text-Fabric snapshot;
- `PreparedCorpus.version` — selected TF version;
- `PreparedCorpus.source_revision` — resolved immutable Git revision.

`ContextFabricResolver.prepare()` materializes a selected corpus path and records the resolved revision. Feature-module selection already validates `parent` and `parent_versions`.

However ordinary preparation may call `GitStore.ensure_metadata()` and therefore may refresh/fetch. #135's execution-time dependency must instead be **already acquired** and fail closed without network fallback.

The existing GitStore is revision-addressed and has object lease/eviction machinery. Parent-resource execution should reuse those trusted snapshots and hold a read lease for the converter lifetime so cache eviction cannot remove a mounted dependency mid-run.

### Registry state relevant to Burns

`registry/resources.yaml` declares:

- resource id `cuc`;
- kind `corpus`;
- repository `DT-UCPH/cuc`;
- no immutable configured `ref`.

Therefore a manifest declaration such as `resource: cuc` cannot be interpreted as permission to fetch whatever upstream currently points to during materializer execution. The execution binding must resolve an already-present snapshot, select the requested TF version, expose the exact resolved revision, and then run against that immutable local object. Burns itself performs an additional content/fingerprint check against its reviewed CUC base and will fail if the selected bytes are incompatible.

## Dependency-manager comparison

### Homebrew

Homebrew formulae declare dependencies by stable logical formula names. Homebrew resolves them into managed installation prefixes/kegs; build code does not treat arbitrary user paths as dependency identity. Homebrew also distinguishes the active `opt_prefix` from the versioned installed keg. This supports separating **declaration identity** from **resolved local filesystem location**.

Reference: Homebrew Formula Cookbook, dependency and prefix/keg documentation: <https://docs.brew.sh/Formula-Cookbook>.

### Nix

Nix derivations enumerate all store inputs explicitly. A store path is an opaque identifier for exactly one store object, and filesystem exposure is the representation that lets a process read that object. Nix explicitly requires referenced store objects to be declared in the derivation inputs rather than discovered by scanning command strings.

References:

- <https://nix.dev/manual/nix/2.35/store/>
- <https://nix.dev/manual/nix/2.28/store/derivation/>

The transferable design rule is: dependencies are declared separately from command interpolation; resolution establishes immutable identity before process launch; execution receives controlled paths for those resolved inputs.

## Candidate manifest designs

### A. Dedicated `parent_resource`

Example: `"parent_resource": {"resource": "cuc", "version": "0.2.8"}`.

Advantages: very small schema change for Burns.

Problems:

- hard-codes Text-Fabric parent semantics into a generic materializer manifest;
- cannot naturally support multiple resources (lexicon + corpus, model + corpus, alignment table + corpus);
- creates a second dependency concept if future materializers need other inputs.

Rejected as too narrow.

### B. Arbitrary caller-provided dependency paths

Example CLI `--resource parent=/some/path` with `{resource:parent}`.

Advantages: easy host implementation.

Problems:

- path is not trusted resource identity;
- bypasses Agora resource verification/provenance;
- permits arbitrary filesystem injection into the sandbox;
- cannot satisfy exact immutable resource-identity acceptance.

Rejected as the public registered-materializer contract. Explicit low-level host tests may construct `PreparedResourceInput` objects, but callers must not gain a general arbitrary-path trust bypass.

### C. Named registered resource inputs

Example manifest fragment:

```json
"resource_inputs": [
  {
    "name": "parent",
    "resource": "cuc",
    "version": "0.2.8"
  }
]
```

Execution args may then use `{resource:parent}`. Resolution happens before execution and produces a typed immutable binding containing at least name, resource id, version, source revision and local path.

Advantages:

- general enough for future non-parent dependencies;
- preserves logical registry identity;
- multiple resources have deterministic declaration order and unique names;
- host remains catalog-agnostic;
- deterministic sandbox paths can be `/resources/<name>`;
- provenance can record logical identity/revision without exposing host absolute paths;
- existing manifests with no `resource_inputs` remain unchanged.

Selected for v1.

## Proposed trust/runtime model

### Declaration

Add optional `resource_inputs` to each materializer. V1 entries contain:

- `name`: safe logical name (`^[a-z][a-z0-9-]*$`);
- `resource`: existing Agora/Context-Fabric resource id;
- `version`: required Text-Fabric dataset version for v1.

Names must be unique. V1 intentionally supports corpus resources only; feature-module/collection member dependencies need additional selection semantics and should not be guessed into this ticket.

Execution arguments gain `{resource:<name>}`. A placeholder is valid only when `<name>` is declared by that materializer. Undeclared resource placeholders are manifest errors, not runtime empty substitutions.

Do not add arbitrary environment interpolation.

### Resolution

Before converter host invocation, a trusted resolver resolves every declaration from already-acquired Agora-managed Context-Fabric snapshots only. No network/fetch fallback is allowed in this phase.

Each result becomes a `PreparedResourceInput`/equivalent with:

- declared `name`;
- logical `resource_id`;
- selected `version`;
- immutable `source_revision`;
- trusted concrete `path`;
- cache lease/cleanup lifetime as needed.

Resolution is deterministic in declaration order. Failure of any resource prevents host invocation and output publication.

A dedicated cached/offline prepare seam is preferable to using ordinary `ContextFabricResolver.prepare()` under its default freshness policy. It must select an existing revision-addressed snapshot and hold a lease through converter completion.

### Generic host

Extend `host.materialize(...)` with an already-resolved resource-input mapping/sequence. The host:

- never resolves/fetches resources;
- checks declared names exactly match supplied bindings;
- renders `{resource:<name>}` only from supplied trusted bindings;
- Linux: read-only bind each dependency to deterministic `/resources/<name>`;
- macOS: grant read access to each resolved dependency path and render its host path;
- sandbox-off development path: render resolved host paths directly;
- records logical dependency provenance (`name`, `resource`, `version`, immutable revision) but no host absolute path.

Primary source remains `/input`; dependencies are not flattened/copied into it. Output staging/atomicity remains unchanged.

### Registered runner / Context-Fabric bridge

`materialize_registered()` remains responsible for verified plugin identity and runtime lock. It obtains resource bindings via a trusted resolver seam before delegating to the host and holds their leases until host completion.

Avoid importing Context-Fabric catalog/GitStore implementation into the generic host. The integration may live in the registered-runner layer or a small Context-Fabric adapter, but tests must permit injection of a resolver so the trust boundary is explicit.

## Provenance and identity

Resource-input provenance must include logical immutable identity, not path spelling:

```json
"resource_inputs": [
  {
    "name": "parent",
    "resource": "cuc",
    "version": "0.2.8",
    "source_revision": "<immutable sha>"
  }
]
```

Absolute cache paths are local implementation details and should not appear in public provenance.

The newly merged materializer execution-identity v3 describes converter runtime bytes. Resource-input identities are **request/build inputs**, not converter-code identity. They must be available to downstream managed-artifact identity/cacheability work, but should not mutate the installed plugin execution identity merely because a different corpus snapshot is selected.

## TDD boundary

Preserve RED before implementation for:

1. schema accepts optional named `resource_inputs` and `{resource:name}` placeholders;
2. duplicate/unsafe names and undeclared placeholders fail manifest validation;
3. an existing single-source manifest remains valid and executes unchanged;
4. generic host receives only already-resolved bindings and performs no resource acquisition;
5. source and parent are separate paths; Linux command read-only mounts parent at `/resources/parent` and renders that path;
6. sandbox-off and macOS rendering preserve the same logical binding without copying it into source;
7. registered execution resolves each dependency before host invocation and passes exact path/version/revision;
8. dependency-resolution failure prevents converter invocation/output publication and triggers no implicit plugin install/repair or resource fetch;
9. resource leases span converter execution and release on success/failure;
10. provenance binds name/resource/version/revision and excludes absolute dependency paths;
11. deterministic resource declaration/render ordering;
12. a synthetic feature-module contract proves separate source + parent inputs end to end without copyrighted data.

## Risks to challenge in independent review

- accepting a caller-supplied path as trusted resource identity;
- hidden network fetch during dependency resolution;
- cache eviction/TOCTOU after resolution but before/during converter execution;
- sandbox read/write privilege accidentally granted to dependency roots;
- placeholder injection or undeclared names;
- absolute-path privacy leaks in provenance;
- resource identity omitted from future artifact cache keys;
- mutating plugin execution identity with run-specific resource state;
- breaking old one-source manifests or registered-run lock semantics;
- order-dependent output from an unordered dependency mapping;
- over-generalizing v1 to collection members or feature-module dependencies without selection semantics.

## Scope / downstream

#135 should deliver the generic named-resource execution seam needed by Burns. Updating the Burns manifest/Agora registry remains downstream in `alexsosn/ugarit-context-parsing#29`, after #135 is merged and independently reviewed.
