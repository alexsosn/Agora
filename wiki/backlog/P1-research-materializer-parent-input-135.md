# Research: trusted parent-resource inputs for feature-module materializers (#135)

## Problem boundary

A Burns feature-module execution has two distinct trust domains:

1. user-local Burns Workbooks, which Agora may validate as private source input;
2. a canonical CUC corpus selected by Agora at an exact Text-Fabric version/revision and mounted read-only for the converter.

The current materializer host has only one logical `{source}`. Its `acquisition` list is fallback acquisition for that one source, not simultaneous named inputs. `materialize_registered()` verifies the installed converter runtime and then delegates to `host.materialize(..., source=...)`; it has no parent/resource binding.

Issue #97 and the managed-artifact work (#99/#100) operate after materializer execution. They do not solve how a converter receives a trusted parent during execution.

## Existing machinery to reuse

The Context-Fabric resolver already represents a prepared canonical corpus with:

- resource ID;
- selected Text-Fabric version;
- exact source revision;
- resolved local path.

It also validates configured `tf_path`/requested version instead of silently selecting a different dataset. This is the right trust model for the CUC parent, but the core materializer host should not import the Context-Fabric plugin or create a second Git/resource resolver.

The materializer execution layer already owns the important security invariants:

- converter runtime identity is verified before execution;
- network is denied by manifest contract;
- source is read-only in the sandbox;
- output is the writable payload root;
- reserved Agora provenance is written by the host, not the converter.

## Architecture choice

Do **not** make the low-level host resolve canonical resources itself. Instead separate resolution from execution:

1. a higher-level trusted orchestrator resolves a canonical parent corpus using Agora's existing resource/Context-Fabric resolver boundary;
2. it passes a typed immutable `ParentResourceBinding` to the registered-materializer runner;
3. the runner validates that binding against the validated materializer manifest and forwards only the resolved local path + immutable identity to the low-level host;
4. the host mounts the parent read-only and exposes one dedicated `{parent}` placeholder to the converter;
5. provenance records the parent identity separately from source provenance.

This avoids both undesirable alternatives:

- bundling CUC under the private Burns source tree, which destroys provenance and ownership boundaries;
- teaching each materializer to fetch its own dependency, which violates `network: deny` and bypasses Agora resource trust.

## Manifest contract

After #134 lands, feature-module output composition already declares the semantic relationship:

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

#135 should reuse this declaration as the required parent input contract rather than duplicate parent/version metadata in a second manifest section.

A feature-module materializer may use `{parent}` in `execution.args`; ordinary materializers may not. At execution time the trusted binding must satisfy:

- `resource_id == output.composition.parent`;
- selected `version` is one of `compatibility.parent_versions`;
- `source_revision` is immutable;
- `path` is an existing prepared corpus root supplied by the trusted orchestrator.

No arbitrary `--parent /some/path` should be treated as a trusted registered execution. A low-level/dev API may accept a path only together with an explicit binding object; identity cannot be inferred from the path string.

## Proposed binding

A narrow immutable value object is sufficient:

```python
@dataclass(frozen=True)
class ParentResourceBinding:
    resource_id: str
    version: str
    source_revision: str
    path: Path
```

The binding is not a dependency solver. It represents the output of trusted resolution.

## Sandbox contract

When a parent is present:

- private source remains separately mounted read-only;
- parent is mounted separately read-only;
- output remains the only writable payload mount;
- `{parent}` expands to the sandbox-visible parent mount, never the host path;
- converter network remains denied;
- source and parent must not overlap output or each other in a way that weakens containment.

This should extend the existing mount-plan abstraction rather than special-case Burns.

## Provenance and identity

`agora-materialization.json` should preserve parent provenance separately, e.g.:

```json
"parent": {
  "resource_id": "cuc",
  "version": "0.2.8",
  "source_revision": "<immutable commit>"
}
```

The parent filesystem path must not be persisted as identity. The receipt must contain enough immutable parent identity for #99 cache/request identity to include it later without conflating it with private-source identity.

The host should copy the trusted binding identity into provenance; converter output must not be authoritative for it.

## Compatibility/fail-closed rules

- Feature-module composition + `{parent}` but no trusted parent binding: fail before converter execution.
- Binding supplied but resource ID/version disagrees with output composition: fail before execution.
- Binding supplied to an ordinary standalone materializer that does not declare feature-module composition: fail rather than silently ignore it.
- `{parent}` in args without feature-module composition: schema-invalid.
- Feature-module materializer that does not actually need the parent path may omit `{parent}` only if downstream semantics explicitly allow that; Burns requires it, so its manifest will include it.
- Parent revision must be immutable (40/64 hex under the current Git-backed resource model); no branch/tag string in a trusted binding.

## Scope boundaries

#135 does not:

- implement dependency solving or autoremove;
- automatically install a missing parent;
- make the low-level materializer host depend on Context-Fabric plugin code;
- make generated local modules canonical Git resources;
- change #97/#99/#100 managed-output lifecycle;
- loosen network or sandbox policy.

## Burns consequence

With #134 + #135, Burns can truthfully register a network-denied feature-module materializer that receives user-local Workbooks as `{source}` and the exact reviewed CUC 0.2.8 corpus as `{parent}`. The producer can run its public `module ... --cuc {parent}` CLI without copying CUC into Burns or letting the converter fetch anything itself.

That is the missing execution contract required before `ugarit-context-parsing#29` can complete its Agora migration.
