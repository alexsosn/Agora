# Agora #221 stage 2: standalone CATSS materializer → Context-Fabric local consumer

## Research (actual code and CI, 2026-10-12)

- Stage-1 registration [PR #273](https://github.com/alexsosn/Agora/pull/273) is merged at `4dd54d892c83925ce94cc7d81beb7e5f173ba48d`. Managed CI [38239047913](https://github.com/alexsosn/Agora/actions/runs/38239047913) proved immutable CATSS-TF `3ee63c4c054960b816b14496815815153e5e543d` passive fetch, explicit Python install, required bubblewrap, user-local 2-alignment-slot conversion, original input preserved, host receipt, native Text-Fabric `Fabric.loadAll()`, and idempotent install. CATSS `catss-bhsa`/`catss-lxx` parent modules are NOT registered.
- Exact real `.github/workflows/materializer-install.yml` already has a **green** CopticScriptorium-TF → Context-Fabric handoff in the same workflow: install `plugins/context-fabric` under Python 3.13, launch local MCP `agora_context_fabric.server` with runner-scoped cache, call `install_local_corpus` on a generated native TF directory, discover, `prepare_corpus(source_mode="offline")`, `load_corpus(source_mode="offline")`, `describe_corpus`, `search`, `unload_corpus`, `remove_cached_corpus`. Reuse the supported *public* MCP interface rather than introducing a CATSS-specific consumer adapter.
- CATSS actual native output is the **standalone alignment-slot** Text-Fabric root, with `otype.slotType='alignment'`, two fixture slots, `catss_alignment_id` and `catss_lxx_plus`; it also contains native TSV sidecars and Agora provenance. Its parent-dependent BHSA/LXX projections are not part of this validation.
- Important unknown to validate live: Context-Fabric local importer may handle native TF plus non-TF sidecars differently than Coptic's `tf/` directory. Detect and correct a real contract defect if needed; never pre-delete user data, symlink around importer constraints, or claim local import succeeded from the standalone TF load alone.

## Plan and gates

1. Preserve a **RED-only test commit** asserting the CATSS registered job contains an exact-head, after-materialization, real MCP handoff with user-local native source, explicit offline prepare/load, discover/query/unload/remove and proof marker. Confirm it fails before adding workflow steps.
2. GREEN: extend only the already-present `catss-tf` registered workflow job, keeping source, pin, approved installation, and kernel sandbox unchanged. Call actual Context-Fabric MCP with `CATSS_TF=$RUNNER_TEMP/catss-output`, runner-private cache, offline load of `catss_alignment_id`/`catss_lxx_plus`; count `alignment` slot nodes and verify cleanup. Do not fabricate source data or register unreviewed BHSA/LXX projections.
3. Run relevant focused tests and exact-head live CI: contract, registry, managed synthetic fixture producer, native Text-Fabric, Context-Fabric import/discovery/offline query/removal, Foundation and existing materializer/sandbox checks. Reject if any relevant step fails.
4. Independently adversarially review actual diff, Code/manifest identity, CI logs and failure paths after implementation. Finalize only if exact-head checks pass. Keep Agora #221 open for parent-bound projection feature modules and full scholarly source validation.

## Risk and limit

This verifies the interface for a **two-row synthetic local** input with no CATSS source licensing dependency; it does not establish correctness of 46-file source parsing, automatic installation of a corpus, or parent-dependent feature composition. The original 46-file upstream real-data equivalence belongs to CATSS-TF, not this narrowly scoped Agora consumer smoke.
