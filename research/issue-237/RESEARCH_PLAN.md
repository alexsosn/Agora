# #237 — CTC-TF managed CUC Burns registration

## Research: upstream and real code/data gates (2026-10-11)

- Upstream `alexsosn/CTC-TF` merged PR #122 at master `f58b162197ad8f113b7cd6fc0088ae5dd39a096d` (PR head `c832e2e7f53bb5defc43e94219b167c78feaabc1`). Its exact PR head passed six relevant GitHub Actions workflows: Tests; reviewed CUC index; appendix concordance; CFM module contract; reviewed CUC native feature module; real Burns Workbooks acceptance.
- Actual root `agora.materializer.json`: plugin ID **`cuc-burns`**, version `0.3.0`, producer ID **`cuc-burns-csv`**; `user-local` directory input and `*/*.csv` required paths; parent `cuc` TF `0.2.8` requiring `otype.tf`, `oslots.tf`, `otext.tf`; `python-module` **`ugarit_context_parsing.agora_adapter`**, argument placeholders source/parent/output; `network: deny`; feature-only TF output and mandatory `burns-feature-module-report.json`. Upstream adapter bridges native absent-output requirement to Agora's existing precreated empty stage; it verifies no symlinks/warp changes. Confirmed by upstream `tests/test_agora_parent_manifest.py` and live OS sandbox acceptance.
- Agora canonical `cuc` points at immutable `DT-UCPH/cuc@0408967b1808c1f22c69e299d302b1e7b5e26354`, TF `0.2.8`. The preexisting `cuc-burns` feature module defines exactly this `parent-base` dependency; upstream converter's later CUC commit uses a byte-identical TF tree as documented in Agora's registry.
- Agora #207/#208/#209/#218/#220 have already merged: typed parent resolution and read-only OS sandbox, host receipt/provenance, cache lease, bundled non-injectable resolver, explicit-by-ID module publication, catalog-bound immutable `acquisition.materializer` authorization. Context-Fabric's `local-module` strategy reads the resulting file store and snapshots it; no producer code belongs in Agora.
- Data restrictions: CTC/Burns source and resulting annotation content are **local and not redistributed** (CC BY-NC-ND 2.5 as currently recorded by Agora); converter software is MIT. Explicit install trust `explicit-code-execution`, never auto-approve.

## Plan and TDD

1. Add/modify focused tests **RED before registration** asserting the new registered producer exact SHA/ID/version/manifest/execution trust/disabled release tracking, and `cuc-burns` bundled resource catalog pin (`acquisition.strategy=local-module`, `materializer.plugin=cuc-burns`, `materializer.id=cuc-burns-csv`, unchanged immutable `parent-base` revision); assert no legacy `convert` entries.
2. Replace the now-stale assertion that canonical `cuc-burns` has *no* producer with a refusal-before-acquisition test on an **uninstalled** producer, retaining fail-closed behavior.
3. GREEN minimal metadata-only changes to `registry/materializers.yaml` and both mirrored `registry/feature-modules.yaml` and `plugins/context-fabric/resources/feature-modules.yaml`. Pin exact master commit above and disable release tracking until upstream release, no corpus data or source artifact redistribution.
4. Run full registered schema/registry/Context-Fabric checks, foundation matrix, and a real CUC+Burns registered smoke. If producer's input ZIP/CSV cannot be reproduced legally, leave full native consumer integration as an explicit remaining gate instead of substituting fixture-only evidence.
5. Independent adversarial review rooted in exact real code, manifest and CI logs; merge only after exact-head green and corrected findings.

## Out of scope

No new package-manager abstraction, auto-install/execute without approval, multi-parent solver, CUC node changes, or discontinued standalone Burns `convert`. Do not close Agora #135 from registration alone; the real one-command Burns data → joint CUC/TF load/search and shared-parent deduplication acceptance must still be verified.
