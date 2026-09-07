# Research: v0.1 release-document consistency (#16)

## Question

Which parts of issue #16 are still true on current `main`, which have already been repaired, and what is the smallest durable mechanism that keeps release/status documentation from overstating canonical registry evidence?

## Current source-of-truth audit

Audited against `main` at `293c3be5688fea2d7e5f5edb867559301ab86e57`.

### Already repaired

- `wiki/releases/v0.1-scope-frozen.md` now states that TLHdig-TF follows its default branch while explicitly selecting `tf/0.1.0`. The old “not pinned in Phase 1” contradiction from #16 is no longer present.
- `README.md` already states the current verification model correctly: all four aggregate plugin statuses remain `community`; Codex paths carry live `verified` evidence; Claude paths currently carry deterministic `community` evidence.
- The README no longer presents Phase 5 skills as wholly future work; it describes bundled scholarly skills as an existing capability.

### Still stale: active release plan

`wiki/releases/v0.1-plan-active.md` contains several current-state claims that contradict the repository:

1. Phase 4 says **“implemented and Verified”**, while `registry/plugins.yaml` gives every aggregate plugin `verification.status: community`.
2. Phase 5 says **“next major implementation phase”** and the sequence labels it `NEXT`, while the repository already ships and validates the required v0.1 scholarly skills.
3. Phase 6 says the current v0.1 plugin statuses are `verified`, again exceeding the canonical aggregate status.
4. Phase 7 still lists installation instructions and plugin-specific usage pages as missing even though installation guidance and plugin/skill guidance now exist. The compatibility matrix remains genuinely unfinished and belongs to #18.
5. The end-of-plan “main remaining v0.1 work” paragraph still reflects an older project stage and should be reconciled with the current registry/tests rather than preserved as a status claim.

### Still stale: wiki index priorities

`wiki/README.md` has a section titled **“Current P0 engineering findings”** copied from an older review. It still lists several items that have since been implemented: immutable SHA-addressed materialization, collection snapshot propagation, representative corpus loads, README verification reconciliation, and executable verification evidence. The only clearly still-open item in that list is repository branch protection (#9), which is an administration/governance task rather than a reason to present the completed engineering items as current P0 work.

The wiki index is therefore not merely historical prose: its “Current” label makes it part of the user/contributor-facing status surface covered by #16.

### Still stale: implementation-details pointer

`wiki/architecture/ref-implementation-details.md` has an otherwise current phase-status table, but its closing sentence still names Context-Fabric snapshot integrity and representative corpus-load evidence as among the highest-priority implementation items. Those are completed. Because README links this file as the detailed current implementation/status reference, that stale priority pointer should be reconciled in the same documentation-consistency change.

## Why ordinary prose edits are insufficient

The verification model is intentionally multi-dimensional: aggregate plugin status, per-client status, provider health, and resource/member evidence are separate. Repeating a hand-written “current status” in several documents invites the same drift to recur whenever registry evidence changes.

A validator that merely rejects specific stale phrases would encode historical mistakes rather than the intended contract. A stronger and smaller boundary is to generate the dynamic plugin/client verification summary from canonical registry data and make CI check that generated block. The broader phase/priority narrative should remain hand-authored but must stop calling historical review findings “current” after they are completed.

## Existing contracts to reuse

- `registry/plugins.yaml` is canonical for aggregate and per-client plugin verification status and references stable verification check IDs.
- `registry/verification-checks.yaml` is canonical for check kind, evidence level, plugin/client binding, transport, and executor semantics; live evidence must be joined through this data rather than inferred from check-ID names.
- `registry/v0.1.yaml` defines the fixed v0.1 plugin family set.
- Existing tests under `tests/test_skills.py` already enforce the required committed v0.1 skill set; no new skill registry is needed merely to update Phase 5 prose.
- Foundation already runs deterministic generators/checkers and is the natural CI gate for another cheap offline freshness check.

## Proposed scope

1. Reconcile stale current-state prose in `v0.1-plan-active.md`; do not rewrite the already-correct scope document or README unnecessarily.
2. Reconcile `wiki/README.md` so completed review findings are not presented as current P0 engineering work; preserve links to historical reviews as history.
3. Reconcile the stale closing priority pointer in `wiki/architecture/ref-implementation-details.md` while preserving its otherwise-current phase table.
4. Add a deterministic generated verification-status block to the plan, derived from `registry/v0.1.yaml`, `registry/plugins.yaml`, and `registry/verification-checks.yaml`.
5. Add `--check` support and Foundation coverage so future registry status changes cannot leave that block stale.
6. Update Phase 5 from `NEXT` to implemented/currently refining, grounded in the existing skill tests.
7. Update Phase 7/current-sequence/current-remaining-work wording to describe only genuinely unfinished work, leaving the client/platform matrix explicitly to #18.

## Non-goals

- Do not change any registry verification status.
- Do not promote Claude paths or aggregate plugins beyond current evidence.
- Do not create a second canonical verification model in Markdown.
- Do not solve #18’s cross-platform/client verification matrix in this ticket.
- Do not solve #9 branch protection from repository code.
- Do not change scholarly skill behavior or add new skills.

## Risks to test adversarially

- Generator accidentally derives status from all plugins rather than the fixed v0.1 set.
- Mixed client statuses are flattened into an aggregate “verified” claim.
- Live evidence is inferred from check-ID naming instead of canonical check metadata.
- Missing/mismatched client evidence is silently omitted instead of failing closed or being represented conservatively.
- Generated-block matching is loose enough that stale hand-written dynamic claims survive elsewhere in the plan.
- The generator rewrites unrelated hand-authored release history.
- Wiki index cleanup erases historical review evidence rather than changing only the false “current” framing.
- Current-status cleanup updates the plan but leaves README-linked `ref-implementation-details.md` pointing at already-completed priorities.

## Research conclusion

#16 is still actionable but should be rescoped: TLHdig scope and README verification wording are already fixed. The remaining defects are stale `v0.1-plan-active.md` current-state prose, stale “Current P0” framing in `wiki/README.md`, one stale current-priority pointer in `ref-implementation-details.md`, and the lack of a canonical registry-derived guard for the plan’s dynamic verification summary. A generated verification block plus targeted narrative reconciliation and deterministic freshness checking is the smallest durable fix.
