# Plan: promote Burns CSV reuse from exact managed replay (#114)

## Goal

Promote `burns-workbooks-csv-text-fabric` from fail-closed unknown cacheability to `reusable` only after Agora has replayed one exact immutable upstream commit twice under one exact integrity-verified managed execution identity and independently reviewed the semantic evidence.

Research: `P1-research-burns-csv-managed-replay-114.md`.

## Preconditions

- #103 trusted cacheability authorization must be merged before Stage B attestation is finalized.
- Current registry pin is `e1218b88d9d849c58ee25541339f32b0d8f5a7d3`.
- Selected evidence target is `f0c4e666fa9783b455ef3cc1b86238f41bb6e8b6` because it contains the packaged negative-tested semantic comparator while changing no converter core module relative to the current pin.
- Burns PDF remains outside this promotion.
- All CI input is synthetic; no Burns-derived source or output may be persisted/uploaded.

## Architectural decisions

1. **Exact commit means exact commit.** Do not transfer determinism evidence between `e1218b88…` and its descendants even when converter core code is unchanged.
2. **Use the comparator from the installed candidate runtime.** Agora must not maintain a parallel scholarly-equality implementation for this promotion.
3. **Separate evidence collection from authorization.** The managed `execution_identity_sha256` does not exist until installation completes, so Stage A records it while reuse remains denied; Stage B commits it as reviewed metadata.
4. **Attest only the replayed environment.** The first reusable identity is the exact Ubuntu/Python-3.12 environment exercised in CI. Other environments stay executable but fail closed for reuse.
5. **Converter semantics and Agora provenance are separate surfaces.** Upstream comparator covers converter TF/report output. Agora separately verifies registration/source/sandbox provenance while excluding only explicitly run-specific fields from equality.
6. **No artifact upload.** Evidence is compact metadata/log output only.

# Stage A — repin and collect exact managed replay evidence

## RED A1 — registry candidate and workflow contract

Tests-only commit before registry/workflow changes must require:

- Burns registration ref equals `f0c4e666fa9783b455ef3cc1b86238f41bb6e8b6`;
- version remains `0.2.0`, repository/manifest/materializer IDs remain unchanged;
- CSV still has no effective reusable authorization at this stage;
- PDF has no reusable authorization;
- registered-install workflow performs two CSV executions into distinct fresh directories from one synthetic source and one managed installation;
- both executions use the normal registered runner with required sandbox;
- workflow imports `ugarit_context_parsing._semantic_compare` from the resolved managed runtime and requires `compare_text_fabric_artifacts(first, second) == ()`;
- workflow creates a disposable negative-control copy, changes a scholarly TF feature/value, and requires comparator inequality including a scholarly feature/persisted-file difference;
- workflow reads and prints the installation receipt execution identity in a compact evidence line;
- workflow does not call `actions/upload-artifact` for Burns source/generated outputs;
- existing one-run semantic smoke checks remain or are subsumed by the stronger replay assertions.

Expected RED: registry still pins `e1218b88…` and workflow only materializes once.

## GREEN A1 — deliberate candidate repin

Change only the Burns registry `ref` to `f0c4e666…`. Do not add `cacheability.reusable` yet.

Run registry validation and release/update regression tests to prove ref-only repin does not alter manifest ID/version/materializer binding.

## GREEN A2 — managed replay workflow

Extend the Burns install-smoke job after installation:

1. resolve managed runtime and receipt;
2. print `BURNS_REPLAY_EXECUTION_IDENTITY_SHA256=<64hex>`;
3. create synthetic CSV source;
4. materialize output A via `agora_materialize_registered.py` under real bubblewrap;
5. materialize output B via the same command/runtime/source into a fresh directory;
6. from a working directory outside the Agora checkout, set `PYTHONPATH` to the managed runtime and import the installed upstream comparator;
7. require semantic equality A/B;
8. copy B to a disposable negative-control directory;
9. mutate one known scholarly node-feature value (for example `cuc_tablet.tf` canonical synthetic KTU value) without changing structure validity;
10. require comparator differences to include the persisted TF file and loaded node feature;
11. separately compare `agora-materialization.json` after deleting only explicitly run-specific fields; require plugin ID/ref, materializer ID, source type/content digest, sandbox and code/runtime identity to remain correctly bound.

The workflow must delete/use runner-temporary directories only and must not upload them.

## Stage A exact-head gate

Require:

- Foundation;
- registered materializer install smoke;
- materialization sandbox E2E;
- exact upstream manifest compatibility;
- no restricted artifact upload path;
- independent adversarial review of candidate ref + workflow evidence semantics.

Record from the successful exact-head log:

- candidate ref;
- exact `execution_identity_sha256`;
- Python/runtime/platform cell;
- stable workflow/test target and run evidence.

