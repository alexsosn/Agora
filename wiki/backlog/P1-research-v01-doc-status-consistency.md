# Research: v0.1 documentation status consistency

Issue: #16 — **P1: Reconcile v0.1 plan/scope documentation with the current registry and implementation**

## Question

Which current high-level v0.1 documents contradict Agora's canonical registry or implemented repository state, and what machine-checkable facts are stable enough to prevent the same trust/status drift from recurring?

This is a documentation-integrity problem, not an invitation to create another manually maintained release-status source of truth. The authoritative facts should remain in the registry, implementation tree, and normative architecture references.

## Sources inspected

The audit was performed against `main` at merge commit `6953bd5502f056025dc31c630f14bfeec18ad9de` after issue #14 / PR #59.

Primary sources:

- `registry/plugins.yaml` — canonical plugin aggregate/client verification state;
- `registry/resources.yaml` — canonical TLHdig-TF source configuration and collection discovery configuration;
- `plugins/*/skills/*/SKILL.md` and `tests/test_skills.py` — implemented/required v0.1 scholarly skills;
- `wiki/architecture/ref-context-fabric-collections.md` — current collection-index architecture;
- `README.md`;
- `wiki/README.md`;
- `wiki/releases/v0.1-scope-frozen.md`;
- `wiki/releases/v0.1-plan-active.md`;
- `wiki/architecture/ref-implementation-details.md`;
- `tests/test_architecture_review_contracts.py`;
- `.github/workflows/foundation.yml`.

## Canonical facts on current `main`

### Plugin verification is client-scoped

All four v0.1 plugins currently have the same status shape in `registry/plugins.yaml`:

| Plugin | Aggregate | Claude | Codex |
| --- | --- | --- | --- |
| Context-Fabric | `community` | `community` | `verified` |
| Perseus | `community` | `community` | `verified` |
| Sefaria | `community` | `community` | `verified` |
| SEDRA | `community` | `community` | `verified` |

The Codex entries reference live checks. Claude entries have deterministic manifest/configuration evidence but no equivalent live client-path check. `tests/test_architecture_review_contracts.py` already enforces that aggregate status cannot exceed the weakest client status.

Therefore high-level prose such as “the plugins are Verified” or “current plugin statuses are verified” is incorrect. The accurate summary is: **Codex paths are live-verified; Claude paths and aggregate plugin statuses are community**.

### TLHdig-TF follows the default branch; only its TF path is fixed

Current `registry/resources.yaml` says:

```yaml
id: TLHdig-TF
upstream:
  repository: alexsosn/TLHdig-TF
  tf_path: tf/0.1.0
acquisition:
  strategy: repository
  lazy: true
  notes: Follow the upstream default branch so rebuilt tf/0.1.0 datasets are picked up without changing the version label.
```

There is no configured immutable `ref`. Runtime tests already assert `ref is None` and `tf_path == "tf/0.1.0"`.

The issue text describes an older contradiction in which the scope allegedly said the path/version was “not pinned in Phase 1” while the implementation pinned a specific commit. That exact contradiction no longer exists on current `main`; both parts of that statement are stale. `wiki/releases/v0.1-scope-frozen.md` now correctly says `tf/0.1.0` is selected explicitly while the repository follows its default branch.

The consistency contract should therefore be derived from the current registry rather than hard-coding the historical issue wording.

### Phase 5's planned v0.1 skills are implemented

`tests/test_skills.py` defines and CI-enforces eight required v0.1 research skills, all of which exist:

1. `context-fabric/context-fabric-research`;
2. `context-fabric/bhsa-research`;
3. `context-fabric/cuc-ugaritic-research`;
4. `context-fabric/tlhdig-hittite-research`;
5. `context-fabric/greek-collections-research`;
6. `perseus/perseus-research`;
7. `sefaria/sefaria-research`;
8. `sedra/sedra-research`.

These correspond directly to the eight subsections that `wiki/releases/v0.1-plan-active.md` still presents as future Phase 5 work. Calling the phase “next major implementation phase” or `NEXT` is therefore false.

`wiki/architecture/ref-implementation-details.md` is closer to reality: it says eight skills are implemented and CI-validated, while leaving room for additional resource-specific guidance. The release plan should use the same distinction: **the planned v0.1 Phase 5 baseline is implemented; additional guidance is incremental follow-up, not an unstarted phase**.

