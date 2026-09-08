# Plan: promote Burns CSV reuse from exact managed replay (#114)

## Goal

Promote `burns-workbooks-csv-text-fabric` from fail-closed unknown cacheability to `reusable` only after Agora has replayed one exact immutable upstream commit under one exact **reproducible** integrity-verified managed execution identity and independently reviewed the semantic evidence.

Research: `P1-research-burns-csv-managed-replay-114.md`.

## Preconditions

- #103 trusted cacheability authorization must be merged before Stage B attestation is finalized.
- #111 reproducible managed execution identity/receipt semantics must be merged before Stage A records any identity intended for Stage B reuse authority.
- Current registry pin is `e1218b88d9d849c58ee25541339f32b0d8f5a7d3`.
- Selected evidence target is `f0c4e666fa9783b455ef3cc1b86238f41bb6e8b6` because it contains the packaged negative-tested semantic comparator while changing no converter core module relative to the current pin.
- Burns PDF remains outside this promotion.
- All CI input is synthetic; no Burns-derived source or output may be persisted/uploaded.

## Architectural decisions

1. **Exact commit means exact commit.** Do not transfer determinism evidence between `e1218b88…` and its descendants even when converter core code is unchanged.
2. **Use the comparator from the installed candidate runtime.** Agora must not maintain a parallel scholarly-equality implementation for this promotion.
3. **Separate evidence collection from authorization.** The managed canonical execution identity does not exist until installation completes, so Stage A records it while reuse remains denied; Stage B commits it as reviewed metadata.
4. **Attest only a reproducible replayed environment.** The first reusable identity is the exact Ubuntu/Python-3.12 environment exercised in CI, but Stage A must prove that identity is reproduced by two fresh equivalent managed installations under the post-#111 receipt contract. Other environments stay executable but fail closed for reuse.
5. **Converter semantics and Agora provenance are separate surfaces.** Upstream comparator covers converter TF/report output. Agora separately verifies registration/source/sandbox provenance while excluding only explicitly run-specific fields from equality.
6. **No artifact upload.** Evidence is compact metadata/log output only.
7. **Schema-v2 identities are not promotion authority.** Historical/raw schema-v2 `execution_identity_sha256` values may be logged for diagnosis but must not be frozen into `reviewed_environments`; #114 consumes the reproducible identity contract that #111 lands.

# Stage A — repin and collect exact managed replay evidence

## RED A1 — registry candidate and workflow contract

Tests-only commit before registry/workflow changes must require:

- Burns registration ref equals `f0c4e666fa9783b455ef3cc1b86238f41bb6e8b6`;
- version remains `0.2.0`, repository/manifest/materializer IDs remain unchanged;
- CSV still has no effective reusable authorization at this stage;
- PDF has no reusable authorization;
- the workflow performs two **fresh equivalent managed installations** of the exact candidate on the target runtime/platform and requires their post-#111 canonical execution identities to be equal;
- one verified installation performs two CSV executions into distinct fresh directories from one synthetic source;
- both executions use the normal registered runner with required sandbox;
- workflow imports `ugarit_context_parsing._semantic_compare` from that resolved managed runtime and requires `compare_text_fabric_artifacts(first, second) == ()`;
- workflow creates a disposable negative-control copy, changes a scholarly TF feature/value, and requires comparator inequality including a scholarly feature/persisted-file difference;
- workflow reads and prints the reproducible managed execution identity in a compact evidence line;
- workflow does not call `actions/upload-artifact` for Burns source/generated outputs;
- existing one-run semantic smoke checks remain or are subsumed by the stronger replay assertions.

Expected RED: registry still pins `e1218b88…`, workflow only materializes once, and/or the #111 reproducible receipt contract is unavailable. Do not implement around a missing #111 prerequisite; leave this lane blocked until that contract is merged.

## GREEN A1 — deliberate candidate repin

Change only the Burns registry `ref` to `f0c4e666…`. Do not add `cacheability.reusable` yet.

Run registry validation and release/update regression tests to prove ref-only repin does not alter manifest ID/version/materializer binding.

## GREEN A2 — reproducible managed replay workflow

After #111 is merged, extend the Burns install-smoke/evidence job:

1. install the exact candidate through the normal explicitly approved installer into managed root A;
2. install it independently into fresh managed root B under the same Python/runtime/platform cell and dependency-resolution inputs;
3. resolve and integrity-verify both post-#111 receipts;
4. require their canonical `execution_identity_sha256` values to be identical while preserving whatever raw per-install integrity hashes #111 defines;
5. print `BURNS_REPLAY_EXECUTION_IDENTITY_SHA256=<64hex>` from that shared canonical identity;
6. create synthetic CSV source once;
7. materialize output A via `agora_materialize_registered.py` under real bubblewrap using one verified installation;
8. materialize output B via the same command/runtime/source into a fresh output directory using that **same** installation, proving repeated converter execution rather than cross-install output equivalence;
9. from a working directory outside the Agora checkout, set `PYTHONPATH` to the selected managed runtime and import the installed upstream comparator;
10. require semantic equality A/B;
11. copy B to a disposable negative-control directory;
12. mutate one known scholarly node-feature value (for example `cuc_tablet.tf` canonical synthetic KTU value) without changing structure validity;
13. require comparator differences to include the persisted TF file and loaded node feature;
14. separately compare `agora-materialization.json` after deleting only explicitly run-specific fields; require plugin ID/ref, materializer ID, source type/content digest, sandbox and code/runtime identity to remain correctly bound.