Do not merge a `reusable` attestation in Stage A. Stage A may merge the reviewed repin/evidence lane with reuse still denied, or Stage B may follow on the same PR only if the exact Stage A head and observed identity remain immutable and reviewable. Prefer separate immutable commits regardless.

# Stage B — bind exact replay identity into cacheability authorization

## RED B1 — exact evidence-backed registry disposition

After Stage A exact-head replay succeeds, add tests-only commit freezing the observed identity `<OBSERVED_SHA256>` and requiring:

- `cacheability.burns-workbooks-csv-text-fabric.mode == reusable`;
- `reviewed_ref == f0c4e666…`;
- exactly the observed execution identity is present in `reviewed_environments` for the first promotion;
- evidence contains a `managed-replay` entry pointing to `alexsosn/Agora`, an immutable Agora evidence commit/ref, and a stable replay target/check;
- `resolve_cacheability_authorization()` returns reusable when run against a verified synthetic installation with that exact identity/ref;
- same plugin ref with a different execution identity returns unknown/reuse denied;
- changed plugin ref returns unknown/reuse denied;
- PDF remains unknown/reuse denied;
- Pseudepigrapha remains unaffected;
- no restricted fixture/path/content is introduced into registry metadata.

Expected RED: Stage A deliberately has no reusable cacheability entry.

## GREEN B1 — minimal registry attestation

Add only the CSV cacheability metadata required by the frozen evidence. Do not add PDF or Pseudepigrapha reuse.

Attestation evidence target must identify the exact committed Stage A replay contract, not a mutable branch name.

## Stage B exact-head gate

Require:

- Foundation full suite;
- canonical registry validation;
- registered install smoke executing the replay again;
- sandbox E2E;
- trusted #103 authorization tests;
- release-update tests proving ref/version drift invalidates effective reuse;
- independent adversarial exact-head review.

Review must compare the registry execution identity to the identity produced by the exact replay run, not merely validate its shape.

# Provenance equality contract

The upstream comparator is authoritative for converter-owned `*.tf` and `conversion-report.json` semantics. Its only TF persistence exclusion is `@dateWritten`.

For Agora `agora-materialization.json`, define a separate canonical comparison helper/test. It may ignore only fields proven to be per-run observation metadata (for example a run timestamp). It must still compare/bind:

- plugin ID, repository and exact ref/commit if present;
- materializer ID;
- source type and content digest/identity (but not local basename/absolute path);
- manifest/code digest and verified execution identity when projected;
- sandbox backend/policy;
- output contract identity.

If current provenance omits verified execution identity, do not invent it inside #114 unless required for evidence; #103 authorization remains the authority. File a separate provenance ticket if a larger schema change is needed.

# Negative control construction

The negative copy must remain a loadable TF artifact. Prefer the already upstream-tested mutation approach: replace one synthetic canonical `cuc_tablet` value with another valid-looking canonical value. Require both:

- a normalized persisted-file difference for `cuc_tablet.tf`; and
- a loaded node-feature difference for `cuc_tablet`.

A mutation that merely corrupts syntax or deletes a required file is insufficient evidence of scholarly comparator sensitivity.

# Lock/runtime invariants

- Install once; replay twice from the same managed installation path and receipt identity.
- No repair/reinstall between A and B.
- Registered runner must hold its normal runtime lock for each execution integrity/binding window.
- Reuse is not involved in Stage A; both calls really execute the converter.
- Source bytes must remain unchanged across both runs.

# Documentation

Update registry/materializer docs only in Stage B to state:

- Burns CSV reusable is exact-ref + exact-environment only;
- the first attested environment is the recorded Ubuntu/Python-3.12 managed identity;
- other platforms/runtime closures remain executable but non-reusable;
- PDF remains unknown until separate evidence;
- any ref/dependency/runtime drift disables reuse pending new replay.

# Independent adversarial review

For Stage A challenge:

- whether the repin contains hidden converter/manifest behavior changes;
- whether the installed comparator really comes from the managed candidate runtime;
- whether A and B share one execution identity;
- whether only `@dateWritten` is excluded from converter equality;
- whether negative control exercises a scholarly value and remains loadable;
- whether source or generated artifacts can be uploaded/leaked;
- whether the evidence line exposes only non-restricted metadata.

For Stage B challenge:

- whether the committed execution identity exactly matches Stage A evidence;
- whether evidence points to immutable code/check target;
- whether another environment/ref can accidentally authorize;
- whether release automation can carry reusable authority across pin drift;
- whether PDF/Pseudepigrapha inherited evidence;
- whether user-local source names/paths entered public metadata.

Every blocker gets a focused regression RED before correction.

# Definition of done

#114 is complete only when one exact immutable Burns CSV commit and one exact verified Agora managed execution identity have reproducible, negative-tested semantic replay evidence and the registry grants reuse only to that pair. Direct execution must remain available everywhere else, with reuse denied fail-closed.