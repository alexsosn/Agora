# Research amendment: materializer cacheability and local provenance privacy (#97 / #103)

## Adversarial finding

Independent review of the proposed managed-artifact cache found an unstated semantic assumption: the current materializer-plugin v1 schema has no determinism/cacheability declaration. It defines acquisition, input, execution and output only.

A request-identity cache (`source + execution identity + materializer + options`) is therefore unsafe as a generic default. For a nondeterministic converter, returning a previously generated artifact changes direct-execution semantics even when every known identity input matches.

## Decision

Managed artifact **reuse** must fail closed unless the materializer has an explicit reviewed cacheability contract. Direct registered execution remains available regardless of cacheability.

Issue #103 owns the independent research/design/TDD work for that contract. #99 may implement artifact identity, receipts, validation and transactional storage only after #103 defines how a materializer becomes reusable.

Until #103 lands:

- `unknown` / legacy cacheability means execute normally but do not memoize/reuse by request identity;
- no implementation may infer determinism from `network: deny`, immutable plugin source, Text-Fabric output, converter name, or successful repeated tests alone;
- the Burns and Pseudepigrapha materializers need explicit evidence/disposition under the selected contract before #101 claims cache reuse.

The eventual cache identity must bind the cacheability policy/attestation version (or equivalent reviewed metadata) so changing that policy cannot leave stale reusable entries silently valid.

## Byte determinism versus semantic determinism

The current materialization host writes `agora-materialization.json` with a creation timestamp. Text-Fabric or converter-owned reports may likewise contain creation metadata. Therefore an acceptable cacheability contract should not accidentally require bit-identical whole artifact trees unless the materializer explicitly promises that.

#103 must distinguish at least:

- deterministic scholarly/content output under declared inputs;
- allowed non-semantic provenance/timestamp variation;
- genuinely stochastic/external-state-dependent output that must not be request-memoized.

Artifact receipts still bind the exact output tree hash of the artifact that was actually published; that is integrity evidence, not proof that a fresh rerun would produce identical bytes.

## Local source privacy finding

`prepare_user_source()` currently stores the local source directory basename as `source.name` in Agora materialization provenance. It does not store the absolute local source path, but a basename can still contain user-sensitive project/document naming.

Decision for #100/#101 public projections:

- managed receipts may retain the local provenance needed for local audit, subject to normal local file protections;
- MCP/public tool responses must not expose the local source path **or basename by default**;
- public provenance should expose content identity/type/revision and approved converter identity, with any human-readable local source label requiring an explicit future design rather than accidental passthrough.

## Updated dependency

```text
#95 registered run-by-ID
          |
          v
#103 reviewed cacheability semantics
          |
          v
#99 managed artifact cache/receipt
          |
          v
#100 Context-Fabric managed-artifact load
          |
          v
#101 end-to-end composition + Burns acceptance
```

This amendment is blocking for the research/design review: #97 must not be finalized while generic cache reuse still relies on undocumented determinism.
