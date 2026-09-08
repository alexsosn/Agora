# Design amendment: version-scoped verification promotion (#107 / #115)

## Status

This amendment is normative for the merged #107 design and overrides any earlier wording that could be read as allowing a changed corpus/member candidate to retain `verification.status: verified` merely because the same stable verification check ID still exists.

It resolves the post-merge independent adversarial review finding tracked in #115.

## Current trust-model constraint

Agora's resource/member verification checks are stable subject-bound executors. For example, `resource-load/bhsa`, `resource-load/cuc`, and `member-load/greek-iliad` bind a resource/member, workflow matrix cell, claims, and evidence level. They do **not** bind the canonical check definition itself to one source commit or one TF path.

That is intentional for reusable check identity, but it means a version updater cannot treat an existing `check_id` as proof that a newly selected source revision/TF root has already passed the check.

Therefore changing runtime dataset identity invalidates the old `verified` claim until the exact candidate is exercised.

## Verification identity

For version-promotion purposes, evidence validity is scoped to the effective dataset identity:

```text
resource subject:
  (resource_id, immutable source revision, TF path)

collection-member subject:
  (collection resource_id, member_id, immutable collection source revision, member TF path)
```

A change to any identity component above invalidates prior candidate verification for that subject, even when the stable check ID and representative assertions remain unchanged.

For a collection source-revision update, every independently verified member whose bytes are supplied by that collection revision is considered changed evidence identity. Reusing the same member path string is not enough to preserve verification across a new collection commit.

## Required two-stage proposal contract

#108 must implement candidate adoption as two trust stages inside one reviewable update PR, or an equivalent mechanism with the same fail-closed properties.

### Stage A — candidate selected, verification pending

When a proposal changes a resource/member effective dataset identity:

1. write the reviewed candidate immutable source revision and validated TF path/member-index state;
2. write matching `version_tracking.accepted` candidate publication/source/path state as appropriate;
3. preserve stable configured check IDs as executable check configuration where useful;
4. **downgrade/invalidate any prior `verified` status for every affected subject** before the candidate live check runs;
5. report the subject as verification-pending, never as candidate-verified;
6. keep known issues and licensing claims at the same or a more conservative level;
7. run canonical validation successfully in this non-verified candidate state.

The exact downgraded status value may follow the existing registry vocabulary (`community` unless a more conservative existing state is required), but it must not be `verified`.

A candidate PR is allowed to exist in this Stage-A state. Discovery automation must not fabricate a successful evidence result merely because it scheduled the workflow.

### Stage B — evidence-backed promotion

Only after the Stage-A PR head has successfully executed the configured subject-bound live check against the exact candidate identity may a later commit on the same review PR restore `verification.status: verified` for that subject.

The promotion step must:

- identify the exact Stage-A candidate source revision/path that was exercised;
- reject evidence from an earlier PR head, earlier source revision, or different member path;
- promote only subjects whose required claims passed;
- leave unrelated collection/resource/member statuses unchanged;
- preserve canary/known-issue evidence as non-positive evidence;
- rerun normal exact-head CI after the promotion commit;
- still require ordinary independent review before merge.

The mechanism may be a deterministic trusted promotion helper/workflow or an explicit maintainer invocation, but it must be reproducible and testable. It must never auto-merge the PR.

If Stage B is not implemented in the first #108 slice, Stage A remains a truthful usable outcome: the update PR may carry the candidate at a downgraded status and require later reviewed promotion. It may **not** carry stale `verified` state for convenience.

## Promotion-evidence trust boundary

Stage B must not let a candidate PR manufacture its own proof by editing the verification executor, stable check definition, or evidence-consumer logic and then consuming that PR-authored run as authoritative evidence.

A trusted Stage-B implementation must therefore do one of the following:

- evaluate the promotion decision with code/workflow definitions loaded from reviewed `main`, while treating candidate-run outputs as data; or
- prove before promotion that the candidate diff leaves the relevant verification check definition, workflow, smoke implementation, artifact contract, and promotion verifier byte-equivalent to the reviewed base.

If any relevant evidence-producing or evidence-consuming executable surface differs from the trusted base, automatic Stage-B promotion fails closed and requires explicit review/re-establishment of the trust root.

The ordinary final independent PR review remains required even after this guard; this rule prevents the PR from self-asserting `verified` before that review.

## Required RED contracts for #108

Before implementation, add tests proving at least:

1. changing a verified resource's source revision while leaving the old stable check ID present cannot leave the resource canonically `verified`;
2. changing a verified resource's TF path has the same invalidation effect;
3. changing a collection source revision invalidates prior `verified` member status even when the member ID/path text is unchanged;
4. changing a verified member TF path invalidates that member without automatically changing unrelated sibling members or the collection aggregate;
5. an unchanged effective dataset identity may preserve the existing verification state;
6. Stage-B promotion rejects evidence produced for a different PR head/source revision/TF path;
7. Stage-B promotion affects only the exact subjects whose required live claims passed;
8. a `known-issue-canary` check cannot satisfy positive promotion claims;
9. a candidate that has not completed Stage B remains non-verified even if the workflow/check definition itself has `evidence_level: verified`;
10. final promoted state still passes the existing resource/member promotion validator from #19;
11. candidate changes to the relevant verification workflow/check/smoke/promotion-verifier surface block automatic Stage-B promotion unless the trusted-base mechanism is used;
12. candidate-produced evidence cannot cause promotion when the evidence consumer itself comes from unreviewed candidate code.

These are in addition to the original RED4 compatibility/licensing tests and RED5 deterministic PR-automation tests.

## Default-branch discovery restriction

For v1, `discovery.mode: default-branch` is observation/discovery only. The schema/semantic validator must reject:

```text
default-branch + promotion: proposal
```

unless a later reviewed design explicitly defines a safe promotion policy for that combination.

This keeps a moving branch from becoming an implicit publication channel. Collections that currently have only a moving default branch can still use discovery-only reporting and review a source-revision/index update explicitly; #108 must not silently reinterpret branch movement as acceptance.

Add this as an explicit RED1 mode-combination test rather than relying on a generic "mode-specific fields" assertion.

## Relationship to accepted publication state

The existing accepted-publication amendment remains required. Stage A binds the candidate runtime commit/path and accepted publication state together; Stage B changes only the trust claim after exact candidate evidence succeeds.

Thus publication acceptance, runtime identity, and verification remain distinct:

```text
publication candidate selected
        -> immutable runtime identity recorded
        -> candidate trust downgraded/pending
        -> exact candidate live evidence
        -> evidence-backed trust promotion
        -> exact final-head CI + independent review
```

No step may infer the next one automatically from the existence of an old stable check ID.

## Definition of done

#115 is complete when this amendment is exact-head green, independently reviewed, and merged before #108 production implementation relies on automatic candidate promotion semantics.
