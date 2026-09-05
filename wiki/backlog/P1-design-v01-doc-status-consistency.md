# Design: v0.1 documentation status consistency

Issue: #16
Research: [`P1-research-v01-doc-status-consistency.md`](P1-research-v01-doc-status-consistency.md)

## Decision

Add one **derived documentation-consistency validator**. It reads the existing canonical registry and implementation tree, derives the v0.1 facts that high-level documents are allowed to claim, and checks a small set of visible bounded status summaries plus targeted stale-claim regressions.

Do **not** add another manually maintained status registry and do not generate whole narrative documents.

## Authority model

The validator derives facts from existing sources only:

| Fact | Authority |
| --- | --- |
| plugin aggregate verification | `registry/plugins.yaml` |
| Claude/Codex client verification | `registry/plugins.yaml` |
| TLHdig repository/ref/TF path | `registry/resources.yaml` |
| collection discovery mode | `registry/resources.yaml` |
| implemented scholarly skills | `plugins/*/skills/*/SKILL.md` |

Normative architecture remains authoritative for meaning. Historical reviews remain immutable and are not validated as current-status documents.

## New validator

Add:

```text
scripts/validate_release_documentation.py
```

with a pure callable:

```python
validate_release_documentation(root: Path = ROOT) -> list[str]
```

and a CLI that exits nonzero with one diagnostic per inconsistency.

### Derived fact shape

Internally, derive a small immutable structure equivalent to:

```python
ReleaseDocumentationFacts(
    plugin_statuses={
        "context-fabric": {"aggregate": "community", "claude": "community", "codex": "verified"},
        ...
    },
    skills=(
        "context-fabric/bhsa-research",
        ...
    ),
    tlhdig={
        "repository": "alexsosn/TLHdig-TF",
        "configured_ref": None,
        "tf_path": "tf/0.1.0",
    },
    collections={
        "bible": "indexed",
        "patristics": "indexed",
        "greek_literature": "indexed",
        "translatin-manif": "indexed",
    },
)
```

No values above are hard-coded as expected production state; the example merely describes current `main`.

### Skill discovery

Discover committed scholarly skills from:

```text
plugins/*/skills/*/SKILL.md
```

The validator should not import a test module as production configuration. `tests/test_skills.py` remains the stronger v0.1 skill-content contract; documentation consistency only needs the actual implemented set/count.

Repository-maintenance skills under `.agents/skills/` are excluded by construction.

## Visible machine-checkable summaries

Use short visible Markdown blocks delimited by stable comments. The comments make parsing robust while the content remains useful to readers.

### Shared verification/Phase-5 block

Documents that summarize current v0.1 implementation status use:

```markdown
<!-- BEGIN AGORA V0.1 STATUS -->
...visible Markdown summary derived from registry/tree facts...
<!-- END AGORA V0.1 STATUS -->
```

The validator compares the content between markers to a deterministic rendering from the derived facts. The block is deliberately compact and should state only:

- aggregate plugin verification state by plugin, or a common value only when all four are equal;
- Claude client-path state;
- Codex client-path state;
- implemented scholarly-skill count;
- distinction between implemented baseline and optional future guidance.

Use this block in:

- `README.md`;
- `wiki/releases/v0.1-plan-active.md`;
- `wiki/README.md`;
- `wiki/architecture/ref-implementation-details.md`.

The scope document is a release contract rather than a general status dashboard, so it does not need the full shared block.

### Scope runtime-facts block

`wiki/releases/v0.1-scope-frozen.md` gets a separate bounded block around the two implementation-sensitive scope facts:

```markdown
<!-- BEGIN AGORA V0.1 RESOURCE RUNTIME FACTS -->
...visible TLHdig source configuration and collection discovery summary...
<!-- END AGORA V0.1 RESOURCE RUNTIME FACTS -->
```

It is rendered from:

- TLHdig repository, configured ref or explicit “default branch / no configured ref”, and TF path;
- all v0.1 collection IDs and their discovery mode.

This prevents the scope from reverting to the old “path not pinned” or ordinary live Git-tree discovery descriptions when the registry says otherwise.

## Narrative corrections

The machine-checkable blocks do not excuse contradictory surrounding prose. Correct the existing release narrative as follows.

### `wiki/releases/v0.1-plan-active.md`

- Phase 3: replace ordinary dynamic Git-tree discovery language with commit-bound indexed discovery plus exact-revision regeneration/mismatch policy.
- Phase 4: change status from generic “Verified” to implemented with Codex paths live-verified and aggregate/Claude status Community.
- Phase 5: mark the v0.1 baseline implemented; enumerate the eight actual skill names/capability areas as completed. Additional source-specific guidance may remain follow-up work.
- Phase 6: remove the false statement that current plugin aggregate statuses are `verified`; state aggregate/client distinction explicitly.
- Current sequence: use the same terms as the shared status block; no `NEXT` for Phase 5.

