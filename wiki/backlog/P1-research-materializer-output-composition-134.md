# Research: materializer output composition metadata (#134)

## Problem boundary

Agora currently has two separate concepts that are individually sound but cannot yet be joined for a materializer-produced Text-Fabric feature module:

1. canonical `feature-module` resources express a parent corpus and compatible parent versions;
2. materializer manifests express only output format and required paths, while `agora-materialization.json` records only the output format.

Burns now produces a feature-only Text-Fabric module over reviewed CUC 0.2.8 and Context-Fabric can load the ordered base+module locations. Registering that output as an ordinary repository-backed resource would be false: the Burns-derived module is generated locally from user-supplied Workbooks and must remain local-only.

## Existing vocabulary to reuse

`registry/schema/resources.schema.json` defines the semantic precedent for feature modules:

- `kind: feature-module`;
- `parent: <resource-id>`;
- `compatibility.parent_versions: [<version>, ...]`.

The materializer schema should reuse that vocabulary rather than invent a Burns-specific dependency field.

## Existing materializer/runtime boundary

`registry/schema/materializer-plugin.schema.json` currently restricts `output` to:

- `format`;
- `required_paths`.

`scripts/agora_materialize.py` validates the manifest, verifies required paths, then writes reserved `agora-materialization.json`. Its output provenance currently contains only `format`.

This gives a narrow implementation seam: declarative composition belongs inside the materializer output declaration and should be copied into the trusted Agora provenance after output validation.

## Chosen contract

Add an optional `output.composition` object with exactly this v1 shape:

```json
{
  "kind": "feature-module",
  "parent": "cuc",
  "compatibility": {
    "parent_versions": ["0.2.8"]
  }
}
```

Constraints:

- `kind` is a constant `feature-module` in this slice; do not pre-design arbitrary composition kinds.
- `parent` uses the existing resource-id lexical contract.
- `compatibility.parent_versions` is non-empty, unique, and treats versions as opaque non-empty strings; no SemVer assumption.
- the object is all-or-nothing: a feature-module composition declaration requires kind, parent and compatibility.
- ordinary standalone materializers omit `composition` and remain valid unchanged.

## Runtime provenance

When present, Agora copies the validated composition object unchanged into:

```json
"output": {
  "format": "text-fabric",
  "composition": { ... }
}
```

The provenance copy is descriptive and compatibility-bearing only. It does **not** install the parent, resolve dependencies, mutate canonical resources, load Context-Fabric, or create lifecycle/autoremove edges. Those behaviors belong to the ongoing #97/#99/#100/#125 architecture.

## Security/trust boundary

The producer cannot self-authenticate composition via generated files: the authoritative declaration comes from the already-trusted materializer manifest, and Agora writes it into its reserved provenance file only after validating output. Existing reserved-path protection, sandboxing, required-path validation and transactional publication remain unchanged.

## Burns consequence

After this lands, `ugarit-context-parsing` can truthfully declare its local module output as a feature module compatible with `cuc` 0.2.8 without pretending the generated Burns module is a Git-backed canonical corpus and without copying the CUC warp.
