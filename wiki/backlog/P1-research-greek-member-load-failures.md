# Research: Greek collection members that cannot load

Issue: #47 — **`greek_literature` members with duplicate structure levels crash `load_corpus` with an unhandled `ValueError`**

## Question

What part of #47 belongs in Agora, how can Agora identify affected collection members without taking ownership of Context-Fabric or corpus semantics, and what evidence is strong enough to change discovery and verification claims?

## Sources inspected

The investigation used Agora `main` at `6953bd5502f056025dc31c630f14bfeec18ad9de` and the exact `greek_literature` index snapshot `77d85bf71fc6f689f7faedc255666a2609ffe590`.

Primary Agora sources:

- `AGENTS.md`;
- `CONTRIBUTING.md`;
- `wiki/architecture/ref-plugin-boundary.md`;
- `registry/resources.yaml`;
- `registry/collections/greek_literature.yaml`;
- `plugins/context-fabric/src/agora_context_fabric/collection_index.py`;
- `plugins/context-fabric/src/agora_context_fabric/resolver.py`;
- `plugins/context-fabric/src/agora_context_fabric/service.py`;
- `plugins/context-fabric/src/agora_context_fabric/catalog.py`;
- `scripts/generate_context_fabric_collection_indexes.py`;
- collection-index regression tests.

Upstream sources:

- `Context-Fabric/context-fabric` at repository commit `3a38ca80e617d872ce1664e0f0740486d0e7e8ac`;
- `pthu/greek_literature` at `77d85bf71fc6f689f7faedc255666a2609ffe590`.

## Reproduction and ownership

The failure is upstream and reproduces with no Agora code in the stack. A failing member such as

`canonical-greekLit/tlg0001/tlg001/perseus-grc2/1/tf/1.0`

contains in `otext.tf`:

```text
@structureFeatures=_book,book,card,card,_sentence,_phrase
@structureTypes=_book,book,card,card,_sentence,_phrase
```

Current Context-Fabric detects this in `libs/core/cfabric/precompute/prepare.py::structure()`:

```python
sTypes = set(sTypeList)
if len(sTypes) != nsTypes:
    error("WARNING: duplicate structure levels")
    return ({}, {})
```

`libs/core/cfabric/navigation/text.py` later treats any non-null `structure.data` as a six-item tuple:

```python
(
    self.hdFromNd,
    self.ndFromHd,
    self.hdMult,
    self.hdTop,
    self.hdUp,
    self.hdDown,
) = structure.data if structure else (None, None, None, None, None, None)
```

The malformed corpus declaration and the resulting internal tuple-unpack crash therefore both exist without Agora. Per the normative plugin boundary, Agora must not repair either one by rewriting `otext.tf`, monkey-patching Context-Fabric, or substituting structure semantics.

Agora does own what it advertises about the resource and member, how collection discovery presents known integration failures, and whether a known-bad member is allowed to pay acquisition/compile cost before a predictable failure is reported.

## The affected set is broader than the original 2/10 sample

The issue correctly warns against extrapolating from the first ten members. Static inspection of the exact upstream snapshot already establishes that the defect is not limited to those two examples.

Repository search finds repeated `card,card` declarations in the first failing Apollonius member, the sampled Euripides `tlg0006/tlg009` member, and additional Perseus members. It also finds repeated `section,section` declarations across both `canonical-greekLit` and `First1KGreek`, including examples whose `@structureTypes` explicitly repeat `section`.

The right affected-set calculation is therefore not a hand-maintained list inferred from the sample or from one repeated token. It should inspect every indexed member's exact `otext.tf` metadata and apply the Context-Fabric precondition generically: `structureTypes` is invalid when the comma-separated level names are not unique.

## The requested 1,779-member batch load sweep should be rescoped

Issue #47 asks for a batch load of all 1,779 members. That is poor evidence for an Agora change for two reasons.

First, measured member loads in the issue take roughly 20–33 seconds for many members. An exhaustive load sweep would take many hours and could create large compiled caches. Second, Agora's architecture explicitly says its tests must not become a third-party semantic regression suite.

The duplicate-level condition is present in small `otext.tf` metadata and is exactly the precondition Context-Fabric checks before the crash. Agora can therefore audit all 1,779 members at the immutable collection revision without loading or compiling them. The exhaustive gate should be:

1. inspect every indexed member's `otext.tf` header at the exact source revision;
2. classify duplicate `structureTypes` as a blocking known integration issue for that member;
3. keep one representative direct-load failure as smoke evidence that the signature still matches current upstream behavior.

This is stronger for marketplace discovery than a one-time multi-hour sweep: the result is reproducible from the commit-bound source metadata and can be regenerated with the collection index.

## Existing collection-index architecture is the right place to derive member evidence

The committed collection indexes are already the low-cost discovery surface. They are bound to immutable revisions and already carry member-level:

- `verification.status`;
- `verification.evidence` check IDs;
- `verification.notes`.

`CollectionIndexManager` currently reads `_book.tf` metadata only to derive author/title/canonical identity. `GitStore.tf_header_metadata()` can read Text-Fabric header metadata from the Git snapshot without materializing the corpus. The index generator already resolves every collection at the configured immutable revision.

The narrow extension is to read `otext.tf` metadata while generating an index, apply non-semantic structural sanity checks whose failure is already defined by upstream loader requirements, and persist machine-readable known-issue metadata in the member index.