### Collection discovery is now index-first and revision-bound

Current collection resources use:

```yaml
collection:
  discovery: indexed
  member_index: registry/collections/<collection>.yaml
```

for the four v0.1 collection resources. `wiki/architecture/ref-context-fabric-collections.md` documents committed complete indexes bound to immutable `source_revision`s, index-first list/search/prepare behavior, and exact-revision local regeneration only when a requested/current revision is not represented by the bundled index.

Two high-level documents are stale:

- `wiki/releases/v0.1-scope-frozen.md` says Agora discovers current members lazily from upstream Git tree metadata;
- `wiki/releases/v0.1-plan-active.md` still lists “dynamic discovery of current TF dataset roots in `pthu/greek_literature`” as the implementation state.

Those statements describe the pre-#13 implementation. The current model is **committed/indexed discovery with revision-bound regeneration as a mismatch policy**, not rescanning the Git tree for ordinary list/search/prepare calls.

### README verification wording is already substantially correct

Current `README.md` explicitly says:

- the four v0.1 integrations have live **Codex-path** verification;
- aggregate plugin status remains `community`;
- Claude paths have deterministic configuration evidence rather than equivalent live client-path evidence;
- provider/service health, plugin/client evidence, and resource/data status are separate dimensions.

This should be treated as the current user-facing terminology baseline rather than rewritten around the issue's older phrasing.

The README does not currently claim an exact skill count, so the issue's statement that it “states eight skills are already implemented” is also stale. The count is nevertheless independently established by the implementation tree and `tests/test_skills.py`.

## Current contradictions

### `wiki/releases/v0.1-plan-active.md`

Materially stale statements include:

1. Phase 4 status: `implemented and Verified` — overstates aggregate status and does not scope verification to Codex.
2. Phase 5 status: `next major implementation phase` — all eight listed baseline skills exist.
3. Current sequence: `Phase 4 ... ✓ verified integrations` — same aggregation problem.
4. Current sequence: `Phase 5 scholarly skills NEXT` — false.
5. Phase 6: `The current v0.1 plugin statuses in registry/plugins.yaml are therefore verified.` — directly contradicts the canonical registry.
6. Phase 3: dynamic Git-tree discovery for Greek literature — superseded by commit-bound indexes.
7. The introduction's generic wording “A Verified plugin ...” is not itself false, but should not imply that any current aggregate plugin has that state.

### `wiki/releases/v0.1-scope-frozen.md`

The TLHdig-TF block is already correct on current `main` and should remain derived from the registry facts: default branch + `tf/0.1.0`.

The collection section is materially stale because it says ordinary member discovery is lazy Git-tree scanning. It should describe indexed, revision-bound member discovery while preserving the marketplace-vs-runtime granularity rule.

The verification-policy section is generic rather than directly false, but can be made consistent with the current aggregate/client distinction so readers cannot infer a stronger current claim.

### `wiki/README.md`

The “Current P0 engineering findings” list is historical but presented as current. Several entries are already completed:

- immutable/revision-addressed Context-Fabric materialization;
- collection snapshot continuity;
- representative load evidence;
- README verification reconciliation;
- executable verification evidence.

