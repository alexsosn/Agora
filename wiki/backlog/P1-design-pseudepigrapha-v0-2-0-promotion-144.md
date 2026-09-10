# Design: Pseudepigrapha-TF v0.2.0 promotion (#144)

Research: [`P1-research-pseudepigrapha-v0-2-0-promotion-144.md`](P1-research-pseudepigrapha-v0-2-0-promotion-144.md).

## Contract

Promote only Agora's canonical stable materializer identity:

- version `0.2.0`;
- exact commit `317e960e05ca7f36f35a11fcf567285312951095`;
- repository remains `alexsosn/Pseudepigrapha-TF`;
- release tracking remains `github-releases` / `stable` / prefix `v`;
- ordered materializer IDs remain exactly `[ocp-text-fabric]`.

No upstream converter, corpus semantic, adapter, schema, resolver, or marketplace-generation behavior changes are in scope.

## TDD gates

### RED

Before registry mutation, a Foundation-discovered `unittest` regression must require the exact v0.2.0 identity above and fail on the current v0.1.0 pin for that reason only. Repository structure and unrelated suites must remain green.

### GREEN

Update only the canonical `registry/materializers.yaml` `version` and `ref` fields for `pseudepigrapha-tf`, unless live evidence demonstrates a separate Agora-owned incompatibility. Do not hand-edit generated marketplace artifacts.

## Verification

After GREEN:

1. run canonical registry validation and generation freshness checks;
2. run release-selection/binding regressions;
3. confirm the public `v0.2.0` annotated tag still resolves to the exact reviewed commit;
4. exercise Agora's registered materializer install/materialization smoke against the promoted identity;
5. run full exact-head Foundation and applicable materializer/sandbox integration lanes;
6. perform a fresh logically independent exact-head adversarial review before merge.

A failed install/materialization or binding check blocks promotion; no fallback to the older release is performed inside this PR.
