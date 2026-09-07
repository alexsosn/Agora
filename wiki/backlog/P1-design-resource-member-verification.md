# Design: machine-readable resource/member verification evidence (#19)

## Status

Design gate for #19. Implementation must not begin until this design is reviewed and merged.

Research: [`P1-research-resource-member-verification.md`](P1-research-resource-member-verification.md).

## Goal

Make `verified` resource/member status mean that Agora can point to exact executable, subject-matched integration evidence, while preserving the existing separation between:

- plugin/client verification;
- provider/service health;
- resource verification;
- collection-member verification;
- scholarly data quality.

This is a trust/evidence change, not a corpus-semantics change.

## Non-goals

- verifying all 37 Context-Fabric resources in this ticket;
- certifying textual, linguistic, morphological, annotation, or edition quality;
- fixing known upstream corpus/Context-Fabric bugs;
- deriving collection status from member status;
- deriving resource/member status from plugin or provider status;
- adding a second evidence/check registry;
- restoring stale historical TLHdig-TF status text merely because #19 mentioned it in August.

## Canonical model

### 1. Keep one executable-check catalog

`registry/verification-checks.yaml` remains the single catalog of stable executable check IDs.

Existing client checks remain valid without a mass migration. Add a second check variant for direct resource/member evidence.

Common fields remain:

```yaml
id: resource-load/bhsa
kind: live
plugin: context-fabric
evidence_level: community
executor: ...
```

A resource/member check additionally requires:

```yaml
provider: context-fabric
subject:
  type: resource            # or collection-member
  resource_id: bhsa
claims:
  - materialization
  - load
  - representative-content
```

Collection-member example:

```yaml
subject:
  type: collection-member
  resource_id: greek_literature
  member_id: canonical-greeklit-tlg0012-tlg001-perseus-grc2-1-67402e1a
```

Resource/member checks do **not** carry `client`, `transport`, or client-platform fields. They are direct provider/resource integration observations and must not pretend to execute Claude or Codex.

### 2. Check schema is a discriminated union by subject presence

`verification-checks.schema.json` should accept:

- the existing client-check shape: `client` + `transport`, optional provider/platform, no resource `subject`/`claims`;
- the resource-evidence shape: provider + `subject` + non-empty `claims`, no client/transport/platform.

No existing check IDs or plugin/client evidence semantics need to change.

### 3. Resource/member integration claims

Controlled resource-evidence claims:

- `discovery` — canonical resource/member can be resolved without claiming content load;
- `materialization` — exact dataset bytes can be acquired/materialized through Agora;
- `load` — the supported Context-Fabric integration loads the dataset;
- `representative-content` — one or more narrow stable feature/text values prove the intended dataset/feature path is accessible;
- `known-issue-canary` — an explicitly declared known issue was observed with its bounded retirement signature.

`representative-content` is an integration identity sentinel only. The artifact may record feature/value checks, but the registry does not claim those checks certify broad corpus correctness.

### 4. Resource verification references

Add to `resources.schema.json`:

```yaml
verification:
  status: community
  evidence:
    - check_id: resource-load/bhsa
```

The member schema already has the same compact reference form and should remain compatible.

### 5. Known-issue impact

Add one required field to resource known-issue definitions:

```yaml
impact: resource | member
```

Semantics:

- `impact: resource` describes a problem applicable to the resource as a whole;
- `impact: member` defines a problem that applies only to collection members that explicitly reference that issue ID.

The current `context-fabric/duplicate-structure-levels` definition becomes `impact: member` because only listed Greek members are affected.

This avoids the incorrect rule "a collection defines one blocking member issue, therefore the whole collection can never be verified."

## Validation rules

### Reference integrity

For every resource/member `verification.evidence` reference:

1. the check ID must exist;
2. the check must be a resource-evidence check rather than a client check;
3. check `plugin`/`provider` must match the resource;
4. check subject must exactly match:
   - resource ID for resource evidence;
   - resource ID + member ID for member evidence.

A plugin/client live check is therefore never valid evidence for a resource merely because it exists.

For every resource-evidence check definition:

- referenced resource must exist;
- `collection-member` subject requires a collection resource and an existing committed member ID;
- a `resource` subject must not name a member;
- executor binding must remain exact under the existing executor validator.

### Promotion rules

No evidence is required for `experimental` or `community` status. These statuses may still carry evidence.

`verified` is fail-closed:

#### Corpus or feature-module resource

The union of referenced **live + `evidence_level: verified`** subject-matched checks must include:

- `materialization`;
- `load`;
- `representative-content`.

#### Collection resource

The union must include `discovery` from a live verified resource-subject check.

This verifies collection discovery itself only; member evidence never promotes the collection.

#### Collection member

The union of live verified subject-matched checks must include:

- `materialization`;
- `load`;
- `representative-content`.

A check may satisfy several claims in one bounded execution.

### Known-issue promotion gates

A resource cannot be `verified` while it has an unresolved `blocking` issue with `impact: resource`.

A member cannot be `verified` while it references a `blocking` issue definition. Advisory issues do not block promotion, but remain visible.

A member-scoped issue definition on a collection does not by itself block the collection; only member references apply it.

`known-issue-canary` evidence does not count toward the positive coverage needed for `verified`.

### No propagation

Validation must not infer or propagate status:

- verified plugin ≠ verified resource;
- healthy provider ≠ verified resource;
- verified collection ≠ verified member;
- verified member ≠ verified collection;
- blocked member ≠ blocked collection or sibling member.