The workflow must delete/use runner-temporary directories only and must not upload them.

## Stage A exact-head gate

Require:

- #111's receipt/identity migration and clean-install reproducibility tests green on the relevant platform/runtime;
- Foundation;
- registered materializer install smoke;
- materialization sandbox E2E;
- exact upstream manifest compatibility;
- two fresh equivalent Burns candidate installs producing the same canonical execution identity;
- no restricted artifact upload path;
- independent adversarial review of candidate ref, identity reproducibility, and workflow evidence semantics.

Record from the successful exact-head log:

- candidate ref;
- exact canonical `execution_identity_sha256`;
- receipt schema/identity-contract version introduced by #111;
- Python/runtime/platform cell;
- evidence that fresh install A and fresh install B yielded the same canonical identity;
- stable workflow/test target and run evidence.

Do not merge a `reusable` attestation in Stage A. Stage A may merge the reviewed repin/evidence lane with reuse still denied. Stage B must follow only from immutable reviewed Stage A evidence; do not rely on a transient workspace surviving across CI runs.

# Stage B — bind exact reproducible replay identity into cacheability authorization

## RED B1 — exact evidence-backed registry disposition

After Stage A exact-head replay succeeds, add tests-only commit freezing the observed canonical identity `<OBSERVED_SHA256>` and requiring:

- `cacheability.burns-workbooks-csv-text-fabric.mode == reusable`;
- `reviewed_ref == f0c4e666…`;
- exactly the observed reproducible execution identity is present in `reviewed_environments` for the first promotion;
- evidence contains a `managed-replay` entry pointing to `alexsosn/Agora`, an immutable Agora evidence commit/ref, and a stable replay target/check;
- `resolve_cacheability_authorization()` returns reusable when run against a **fresh independently installed** verified synthetic installation with that same canonical identity/ref;
- same plugin ref with a different execution identity returns unknown/reuse denied;
- changed plugin ref returns unknown/reuse denied;
- a legacy/pre-#111 receipt cannot accidentally satisfy the new reusable attestation;
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
- registered install smoke performing a **fresh install** whose canonical identity equals the attested Stage A identity, then executing the replay again;
- sandbox E2E;
- trusted #103 authorization tests;
- #111 receipt migration/reproducibility tests;
- release-update tests proving ref/version drift invalidates effective reuse;
- independent adversarial exact-head review.

Review must compare the registry execution identity to the reproducible identity produced by the exact Stage A and fresh Stage B installs, not merely validate its shape.

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

- Install twice only to prove the post-#111 canonical identity reproduces across clean equivalent managed installations.
- Perform the scholarly replay twice from one selected verified managed installation so converter repeated-execution evidence is not conflated with installer reproducibility.
- No repair/reinstall between scholarly replay A and B.
- Registered runner must hold its normal runtime lock for each execution integrity/binding window.
- Reuse is not involved in Stage A; both materialization calls really execute the converter.
- Source bytes must remain unchanged across both replay runs.

# Documentation

Update registry/materializer docs only in Stage B to state:

- Burns CSV reusable is exact-ref + exact canonical environment only;
- the first attested environment is the recorded Ubuntu/Python-3.12 reproducible managed identity;
- equivalent fresh installs on that same runtime/platform are expected and tested to reproduce the identity;
- other platforms/runtime closures remain executable but non-reusable until separately evidenced;
- PDF remains unknown until separate evidence;
- any ref/dependency/runtime drift disables reuse pending new replay;
- legacy pre-#111 receipt identities are not reusable authority.

# Independent adversarial review

For Stage A challenge:

- whether the repin contains hidden converter/manifest behavior changes;
- whether the installed comparator really comes from the managed candidate runtime;
- whether two clean candidate installations really reproduce the same post-#111 identity rather than hitting installer idempotency;
- whether replay outputs A and B share one selected verified execution identity;
- whether only `@dateWritten` is excluded from converter equality;
- whether negative control exercises a scholarly value and remains loadable;
- whether source or generated artifacts can be uploaded/leaked;
- whether the evidence line exposes only non-restricted metadata.

For Stage B challenge:

- whether the committed execution identity exactly matches Stage A evidence **and** a fresh Stage B installation;
- whether a legacy/path-sensitive schema-v2 identity could be accepted accidentally;
- whether evidence points to immutable code/check target;
- whether another environment/ref can accidentally authorize;
- whether release automation can carry reusable authority across pin drift;
- whether PDF/Pseudepigrapha inherited evidence;
- whether user-local source names/paths entered public metadata.

Every blocker gets a focused regression RED before correction.

# Definition of done

#114 is complete only when one exact immutable Burns CSV commit and one exact **reproducible** verified Agora managed execution identity have negative-tested semantic replay evidence, at least two equivalent fresh installations reproduce that canonical identity on the attested runtime/platform, and the registry grants reuse only to that ref/identity pair. Direct execution must remain available everywhere else, with reuse denied fail-closed.