### `wiki/releases/v0.1-scope-frozen.md`

- retain the already-correct TLHdig semantics: default branch, no configured immutable ref, fixed `tf/0.1.0` path;
- replace ordinary lazy Git-tree member discovery with indexed, revision-bound discovery;
- clarify current verification wording so “Verified” cannot be read as an aggregate claim for the current four plugins.

### `wiki/README.md`

- add the compact shared current-status block;
- rename/remove the misleading “Current P0 engineering findings” presentation. Preserve the historical review links and explain that those findings describe the reviewed snapshot; do not present already-closed items as current work;
- #9 may remain mentioned as the currently open governance blocker, but the validator must not depend on live GitHub issue state.

### `README.md`

The existing verification prose is already accurate. Add the bounded shared summary without expanding the README materially; keep the existing explanatory paragraphs.

### `wiki/architecture/ref-implementation-details.md`

- align collection language with index-first revision-bound discovery;
- remove completed snapshot-integrity/load-smoke work from the “next work” sentence;
- use the shared status block as the compact current-status authority inside this document.

## Targeted anti-regression checks

In addition to exact bounded-block validation, reject specific high-risk stale semantics in current-status documents.

At minimum:

1. `v0.1-plan-active.md` must not label Phase 5 `NEXT` or “next major implementation phase” while the discovered baseline skills are present.
2. It must not state that current aggregate plugin statuses are `verified` when registry aggregate statuses are weaker.
3. Scope/plan must not describe normal collection discovery as current/upstream Git-tree rescanning when all registered v0.1 collections are `indexed`.
4. Scope must not claim TLHdig has a configured immutable ref when the registry has none, nor claim the TF path is unknown/not pinned when `tf_path` is configured.
5. `wiki/README.md` must not retain the heading “Current P0 engineering findings” for the immutable 2026-08-29 review checklist.

These checks should be semantic enough to target demonstrated regressions, not a broad forbidden-word list. For example, references to Git-tree scanning remain legitimate when describing exact-revision index regeneration; only language presenting it as the normal current discovery path is stale.

## Test plan / TDD slices

### RED1 — derived status blocks and canonical-source mutation

Add `tests/test_release_documentation_consistency.py` with temp-root fixtures copied from the relevant canonical files/docs.

Required RED assertions:

- current docs fail because the new bounded blocks/validator do not yet exist;
- changing one plugin aggregate/client status in the copied registry changes the expected documentation and is detected without editing a hard-coded expected status in the validator;
- adding/removing a copied scholarly skill changes the expected skill count/set and is detected.

GREEN1:

- implement fact derivation and shared block validation;
- insert accurate shared blocks in README, plan, wiki index, implementation details.

### RED2 — TLHdig and collection runtime facts

Required RED assertions:

- changing copied TLHdig `tf_path` causes scope validation failure;
- adding/removing a configured TLHdig `ref` changes the expected scope summary;
- changing a collection `discovery` value away from `indexed` changes the expected scope facts;
- current stale Git-tree prose is rejected when registry says indexed.

GREEN2:

- implement resource/runtime block validation;
- correct scope and Phase 3 collection prose.

### RED3 — historical stale statements

Required RED assertions mutate corrected docs back to:

- Phase 5 `NEXT`;
- current plugin statuses `verified`;
- “Current P0 engineering findings”.

GREEN3:

- targeted narrative anti-regression checks;
- final plan/wiki cleanup.

## CI integration

Foundation gets a named step after canonical registry validation:

```yaml
- name: Validate release documentation consistency
  run: python scripts/validate_release_documentation.py
```

The full unit suite remains the mutation/regression proof; the named step makes current-doc trust status visible as a first-class CI gate.

No network access is needed.

## Failure behavior

The validator must:

- fail closed when required canonical files or bounded blocks are missing;
- report the document and mismatched fact/block;
- never rewrite files during validation;
- avoid silently normalizing an unknown/mixed status into a stronger summary.

When plugin statuses differ, render them per plugin rather than inventing a common status. A common aggregate/Claude/Codex summary is allowed only when all four values are actually identical for that dimension.

## Compatibility and ownership

This work changes only repository documentation and Agora-owned trust/CI plumbing. It does not alter any plugin's runtime or scholarly semantics.

Historical review documents are intentionally excluded from validation because they are evidence about prior repository states and must not be rewritten to look current.

## Exit criteria

The implementation is ready for independent review only when:

1. all #16 acceptance criteria are represented by a regression test or named validator contract;
2. Foundation is green on the exact PR head;
3. `README.md`, scope, plan, wiki index, and implementation-details current-status wording agree with canonical derived facts;
4. no second manually maintained status source was introduced;
5. independent exact-head review confirms the validator cannot pass while any of the demonstrated high-level overclaims remain.
