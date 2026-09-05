# Design: known-bad Context-Fabric collection members

Issue: #47
Research: `wiki/backlog/P1-research-greek-member-load-failures.md`

## Goal

Make an immutable collection snapshot capable of saying that specific members are known to violate a published upstream loader precondition, surface that fact during Agora discovery, and reject those members before expensive materialization while leaving the upstream corpus and Context-Fabric behavior untouched.

The first use is duplicate `structureTypes` in `greek_literature`, but the data model must not hard-code Greek member IDs into runtime code.

## Boundary

Agora will classify and expose compatibility evidence derived from source metadata. It will not:

- rewrite `otext.tf`;
- choose which duplicate structural level should be renamed or removed;
- monkey-patch Context-Fabric;
- suppress or reinterpret valid Context-Fabric output;
- add an alternative structure algorithm;
- build an exhaustive semantic regression suite for the upstream corpus.

## Data model

### Resource issue definitions

Extend the resource `verification` object with optional `known_issues` definitions:

```yaml
verification:
  status: community
  known_issues:
    - id: context-fabric/duplicate-structure-levels
      severity: blocking
      signature: duplicate-structure-levels
      summary: Some collection members declare duplicate structureTypes and cannot be loaded by the supported Context-Fabric release.
      upstream:
        - repository: Context-Fabric/context-fabric
        - repository: pthu/greek_literature
```

Schema:

- `id`: stable string, pattern `^[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*$`;
- `severity`: `advisory` or `blocking`;
- `signature`: stable machine token, not an exception-message parser;
- `summary`: concise user-facing explanation;
- `upstream`: optional repository references; `issue_url` is optional and must be present only when a real upstream issue exists.

Keep the existing legacy `integration_issues: [string]` field unchanged for compatibility. This PR does not migrate unrelated resources.

### Member issue references

Extend collection-index member verification with issue references:

```yaml
verification:
  status: community
  known_issues:
    - issue_id: context-fabric/duplicate-structure-levels
```

The member index stores references rather than repeating summaries for every affected member. The index's immutable `source_revision` is the evidence revision.

`CollectionIndexMember` and `CollectionMember` gain `verification_known_issues: tuple[str, ...]`.

Serialization must round-trip references exactly. Existing indexes with no `known_issues` remain byte-for-byte unchanged when regenerated unless source-derived classification finds an issue.

### Public output

`describe_available_corpus` returns `verification.known_issues` from the resource definition.

`list_collection_members` returns, for every member:

```json
{
  "verification": {
    "status": "community",
    "evidence": [],
    "notes": [],
    "known_issues": [
      {
        "id": "context-fabric/duplicate-structure-levels",
        "severity": "blocking",
        "signature": "duplicate-structure-levels",
        "summary": "...",
        "upstream": [...]
      }
    ]
  }
}
```

The service resolves compact member references through the collection's resource definitions. Unknown member issue references are a configuration error, not silently discarded.

This satisfies discovery without adding a new filtering API in #47. Filtering can be added later if demand justifies it.

## Source-derived classification

### Header acquisition

`CollectionIndexManager._metadata_for()` currently reads `_book.tf` to derive display metadata. Extend it to also read `<tf_path>/otext.tf` using the existing `GitStore.tf_header_metadata()` path at the same immutable revision.

Only Text-Fabric header metadata is read. No corpus materialization or compilation occurs.

Merge these keys into the metadata supplied to `build_collection_index()`:

- existing `_book.tf` metadata;
- `structureTypes` and `structureFeatures` from `otext.tf` when present.

A missing or unreadable `otext.tf` should preserve current index generation behavior; #47 does not turn unrelated metadata absence into a new blocker.

### Duplicate-level classifier

Add one pure helper:

```python
def duplicate_structure_levels(metadata: Mapping[str, str]) -> bool:
    raw = metadata.get("structureTypes")
    if not raw:
        return False
    levels = [value.strip() for value in raw.split(",") if value.strip()]
    return len(levels) != len(set(levels))
```

This mirrors the upstream precondition without deciding any scholarly semantics.

When true, `build_collection_index()` adds the stable member issue reference `context-fabric/duplicate-structure-levels`.

The classifier is generic across collection resources. If another committed collection contains the same source defect, regeneration will reveal it rather than silently restricting the check to Greek IDs.

## Validation

Add registry validation for resource known issues:

- IDs unique within one resource;
- member issue references in committed indexes resolve to a known issue defined by that collection resource;
- blocking/advisory severity comes from the resource definition, not duplicated member metadata;
- optional `issue_url` must be a valid URI when present.