This keeps ordinary `list_collection_members` cheap: it reads the committed index rather than probing 100 upstream blobs per page.

## Resource-level and member-level presentation

Current `registry/resources.yaml` gives `greek_literature` `verification: {status: community}` with no integration issue. `describe_available_corpus` therefore gives no warning that known members cannot load.

Current member output already has a verification object but no known-issue field. A member known to fail should not remain indistinguishable from an untested community member.

The data model needs two layers:

- a collection-level machine-readable issue describing the failure class and pointing callers to affected member verification;
- a member-level blocking issue/evidence entry on each member whose exact snapshot metadata violates the duplicate-structure-level condition.

The collection should not be globally marked unusable merely because some members are bad. Its aggregate status should be worded at the granularity supported by member evidence.

## Load behavior

A known affected member should fail before full materialization and before calling Context-Fabric. This is marketplace/resource-selection behavior, not a semantic workaround: Agora is declining to launch a resource that its own committed verification evidence says is incompatible with the pinned upstream loader contract.

The error should identify:

- collection ID;
- member ID;
- known-issue ID;
- the source revision on which the classification is based;
- the upstream failure class (`duplicate structure levels`);
- where to look for the upstream report when a report URL is available.

It must not claim that Agora knows how the duplicate levels should be corrected.

A stale classification must fail closed against its evidence revision: member known-issue data from one source revision must never silently block or bless a different revision.

## Upstream reporting attempt

Two ready-to-file reports were prepared:

1. Context-Fabric: duplicate structure levels return a two-item structure result that is later unpacked as six values, producing an internal `ValueError` instead of a clear invalid-corpus diagnostic or deliberate no-structure fallback.
2. `pthu/greek_literature`: generated `otext.tf` files contain duplicate structure level names (`card,card`, `section,section`, and potentially other repetitions) and should be regenerated from the conversion source with valid structure metadata.

The connected GitHub integration has read access to both repositories but returned HTTP 403 (`Resource not accessible by integration`) when asked to create either issue. Agora must not fabricate upstream issue URLs. The PR can preserve these report texts and source links, but the acceptance criterion requiring actual upstream issue links remains externally blocked until an account with write permission files them.

## Design options

### Option A — catch `ValueError` from the loader and rewrite the message

This improves the final error but still downloads/materializes the member first, cannot mark it during discovery, and risks conflating unrelated upstream `ValueError`s with this defect.

Reject as the primary design.

### Option B — inspect `otext.tf` dynamically on every list/load call

This can detect the condition before full materialization, but listing a page could trigger dozens of Git blob reads or lazy network fetches. It defeats the commit-bound index's purpose as cheap discovery and creates runtime behavior that varies with connectivity.

Reject for normal discovery. A load-time defensive recheck of committed evidence is acceptable if bounded.

### Option C — derive member known issues during collection-index generation

Extend the existing revision-bound generator so every member's `otext.tf` header is audited once while building the complete index. Persist the resulting verification/known-issue metadata in the canonical and bundled index. Runtime listing is then pure index access; prepare/load can refuse a member whose committed issue is blocking before materialization.

This is the best fit.

### Option D — hard-code the sampled member IDs

This would immediately fix two examples while leaving the same known failure elsewhere and would turn a source-derived property into manual marketplace folklore.

Reject.

## Recommended direction

Use Option C.

The implementation should:

- extend the collection-index member model with structured known issues;
- make index generation read `otext.tf` header metadata at the exact revision and classify duplicate `structureTypes` generically;
- add a collection-level known issue to `greek_literature` and surface it from `describe_available_corpus`;
- mark affected members in `list_collection_members` through committed index metadata;
- make prepare/load reject a member with a blocking compatibility issue before corpus materialization, with an actionable error;
- preserve normal behavior for unaffected members and for all other collections;
- add one expected-known-failure smoke/evidence record rather than an exhaustive semantic load suite;
- never rewrite structure metadata or Context-Fabric behavior.

## TDD gates to carry into design

The implementation should be sliced so tests fail before each production change:

1. **RED1 — index classification:** a synthetic member whose `otext.tf` has duplicate structure types is not currently marked blocking; a valid member remains unchanged.
2. **GREEN1 — source-derived member issue:** derive and serialize/deserialize the issue without changing valid index output.
3. **RED2 — discovery/resource presentation:** current service output has no structured known-issue data for affected members/collection.
4. **GREEN2 — public metadata:** surface resource and member issue data while retaining existing verification fields.
5. **RED3 — pre-materialization guard:** a known-blocked member currently reaches `GitStore.materialize` / loader.
6. **GREEN3 — fail early:** reject it using exact-revision index evidence; prove materialization and loader were not called.
7. **RED4/GREEN4 — committed evidence:** regenerate the Greek collection index at its pinned source revision, bundle it exactly, and assert at least the two independently reproduced members are classified while a known-good Iliad member is not.
8. **Integration validation:** registry validation, collection-index reproducibility, full Foundation, and a bounded representative upstream smoke.

## Exit criteria for the Agora PR

The Agora implementation can be technically complete once its own contracts and exact-snapshot evidence are green and independently reviewed. It should not claim the two upstream-report ACs complete until real issue URLs exist. If those URLs cannot be created through the available integration, record that as an explicit external blocker rather than inventing links or weakening the boundary.