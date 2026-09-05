# Greek Text-Fabric Collection Handling

Several Text-Fabric repositories do not behave like ordinary single-corpus repositories. In particular, repositories such as `pthu/greek_literature` contain many independent Text-Fabric corpora, typically one work/text per corpus directory.

Agora treats this as a first-class collection model rather than flattening every internal work into a marketplace plugin.

## Design rule

**Marketplace granularity and Text-Fabric runtime granularity are different.**

At the marketplace level:

- `pthu/greek_literature` is one Context-Fabric resource of type `collection`;
- the collection is installed/discovered through the single `context-fabric` plugin;
- individual works are not top-level Agora plugins and do not appear as thousands of marketplace entries.

At the runtime level:

- each individual work remains a separately loadable Text-Fabric corpus;
- Agora discovers, addresses, acquires, caches, and loads collection members independently;
- Context-Fabric MCP is pointed at the selected member corpus, not an artificial merged corpus unless an upstream collection explicitly supports that.

## Registry and index model

Collection resources use metadata distinct from ordinary corpus resources. The normal v0.1 shape is:

```yaml
id: greek_literature
plugin: context-fabric
provider: context-fabric
kind: collection
upstream:
  repository: pthu/greek_literature
collection:
  discovery: indexed
  member_id_scheme: stable-relative-id
  lazy_members: true
  member_index: registry/collections/greek_literature.yaml
```

The committed member index is bound to one immutable upstream commit with `source_revision`. Each member records a stable Agora member ID, version-independent identity path, exact loadable TF path, language and member-level verification status. Where the same-revision upstream TF metadata establishes them, an index may additionally record:

- author;
- work title;
- canonical/CTS or provider identifier;
- explicit edition identifier;
- member verification evidence or integration notes.

These semantic fields are **never inferred from arbitrary repository path positions**. A path such as `Archive/Volume` is not interpreted as author/work merely because it has two components. If the upstream snapshot provides no authoritative semantic metadata, Agora exposes the neutral stable member ID and repository-relative identity/load paths instead.

The member ID is independent of the local checkout path and of the TF version directory. Stable upstream identifiers such as CTS/provider IDs are preserved separately rather than silently replacing the Agora member ID.

The canonical files live under `registry/collections/`. Installed Context-Fabric packages carry generated, lossless copies under `plugins/context-fabric/resources/collections/`; those copies are not a second editable source of truth.

## Commit-bound generation and mismatch policy

The four v0.1 collections have committed `complete` indexes tied to explicit source revisions. `discovery: indexed` is valid only with such a complete, revision-bound index.

For a request whose resolved upstream revision matches the bundled index, list/search/prepare use that index directly and do not rescan the upstream Git tree. This is the normal fast path.

Agora must also preserve the snapshot semantics of collection `source_revision`:

- if a caller pins an exact historical commit already available in the local repository, Agora uses or generates an index for exactly that commit;
- if current upstream state has advanced beyond the committed index revision, Agora may generate a new local exact-revision index;
- generated local indexes are cached by collection ID plus immutable source revision and reused by later list/search/prepare operations;
- an unavailable pinned revision fails closed; Agora never substitutes current upstream state while echoing the requested revision.

Generating a missing exact-revision index may scan Git tree metadata once and read small same-revision TF metadata headers. Subsequent operations use the revision-bound cached index rather than rescanning the collection on every request.

Committed indexes are produced by `scripts/generate_context_fabric_collection_indexes.py`. Generation uses the same runtime index builder, so stable IDs, version selection and metadata rules do not have a separate CI-only implementation.

## Discovery and snapshot consistency

Agents can search collection members before loading one. `list_collection_members` supports search over the metadata actually present in the index, including:

- author and work title where source-backed;
- canonical/provider identifiers where present;
- explicit edition identifiers where present;
- Agora member ID;
- version-independent identity path;
- exact repository-relative TF load path.

For example, the committed Greek-literature index contains provider-authored metadata for the Perseus Iliad member, so `Homer`, `Iliad`, its TLG/provider identifier, or its repository path can find it. Search does not invent a human label for members whose upstream metadata does not supply one.

Member responses expose the identity fields needed to distinguish matching editions/variants: `id`, `author`, `title`, `canonical_id`, `edition`, `identity_path`, `relative_path`, member verification metadata, and `source_revision`. Optional fields remain null/absent semantically when upstream metadata does not establish them; callers should fall back to canonical ID and paths rather than guessing.

Every member listing/search response carries the immutable upstream commit in `source_revision`, and each returned member repeats that revision for provenance. Callers should pass the returned token to subsequent pages and to `prepare_corpus` or `load_corpus` when they need the member they actually inspected.

When `source_revision` is omitted, a floating collection resolves its configured current upstream state before discovery or loading. When an immutable revision is supplied, Agora does not refresh or silently substitute a newer revision: member resolution and materialization operate against that exact cached commit. If the commit is not present in the cache repository, the operation fails deterministically and the caller may explicitly choose whether to resolve current upstream state instead.

This prevents a list → select → load time-of-check/time-of-use race. A member selected from revision A remains addressable at A even after upstream advances to B, so long as the A commit remains available in the local Git store. The same token should be reused across paginated discovery so pages cannot silently straddle different upstream revisions.

## Acquisition and loading

Collection members remain lazy:

```text
select collection member + source revision
→ resolve stable member ID at that revision
→ acquire/cache only the required TF corpus where practical
→ compile/load that member with Context-Fabric
→ expose it through Context-Fabric MCP
```

Do not require cloning, compiling, or loading an entire large collection merely to use one work if the upstream layout allows narrower acquisition.

If Git sparse checkout or another repository-level mechanism is the only practical acquisition method, the collection adapter may use it internally. That is an implementation detail and must not leak into canonical resource IDs.

## MCP process model

The collection model does not assume that all member corpora share one uniform TF schema. Individual corpora may have different node types, section models, feature sets, or malformed/problematic features.

Accordingly:

- member metadata is inspected independently;
- loading occurs per selected member or compatible group;
- Agora does not promise one global query schema across all works;
- feature discovery happens after loading the selected corpus;
- members with broken Agora acquisition or loading paths may carry their own integration status without degrading the whole collection.

The exact process strategy — restart a Context-Fabric MCP process when switching members, maintain a bounded pool, or support dynamic loading in one process — is an implementation detail; the public model remains member-oriented.

## Verification

Verification operates at three levels:

1. **Context-Fabric plugin** — MCP/runtime integration works.
2. **Collection resource** — index generation/discovery and member resolution work.
3. **Collection member** — a specific TF corpus loads and supports representative access.

It is neither necessary nor desirable to run full end-to-end tests for every member on every pull request. CI can combine:

- schema/index validation for all members;
- deterministic regeneration of commit-bound indexes;
- representative member smoke tests on normal PRs;
- batched/scheduled tests across the wider collection;
- explicit per-member integration-issue/status metadata.

Collection-resolution tests additionally cover revision consistency with local Git fixtures: discover a member at commit A, advance the upstream fixture to B with that member moved or removed, and prove that the A token still resolves/materializes A while an unpinned request follows B. Invalid or unavailable revision tokens fail without fallback.

## v0.1 requirement

Agora v0.1 supports this collection/member distinction for the collection resources in the fixed Context-Fabric baseline. `pthu/greek_literature` is the largest motivating case.

The implementation is not complete if `greek_literature` merely appears as one registry row but Agora cannot discover and load its individual TF works. Conversely, it is also not acceptable to represent every individual work as a separate marketplace plugin.