The only listed governance item still open is branch protection (#9). Keeping completed findings under a “Current” heading makes the wiki index contradict current implementation status even if each historical review remains correctly immutable.

The correct pattern is to preserve links to historical reviews while making the index describe current open work, not restate obsolete review priorities as active state.

### `wiki/architecture/ref-implementation-details.md`

This file is mostly aligned with current verification and skill facts, but two phrases are stale:

- it still describes collection members as “discovered at member level” / a changing set without stating the current committed index-first model;
- its final paragraph says the next highest-priority work includes Context-Fabric snapshot integrity and representative corpus-load evidence, both of which have since been implemented.

Because README points readers here for “current implementation status,” leaving these stale would preserve a second contradiction after fixing the release plan.

## Existing safeguards and gap

Existing tests already protect several underlying facts:

- `test_architecture_review_contracts.py` enforces the TLHdig source configuration and aggregate-status ≤ weakest-client rule;
- `test_skills.py` enforces the eight v0.1 skill files and their core contracts;
- collection-index tests enforce `discovery: indexed`, commit-bound indexes, and runtime mismatch behavior;
- Foundation runs the full unit suite.

What is missing is a link from those canonical facts to the high-level documents. A registry or implementation change can therefore leave prose stale while every existing test stays green.

## Consistency-check design options

### Option A — literal phrase tests only

Add unit tests such as “plan must not contain `NEXT`” and “plan must contain `aggregate ... community`.”

Advantages:

- smallest implementation;
- catches today's exact regressions.

Disadvantages:

- brittle wording coupling;
- does not derive expectations from registry/tree state;
- easy for semantically contradictory prose to survive under different wording;
- future legitimate status changes require editing both source data and hard-coded test expectations.

This is insufficient as the primary design.

### Option B — add a second manually maintained release-status YAML

Create a release-status file and validate docs against it.

Advantages:

- structured and easy to render.

Disadvantages:

- creates another source that can itself disagree with `registry/plugins.yaml`, `registry/resources.yaml`, or the skill tree;
- violates the issue's central objective by moving drift rather than removing it.

Reject.

### Option C — derive release-documentation facts and validate explicit status blocks

Create a small validator that derives facts from existing authoritative sources:

- plugin aggregate/client statuses from `registry/plugins.yaml`;
- TLHdig configured `ref`/`tf_path` from `registry/resources.yaml`;
- collection discovery modes from `registry/resources.yaml`;
- implemented required skills from the existing v0.1 skill contract / filesystem.

High-level documents contain concise, explicitly delimited status summaries/tables. The validator parses those bounded summaries and compares them to derived facts. It additionally rejects the known contradictory legacy statements in the surrounding release prose (`Phase 5 ... NEXT`, aggregate “plugin statuses ... verified”, ordinary dynamic Git-tree discovery wording).

Advantages:

- canonical state remains in existing registry/implementation sources;
- failures explain which document fact drifted;
- future registry status changes automatically change the expected documentation facts;
- focused enough to avoid turning all prose into generated content;
- tests can mutate canonical data and documentation independently to prove both directions.

Disadvantages:

- bounded markers/status blocks are a small documentation convention;
- semantic prose outside the block still needs a few targeted anti-regression checks for known high-risk contradictions.

This is the strongest fit for #16.

### Option D — fully generate all release-status prose

Generate large sections of README/plan/scope/wiki index from registry/tree state.

Advantages:

- strongest mechanical consistency.

Disadvantages:

- over-engineers a small trust layer;
- makes narrative release planning awkward;
- generated prose would still need human-maintained context around it;
- increases generator surface for limited value.

Not justified for v0.1.

## Recommended direction

Use **Option C**: one small repository validator deriving authoritative facts from the canonical registry and the existing skill/collection implementation contracts, with bounded machine-checkable status summaries in the high-level docs and targeted checks for the exact known stale statements.

The validator should be called by Foundation directly rather than relying only on incidental unit discovery, so documentation consistency is a named CI gate.

The implementation should not copy verification state into another registry. It should also avoid requiring exact narrative wording beyond explicit status fields/markers and the specific regressions demonstrated by #16.

## Scope for implementation

In scope:

- correct current state in `README.md`, `wiki/README.md`, `wiki/releases/v0.1-plan-active.md`, `wiki/releases/v0.1-scope-frozen.md`, and the current-status portions of `wiki/architecture/ref-implementation-details.md` where they contradict canonical facts;
- add a derived documentation-consistency validator;
- add focused mutation/regression tests;
- add a named Foundation CI step.

Out of scope:

- rewriting historical review documents; they should remain immutable records of the state they reviewed;
- changing plugin/resource verification statuses merely to simplify prose;
- changing TLHdig source pinning policy;
- changing collection runtime behavior;
- implementing new scholarly skills;
- fixing branch protection (#9), licensing audit (#17), platform coverage (#18), or resource/member evidence (#19).

## Research conclusion

Issue #16 is valid but its motivating examples have partially aged. The current defects are broader than the original TLHdig example and narrower than a general documentation rewrite. Agora already has authoritative machine-readable/runtime facts; it lacks only a consistency bridge from those facts to its high-level status documents.

The next gate should design that bridge so current status prose cannot silently exceed or contradict canonical verification, source-configuration, collection-discovery, or implemented-skill state.
