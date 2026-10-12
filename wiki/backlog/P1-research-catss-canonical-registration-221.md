# Agora #221: research — CATSS standalone canonical producer registration

## Verified upstream executable

CATSS-TF [PR #119](https://github.com/alexsosn/CATSS-TF/pull/119) squash-merged as immutable `3ee63c4c054960b816b14496815815153e5e543d` after independently adversarial-reviewed, exact-head 5/5 CI ([38231819506](https://github.com/alexsosn/CATSS-TF/actions/runs/38231819506)), 530 Python tests per 3.11/3.12/3.13, and opt-in real 46-file CATSS data run. Native and Agora-adapter 69 output files matched SHA-256 independently; 349,670 alignment slots and 6,218 scalar reference nodes reloaded as Text-Fabric with zero ignored source diagnostic findings.

The merged root `agora.materializer.json` advertises **exactly one** producer `catss-canonical`, `plugin.id=catss-tf`, `plugin.version=0.1.0`, `repository=alexsosn/CATSS-TF`, `input.required_globs=['*.par']`, `acquisition=user-local`, no symlinks, `execution.module=catss_tf.agora_adapter`, `args=['{source}','--output','{output}']`, `execution.network=deny`, `output.format=text-fabric` with native standalone warp files plus alignment-id feature. The host pre-creates a real empty staging directory. The adapter uses native `materialize_corpus` in an absent private child and publishes no-replace hardlinks; it fails closed on source mismatch/unknown sigla. No `--allow` exceptions in registered path. CATSS-TF package code is MIT but CCAT/CATSS source data have separate, restricted/unclear redistribution permissions: **user supplies own local licensed input**; neither the registry nor tests may fetch/rehost CATSS corpora.

## Actual Agora contracts

Read actual canonical `registry/materializers.yaml`, `registry/schema/materializers.schema.json`, `scripts/agora_install_materializer.py`, `scripts/agora_materialize_registered.py`, `scripts/agora_materialize.py`, and full prior registered Coptic/Burns examples. Agora pins external producers to immutable full SHA, `version` and explicit third-party Python code-execution approval; `release_tracking: disabled` is needed until a GitHub Release demonstrably ships the merged executable. A managed install receipt records pinned source/runtime hashes. Registered runner invokes the materializer only after explicit install/approval and uses `--sandbox required` (bubblewrap) and `--source` to pass a *synthetic* local source. Agora writes `agora-materialization.json` itself after the plugin returns; it does not automatically put produced TF into Context-Fabric.

## Scope and fail-closed boundaries

This registration is **one partial deliverable** of Agora #221 and upstream CATSS #16. It must *not* advertise `catss-bhsa` or `catss-lxx`: those need explicit trusted read-only parent binding for BHSA 2021 and CenterBLC/LXX 1935, and pinned LXX JoshB 9:2a-f spans are absent. No local CATSS resource is preinstalled or searchable in Context-Fabric merely because its producer was registered. Mark verification `community` until successful real managed sandbox end-to-end smoke; release tracking stays disabled.

The existing full 46-file upstream audit downloaded CATSS over **unverified TLS**, a separate upstream issue #44. It proves parsed-output equivalence for that particular CI input but is not authenticated CCAT origin evidence. No such fetch belongs in this downstream Agora smoke. Use a tiny synthetic Genesis fixture and independently verify the exact TF alignment slots/ids, local source provenance, bubblewrap sandbox receipt and no network.

## Research sources

- https://github.com/alexsosn/CATSS-TF/pull/119
- https://github.com/alexsosn/CATSS-TF/actions/runs/38231819506
- https://github.com/alexsosn/Agora/issues/221
- https://github.com/alexsosn/Agora/issues/135
- `registry/materializers.yaml`, `tests/test_ctc_burns_registered_237.py`, `tests/test_copticscriptorium_materializer_registry.py`, `.github/workflows/materializer-install.yml`