Do not add a promotion policy in this PR; issue #19 owns the broader relationship between evidence, known-issue severity, and verification promotion.

## Prepare/load guard

For a collection member, `ContextFabricResolver.prepare()` already resolves the exact index entry before `GitStore.materialize()`.

Insert the guard after member lookup and before materialization:

1. resolve the member's issue IDs against `ResourceSpec.verification_known_issues`;
2. select any issues with `severity == "blocking"`;
3. if one or more exist, raise a dedicated `KnownMemberIssueError` containing resource ID, member ID, source revision, and resolved issue metadata;
4. do not call `materialize()`.

`ContextFabricService`/MCP boundary may allow the exception to become a tool error, but the message must be actionable and stable. Do not catch arbitrary upstream `ValueError` and guess that it is this defect.

The guard is revision-safe because both member issue references and member selection come from the same resolved immutable collection index.

## Expected-known-failure smoke

The repository already has representative Context-Fabric smoke infrastructure. Extend it with one bounded Greek expected-known-failure case for:

`canonical-greeklit-tlg0001-tlg001-perseus-grc2-1-62c8ed02`

The Agora smoke should assert the **Agora-owned** contract: discovery marks the member blocking and prepare refuses it before materialization. It should not repeatedly compile the upstream corpus merely to prove Context-Fabric remains broken.

A separately runnable/manual upstream diagnostic can retain the direct Context-Fabric reproduction for maintainers. When an upstream fix and regenerated corpus remove the duplicate declaration, collection-index regeneration should remove the member issue and make the Agora regression fail, prompting retirement of the known issue.

## Generated artifacts

`registry/collections/greek_literature.yaml` is canonical and the installed plugin bundles an exact copy at `plugins/context-fabric/resources/collections/greek_literature.yaml`.

After GREEN classifier code exists:

```bash
python scripts/generate_context_fabric_collection_indexes.py --resource greek_literature
python scripts/generate_context_fabric_catalog.py
```

Then verify:

```bash
python scripts/generate_context_fabric_collection_indexes.py --resource greek_literature --check
python scripts/generate_context_fabric_catalog.py --check
python scripts/validate_registry.py
```

The regenerated index, rather than a manually edited member list, is the authoritative affected set.

## TDD sequence

### RED1 — classification and round-trip

Add synthetic collection-index tests proving current code fails to:

- classify repeated `structureTypes`;
- serialize/deserialize a member issue reference;
- leave unique/missing structure metadata unclassified.

Commit RED evidence before production changes.

### GREEN1 — index evidence

Implement header merge, pure duplicate classifier, member issue field, and serialization. Run focused collection-index tests.

### RED2 — resource/member public model

Add tests that resource known-issue schema/parsing and member public output are absent on current production code; add a validation test for a dangling member issue reference.

### GREEN2 — discovery

Implement resource schema/catalog parsing, service enrichment, and validation. Add the `greek_literature` resource issue definition with no fabricated `issue_url`.

### RED3 — load guard

Construct a synthetic collection index with a blocking member issue and a store spy. Assert current `prepare()` calls materialization or otherwise fails to provide the required known-issue error.

### GREEN3 — fail before cost

Add `KnownMemberIssueError` and resolver guard. Assert no materialization occurs; unaffected members prepare normally.

### RED4/GREEN4 — exact committed snapshot

Regenerate the canonical Greek index from `77d85bf71fc6f689f7faedc255666a2609ffe590`, regenerate the installed catalog/index bundle, and add committed-evidence tests that:

- the two independently reproduced members carry `context-fabric/duplicate-structure-levels`;
- a known-good Homer Iliad member does not;
- every member issue reference resolves;
- canonical and bundled indexes are identical;
- regeneration is reproducible at the configured revision.

The exact affected count is reported from this generated output. No rate is extrapolated from the original first-ten sample.

### Final validation

Run focused unit tests, registry validation, collection-index/catalog freshness checks, and Foundation on the exact PR head.

Then run an independent `agora-pr-review` + `agora-plugin-review` against the actual diff. Any blocker starts a new RED regression test/fix/retest/re-review cycle.

## Upstream issue links

The GitHub integration returned HTTP 403 for both upstream create-issue attempts. The resource metadata therefore records upstream repositories but no issue URLs. The PR description and #47 must explicitly state that these two acceptance criteria are externally blocked. If real issue URLs are supplied before merge, add them and validate them; never invent placeholder links.