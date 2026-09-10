# Research: trusted parent-resource inputs for feature-module materializers (#135)

## Status and reviewed base

This research is refreshed after #134 merged as `4ebd63f168993a2e7667cd5c464efd0109b7fde8`.

#134 established one authoritative declarative composition source in a materializer output:

```json
"output": {
  "format": "text-fabric",
  "composition": {
    "kind": "feature-module",
    "parent": "cuc",
    "compatibility": {"parent_versions": ["0.2.8"]}
  }
}
```

The host preserves that declaration in `agora-materialization.json`, but execution still has only `{source}`, `{output}`, and `{source_revision}` placeholders. Therefore a converter that must inspect its parent corpus cannot yet consume the declared parent.

## Problem boundary

A Burns feature-module execution has two distinct trust domains:

1. user-local Burns Workbooks, validated as private source input;
2. a canonical CUC corpus selected/prepared by Agora at an exact Text-Fabric version and immutable source revision, mounted read-only for alignment.

`acquisition` is fallback acquisition for the one logical materializer source. It is not a simultaneous multi-input model. `materialize_registered()` verifies the installed converter runtime and delegates to the low-level host with one source path. The low-level host resolves no canonical corpus resources and should stay that way.

Managed artifacts (#99), managed-artifact loading (#100), and end-to-end composition (#101) happen after or around execution; they do not provide the missing second read-only execution input.

## Existing machinery to reuse

The Context-Fabric provider path already resolves/prepares canonical Text-Fabric resources with the information needed for a trusted parent binding:

- canonical resource ID;
- selected Text-Fabric version;
- exact immutable source revision;
- resolved local TF directory.

That resolver is the correct owner of canonical corpus acquisition. The low-level materializer host must not import Context-Fabric plugin code or grow a duplicate Git/resource resolver.

The materializer execution layer already owns complementary invariants:

- registered runtime integrity is verified before execution;
- manifest validation defines the execution/output contract;
- network is denied when required by the materializer;
- source is read-only in the sandbox;
- output is the writable payload root;
- reserved Agora provenance is host-owned, not converter-owned.

## Architecture decision

Separate resolution from execution.

1. A higher-level trusted orchestrator resolves/prepares the canonical parent corpus.
2. It creates an immutable `ParentResourceBinding` containing resource ID, version, immutable source revision, and resolved local path.
3. The registered runner validates this binding against the already-validated `output.composition` declaration before converter execution.
4. The low-level host receives the validated binding, exposes a dedicated `{parent}` placeholder, and mounts the parent separately read-only.
5. Host provenance records only immutable parent identity, never the absolute local parent path.

This avoids two rejected designs:

- **Bundle CUC into the private Burns source tree:** destroys ownership/provenance boundaries and makes the source identity falsely include the parent corpus.
- **Let the converter fetch CUC itself:** violates `network: deny`, bypasses canonical resource verification, and duplicates Agora/Context-Fabric acquisition semantics.

## Manifest contract

Do not add a second `parent_resource` manifest declaration. `output.composition` from #134 remains the single source of truth.

A feature-module materializer may use `{parent}` in `execution.args`. `{parent}` is invalid without `output.composition.kind = feature-module`.

At execution time, when `{parent}` is used, a trusted binding is mandatory and must satisfy:

- `binding.resource_id == output.composition.parent`;
- `binding.version` is one of `output.composition.compatibility.parent_versions`;
- `binding.source_revision` is immutable under the currently supported Git-backed resource model (full 40- or 64-hex digest; no branch/tag/ref name);
- `binding.path` exists and is a directory;
- the parent path is not inferred from user input or from generated files.

A binding supplied to a standalone materializer must fail rather than be silently ignored. A feature-module declaration that does not use `{parent}` remains schema-valid because some derived modules may not need to inspect the parent bytes; Burns does use it.

## Typed binding

A narrow immutable value object is sufficient at the runner/host boundary:

```python
@dataclass(frozen=True)
class ParentResourceBinding:
    resource_id: str
    version: str
    source_revision: str
    path: Path
```

The binding is not a dependency object or resolver result cache. It is a validated execution capability produced by trusted orchestration.

## Placeholder rendering

The current `_render_args()` replacement table is exact and fail-closed for unresolved braces. Extend it with `{parent}` only when a parent binding is actually present.

Do not substitute a host path into a sandboxed command. The sandbox builders must render the parent placeholder to a dedicated sandbox-visible path. In unsandboxed explicit development mode, the resolved host parent path may be used directly.

## Sandbox contract

When a parent binding is present:

- private source remains a distinct read-only mount;
- canonical parent is a second distinct read-only mount;
- output remains the only writable payload mount;
- Linux bubblewrap uses a stable parent mount such as `/agora-parent`;
- macOS sandbox-exec includes the parent in readable roots but not writable roots;
- `{parent}` resolves to the sandbox-visible path under required sandboxing;
- source and parent must not be accepted as the output path or inside the staging output tree;
- network policy is unchanged.

Host-path overlap between source and parent is not itself a trust escalation if both are read-only, but aliasing either to the writable output must fail before execution.

## Provenance

The reserved receipt should add a separate object:

```json
"parent": {
  "resource_id": "cuc",
  "version": "0.2.8",
  "source_revision": "<immutable revision>"
}
```

Do not persist the absolute path. Keep this identity separate from:

- private-source provenance;
- output `composition` declaration;
- plugin/runtime identity.

This gives #99 enough immutable parent identity to include in later managed-artifact/cache identity without conflating it with private source bytes.

## Registered-runner boundary

`materialize_registered()` may accept an already-resolved `ParentResourceBinding` and forward it under the same installed-runtime lock used for execution. It must not fetch/install/repair the parent while holding that lock.

This ticket may expose the typed binding and forwarding seam. It does **not** implement the higher-level Context-Fabric resolver adapter or automatic parent acquisition; those remain orchestration work for #101 / resource-lifecycle design.

## Compatibility and failure ordering

Fail before converter execution for:

- `{parent}` with no feature-module composition;
- `{parent}` with no trusted binding;
- binding resource mismatch;
- binding version mismatch;
- non-immutable revision;
- missing/non-directory parent path;
- parent binding supplied to a standalone materializer;
- parent aliasing the writable staging/final output boundary.

The low-level host must not reinterpret `parent_versions` as SemVer. Values remain opaque exact strings.

## Backward compatibility

Existing one-source materializers must retain their current manifest validity, command rendering, sandbox topology, provenance shape, and registered-runner behavior when no parent binding is supplied.

## Security / adversarial observations

- Parent identity must come from the trusted binding, not basename/path conventions.
- Generated TF metadata may independently claim CUC compatibility, but it is not authoritative for the host binding.
- `output.composition` is declarative intent; the binding is observed execution identity. Both are needed and must agree.
- Parent path must never be written into public/materialization provenance because canonical caches can contain user-specific absolute paths.
- The parent must be mounted read-only even if the underlying host directory is writable by the user.
- No implicit network fallback or parent auto-install belongs in this ticket.

## Burns consequence

After #135, the Burns manifest can truthfully invoke its already-merged public module CLI approximately as:

```text
ugarit_context_parsing.cli module {source} --input-format csv --cuc {parent} --output {output}
```

with Workbooks as the private source and exact reviewed CUC as a separately resolved parent. The converter remains network-denied and does not copy the CUC warp into the Burns module.

## Scope exclusions

This ticket does not implement dependency solving, autoremove, parent acquisition, canonical-resource mutation, managed-artifact caching, Context-Fabric loading, or end-to-end Burns registration. It provides the generic trusted execution seam required by those layers.