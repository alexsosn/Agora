# Design review amendment: disjoint cacheability states and transplant-resistant attestation identity (#103)

## Independent review findings

The parent design correctly makes reusable cacheability exact-plugin-ref and exact-managed-execution-identity scoped, but two schema/identity details must be frozen before production work.

## 1. `non-reusable` is a terminal disjoint state

The schema must not use one permissive object shape where `mode: non-reusable` may also carry stale `reviewed_ref`, `reviewed_environments`, or evidence fields.

That would be semantically ambiguous in reviews and generated tooling: an explicitly non-reusable entry could still look like a formerly approved reusable attestation.

Use disjoint shapes (for example JSON Schema `oneOf`):

```yaml
# terminal deny-reuse state
mode: non-reusable
```

with no additional cacheability fields, versus:

```yaml
mode: reusable
reviewed_ref: <40-hex plugin commit>
reviewed_environments:
  - execution_identity_sha256: <64-hex>
    evidence: [...]
```

`additionalProperties: false` applies to both shapes. RED tests must prove that `non-reusable` plus any `reviewed_ref`, environment, or evidence field is rejected rather than ignored.

Absence remains the distinct legacy/unknown state and is not serialized as a fake `mode: unknown` unless later design explicitly requires that representation.

## 2. Attestation identity binds its registration coordinates

The deterministic attestation digest returned to #99 must not hash only the reusable policy payload/evidence object. It must be domain-separated and bind at least:

- attestation schema/version;
- registered plugin ID;
- registered materializer ID;
- cacheability mode;
- reviewed plugin ref;
- the exact selected reviewed execution identity;
- the exact evidence objects authorizing that selected environment, canonically ordered/serialized.

This prevents a byte-identical reviewed-environment/evidence object from being transplanted between two materializer IDs or plugins and retaining the same attestation identity.

The policy helper may keep the full configured list of reviewed environments in registry validation, but the **effective reusable attestation identity for a request** should identify the selected current execution environment, not imply that one request is authorized by all platform environments at once.

RED tests must prove:

- same evidence under another plugin ID changes the digest;
- same evidence under another materializer ID changes the digest;
- selecting a different reviewed `execution_identity_sha256` changes the digest;
- evidence ordering is either schema-fixed or canonically normalized so semantically identical authored ordering cannot produce accidental distinct identities;
- stale/unmatched policy returns no reusable attestation identity at all.

## Implementation boundary

These requirements do not make cacheability a direct-execution precondition and do not implement the artifact cache. They only remove ambiguity in the reviewed policy object that #99 will later consume.

They are blocking review requirements for #103 implementation: do not merge a schema/helper that permits review-looking fields on `non-reusable` entries or produces an attestation digest that is not bound to plugin/materializer coordinates.
