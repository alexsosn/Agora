# Research: resource/member verification evidence and promotion gates (#19)

## Question

What remains of #19 on current `main`, after the collection-index, known-issue, representative-load, and client/platform verification work that landed after the issue was written?

This research is intentionally about Agora-owned trust/integration metadata. It does not propose semantic validation of third-party corpora beyond narrow integration sentinels already used by the representative-load smoke.

## Current state on `main` @ `09c7996c`

The issue's 2026-08-29 current-state section is materially stale.

### Already implemented

1. **Collection members are canonical, independently addressable records.**
   `registry/collections/*.yaml` contains commit-bound indexes; `collection-index.schema.json` gives every member its own `verification.status`.

2. **Members already have evidence references.**
   A member may carry `verification.evidence: [{check_id: ...}]`, and `validate_registry.py` rejects references to missing IDs.

3. **Members already have compact known-issue references.**
   A member may carry `verification.known_issues: [{issue_id: ...}]`; validation requires the issue to exist on the parent resource.

4. **Known issues already have severity.**
   Resource known-issue definitions support `advisory` and `blocking` severity.

5. **Blocking member issues already fail before acquisition/materialization.**
   `KnownIssueBlockingTests` proves a blocking member is rejected before `GitStore.materialize`, while an advisory member remains materializable.

6. **Representative real-load evidence already exists.**
   `scripts/smoke_context_fabric_resources.py` and `.github/workflows/context-fabric-load-smoke.yml` already exercise:
   - BHSA: acquisition/load plus narrow `g_cons`/`sp` sentinels;
   - CUC: acquisition/load plus `sign`/`usign` sentinels;
   - one Greek Iliad collection member: acquisition/load plus `orig`/`main` sentinels;
   - one known-bad Greek member: Agora blocks it before acquisition, then a deliberately isolated canary reproduces the exact upstream failure signature so a future upstream fix forces retirement/re-audit.

7. **Claim dimensions are already documented as separate.**
   Plugin/client verification, provider health, resource status, member status, and scholarly data quality are deliberately different claims. #77 strengthened this separation further.

### Still missing

1. **Resource records cannot reference executable evidence.**
   `resources.schema.json` gives resource verification only `status`, `notes`, and `known_issues`; unlike members, there is no `verification.evidence` field.

2. **Evidence references are only existence-checked.**
   Current member validation can establish that a `check_id` exists, but not that the check actually targets that resource/member. A member could therefore reference an unrelated client smoke and satisfy the present structural rule.

3. **The executable-check catalog is client-shaped.**
   `registry/verification-checks.yaml` is already a shared catalog used by plugin/client claims and provider health, but its schema requires `client` and `transport` for every check. Direct resource/provider load evidence should not fabricate a Claude/Codex transport.

4. **No resource/member checks are registered.**
   The existing Context-Fabric load smoke has the right runtime behavior, but no stable check IDs connect BHSA, CUC, or the Iliad member to exact executable workflow cells/artifacts.

5. **`verified` resource/member status has no evidence invariant.**
   Registry validation accepts a promoted resource/member status without requiring matching live evidence or minimum integration coverage.

6. **Known-issue impact is not explicit.**
   `severity` exists, but the one current resource known issue (`context-fabric/duplicate-structure-levels`) is a definition for affected collection members, not a collection-wide failure. Promotion rules need to distinguish a resource-wide blocking issue from a member-scoped blocking issue.

7. **The representative-load workflow is not case-addressable in the evidence graph.**
   One job executes all four cases into one JSONL artifact. A stable resource/member check should bind to one exact executable case, not merely to a job that happens to run several cases.

## Important stale assumptions in #19

- "Collection indexes are still pending" is no longer true: four commit-bound indexes are present under `registry/collections/`.
- Member-level evidence/status fields and known-issue references are already present.
- The issue's TLHdig-TF wording should not be used to resurrect obsolete status/warnings. Current canonical `TLHdig-TF` status is `community`. The invariant we need is general: plugin/provider strength must never auto-promote or erase a resource/member's own lower status or warnings.

## Architecture constraints

Per `CONTRIBUTING.md` and `wiki/architecture/ref-plugin-boundary.md`, Agora may verify:

- acquisition/materialization it owns;
- successful load through the supported integration;
- feature/tool accessibility;
- a very small stable public value needed to prove the integration reaches the intended dataset;
- known integration/upstream failure signatures for retirement canaries.

Agora must **not** turn this into a corpus semantic regression suite. Morphology correctness, edition correctness, annotation quality, or broad scholarly suitability remain upstream/data-owner responsibilities.

The existing BHSA/CUC/Iliad sentinels fit this boundary: they are narrow identity/integration checks, not attempts to certify the corpora.

## Design options considered

### A. Separate `resource-verification-checks.yaml`

Pros:
- clean conceptual separation from client checks.

Cons:
- creates a second executable evidence catalog even though provider health and member evidence already reference `verification-checks.yaml`;
- introduces namespace/resolution rules for references that are currently globally unique;
- risks duplicated executor validation.

**Rejected.** One catalog should describe executable checks; claim type is a property of a check, not a reason for a second registry.

### B. Keep current check shape and pretend resource loads are a Codex/Claude check

Pros:
- tiny schema change.

Cons:
- false provenance: `smoke_context_fabric_resources.py` runs the provider/service directly, not a generated client transport;
- collapses exactly the claim dimensions #18/#77 worked to separate.

**Rejected.**

### C. Generalize the existing check catalog with resource/member subjects

Keep the existing client-check form backward compatible and add a second, explicit resource-evidence form with:

- exact provider/resource/member subject;
- declared integration coverage;
- the same validated unittest/GitHub-Actions executor model;
- no fabricated client/transport.

Resource/member references must match the exact subject, not merely an existing ID.

**Selected.**

## Existing evidence suitable for the first canonical seed

The current real-load smoke can support bounded initial evidence without expanding CI breadth:

- `bhsa` resource;
- `cuc` resource;
- `greek_literature` Iliad member `canonical-greeklit-tlg0012-tlg001-perseus-grc2-1-67402e1a`;
- known-bad Greek member `canonical-greeklit-tlg0001-tlg001-perseus-grc2-1-62c8ed02` as a blocking-issue canary, not a verified member.

The parent `greek_literature` collection must remain independent: a verified Iliad member does not promote the collection, and a blocked Argonautica member does not demote every other member.

## Result

#19 should be respecified as a **linkage and promotion-invariant ticket**:

1. make executable checks target resources/members precisely;
2. let resource records reference those checks;
3. make `verified` status evidence-backed and known-issue-aware;
4. bind the already-existing representative load cases into that graph;
5. keep resource/member/plugin/provider/data-quality claims independent.

No new corpus capability, parser behavior, or upstream semantic fix is required.
