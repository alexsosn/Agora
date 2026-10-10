# Agora #233 — pin reviewed Coptic↔LXX native module release

## Research (2026-10-10)
- Canonical registry still points at Coptic Git `60fec735dd6ef9aefe2cfb9e6459e9f7f15924e7`, predating merged Coptic bilateral Coptic→CenterBLC/LXX native TF module support and the source-byte SHA integrity repair.
- Reviewed final merged [CopticScriptorium-TF #87](https://github.com/alexsosn/CopticScriptorium-TF/pull/87) at `3cde20ec41efb1cacf1710643f01f924f11cbf0b` incorporates:
  - #83: actual pinned Coptic 2,628 TT documents / 2,394,354 word slots to two native TF wefts for 21,120 distinct **Greek verse reference address candidates** (not textual equivalence); genuine full run 38080479109 passed.
  - #85: both legacy and streaming API demand exact native parent Coptic `document` `source_sha256` match, avoiding false joins of different source-byte documents.
  - #87: researcher guide and proven 3-file sparse writer CI.
- Exact generated corpus/literal license data still excluded from distribution. `agora.materializer.json` remains `copticscriptorium-tf` plugin v0.1.0 with one **base TT→TF converter** `copticscriptorium-text-fabric`; upstream Coptic source unchanged `@3ac067f1709a0012daf39ea8da2fac79980176a5` with `/*/*_TT/**`, `/*/*_TT.zip`; code execution requires explicit approval; converter must execute without network under Bubblewrap.
- Important boundary: shipping installable `copticscriptorium_tf.lxx_module` streaming API does **not** mean Agora registered an LXX materializer or verified the full automatic remote source (distinct Agora #205/#214).

## Actual RED failure from canonical registry pin advance

Exact-head PR #234 first CI full registered workflow run `38083800417`, job `114305966267`, failed **before source download**, at "Verify canonical Coptic plugin pin and upstream source contract". Workflow `.github/workflows/coptic-registered-full-source.yml` still asserts the previously canonical `60fec735...` SHA. Both `tests/test_issue214_coptic_full_registered.py` and `tests/live_issue214_full_coptic.py` also hard-code that old SHA; these become stale the moment canonical registry advances. Updating only registry without updating the long-running acceptance contract was an actual error, not a Coptic converter failure.

RED-first improve exact canonical pin matching across all three acceptance surfaces: static contract test should require the new pin in the workflow, and live verifier should bind the new immutable revision before acquisition/execution. Consider a future shared canonical constant loader to avoid this repeated brittle manual pin sync, while preserving explicit pinned CLI/artifact identity checks and avoiding all moving refs.

## RED → plan → implementation → test → review
1. RED-first update canonical registry test expected immutable merged Coptic SHA and require actual installed plugin `copticscriptorium_tf.lxx_module.materialize_lxx_reference_modules_streaming` and `verify_coptic_module_parent` to be callable inside the real registered install GitHub workflow. Old canonical pin and old workflow must fail.
2. Minimal code change: only `registry/materializers.yaml` Coptic `ref`; live workflow validates installed LXX APIs while preserving existing manifest Git source and sparse pattern validation, signed source identity/provenance, required network-denied sandbox and Context-Fabric MCP handoff.
3. Exact-head Github actions: Registered materializer install smoke, Materialization sandbox E2E, Foundation plus associated unit tests. Inspect real job logs for installed source commit and functional native TF/Context-Fabric lifecycle.
4. Independent skeptical review exact source/CI head on software version unchanged, package dependency compatibility, repository pin, trust boundary, provenance/identity checks, and absence of invented Greek textual correspondences before squash merging.

## Acceptance
- [x] Research pinned data and merged releases
- [x] RED-first exact pin/API installation test
- [ ] Minimal registry and installed smoke implementation
- [ ] Real exact-head CI all required green
- [ ] Independent adversarial review of final head and merge
