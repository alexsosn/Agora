# Design/plan: materializer output composition metadata (#134)

## Preconditions

Research: `wiki/backlog/P1-research-materializer-output-composition-134.md`.
Base at branch creation: `95ee1e6f6181cb36f0244d636665c2ad8013791d`.

## 1. Preserve RED

Add focused tests around the existing `scripts.agora_materialize` harness before changing production schema/runtime:

- a `feature-module` output declaration with parent + compatibility is accepted;
- standalone output without composition remains accepted;
- malformed/partial composition is rejected by schema;
- non-feature composition kind is rejected rather than silently accepted;
- successful materialization copies the exact validated composition object into Agora's reserved provenance receipt.

The expected baseline failure is schema rejection because `output` currently has `additionalProperties: false` and no `composition` property.

## 2. GREEN schema

Extend only `$defs.materializer.properties.output` in `registry/schema/materializer-plugin.schema.json` with optional `composition`.

Composition v1:

- `additionalProperties: false`;
- required `kind`, `parent`, `compatibility`;
- `kind` constant `feature-module`;
- parent matches canonical resource-id lexical shape;
- compatibility requires non-empty unique opaque `parent_versions` strings.

Do not change schema version: the field is optional and existing manifests remain valid.

## 3. GREEN runtime provenance

In `scripts/agora_materialize.py`, construct output provenance from the validated output spec:

- always retain `format`;
- when `composition` exists, deep-copy it into provenance before `_write_provenance`.

Do not alter acquisition, sandbox commands, output path validation, transaction semantics, or canonical resource registries.

## 4. Regression tests

Run the focused tests and full repository suite/workflows. Existing standalone Burns/Pseudepigrapha materializers must remain valid.

## 5. Independent adversarial review

Freeze the exact final head and independently challenge:

- whether partial/malformed composition can pass;
- whether versions are incorrectly treated as SemVer;
- whether producer output can forge the trusted composition declaration;
- whether the change accidentally creates dependency resolution/lifecycle semantics;
- whether standalone manifests or required-path/sandbox guarantees regress;
- whether any canonical resource is fabricated for a local product;
- whether downstream #99/#100 can consume the receipt metadata without reinterpretation.

Merge only after exact-head CI and a commit-anchored logically independent review have no blockers.