## Reuse the existing representative-load smoke

Do not add a second expensive Context-Fabric integration workflow.

Refactor `.github/workflows/context-fabric-load-smoke.yml` so each current real case is an exact matrix cell with its own artifact/check binding:

| Case | Canonical check | Subject | Positive claims |
|---|---|---|---|
| `bhsa` | `resource-load/bhsa` | resource `bhsa` | materialization, load, representative-content |
| `cuc` | `resource-load/cuc` | resource `cuc` | materialization, load, representative-content |
| `greek-iliad` | `member-load/greek-iliad` | exact Iliad member | materialization, load, representative-content |
| `greek-known-bad` | `member-canary/greek-argonautica` | exact Argonautica member | known-issue-canary |

The matrix cell should include the `case` and `check_id`, and each artifact name should be unique. The smoke script should bind/output that check ID and fail if the canonical check does not target the case's exact resource/member.

The existing contained cold-load smoke remains a separate bounded step/job; it is not resource-verification evidence unless separately modeled later.

### CI triggers

The representative-load workflow must rerun when any input capable of changing these claims changes, including:

- resource registry;
- collection indexes;
- verification check catalog/schema;
- representative-load script/tests;
- Context-Fabric runtime/package inputs;
- workflow itself.

Foundation continues to validate schemas, references, promotion rules, and generated projections deterministically.

## Staged evidence promotion

Do not mark new checks/statuses `verified` merely because the implementation exists.

Implementation sequence:

1. add resource/member check definitions at `evidence_level: community`;
2. link BHSA/CUC/Iliad records while their statuses remain `community`;
3. run the exact implementation-head representative-load workflow;
4. only after the exact subject cells succeed, promote those check definitions to `verified` and promote:
   - `bhsa` resource → `verified`;
   - `cuc` resource → `verified`;
   - Iliad member → `verified`;
5. leave `greek_literature` collection `community` and Argonautica member `community` with its blocking issue;
6. rerun exact-head Foundation + representative loads after promotion.

This mirrors the evidence-first promotion discipline used for client paths in #18/#77.

## Generated/runtime projections

Context-Fabric's installed catalog and installed collection indexes are lossless projections of canonical registry data. Resource/member evidence references and known-issue impact must therefore survive generation unchanged.

No runtime behavior needs to consume positive verification evidence to load a corpus. Positive status is descriptive/trust metadata. Existing blocking-known-issue runtime behavior remains the actual fail-fast safety gate.

## TLHdig-TF

Do not modify TLHdig-TF merely to satisfy stale wording in #19. Current canonical status is `community`. Add regression coverage that lower resource status/notes/known issues are not overwritten by plugin/provider verification, using current canonical records or synthetic fixtures as appropriate.

Any separate load-cost or performance warning belongs to the dedicated load-cost/performance tickets, not this evidence model.

## Documentation

Update the verification/evidence documentation to state:

- client checks and resource checks can share one executable-check catalog but have different subjects;
- provider health may observe a client path without promoting resources;
- resource/member `verified` requires explicit subject-matched live evidence;
- collection and member status are independent;
- representative content checks are integration sentinels, not scholarly-quality certification;
- blocking known-issue impact rules.

## TDD gates

Implementation PR must use RED commits before production changes.

### RED 1 — schema and exact-subject references

Add failing tests proving:

- resource schema accepts evidence references;
- resource/member check schema supports direct subjects without client/transport;
- client check cannot satisfy resource/member evidence;
- wrong resource/member target is rejected;
- missing target resource/member is rejected.

### RED 2 — promotion and issue impact

Add failing tests proving:

- `verified` corpus/member without required verified live claim coverage is rejected;
- community/experimental status can remain without evidence;
- resource-wide blocking issue rejects resource promotion;
- member-scoped blocking issue only rejects referenced members;
- advisory issue does not block verified status when evidence is otherwise sufficient;
- collection/member/plugin/provider statuses do not propagate.

### RED 3 — exact live workflow binding

Add failing tests proving:

- four existing representative cases have exact workflow matrix cells and stable check IDs;
- each cell uploads a unique artifact;
- the script binds the requested check to the exact case subject;
- verification registry/schema changes retrigger the real-load workflow.

### GREEN

Implement the minimum changes needed for each RED slice; run Foundation after each coherent slice.

Then run the live evidence/promotion sequence above.

## Final gate

Before merge:

1. freeze final head;
2. exact-head Foundation green;
3. exact-head representative-load workflow green for all four cells;
4. generated catalog/index freshness green;
5. independent adversarial review against current `main` rules and actual diff;
6. if review finds a defect, add regression first, fix, rerun, and re-review;
7. merge with expected-head protection and close #19 only when all acceptance criteria are satisfied by current repository state.

## Acceptance-criteria mapping

| #19 criterion | Design response |
|---|---|
| Resource records reference stable checks | add resource `verification.evidence` |
| Acquisition/load/content/source-specific evidence | resource check `claims` + existing bounded real-load sentinels |
| Independent member evidence/status | already present; enforce exact member subject |
| Known issue severity/impact | keep severity, add `impact` |
| Promotion blocked by missing evidence/blocking issues | fail-closed promotion validator |
| Experimental/lower resources retain warnings | explicit no-propagation invariant; do not rewrite TLHdig status |
| CI catches stale/missing IDs | exact check/subject/executor/member validation + workflow triggers |
| Documentation distinguishes claim layers | update compatibility/evidence docs |
