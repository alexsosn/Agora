# Greek Text-Fabric Collection Handling

Several Greek Text-Fabric repositories do not behave like ordinary single-corpus repositories. In particular, repositories such as `pthu/greek_literature` contain many independent Text-Fabric corpora, typically one work/text per corpus directory.

Agora must treat this as a first-class collection model rather than flattening every internal work into a marketplace plugin.

## Design rule

**Marketplace granularity and Text-Fabric runtime granularity are different.**

At the marketplace level:

- `pthu/greek_literature` is one Context-Fabric resource of type `collection`;
- the collection is installed/discovered through the single `context-fabric` plugin;
- individual works are not top-level Agora plugins and should not appear as thousands of marketplace entries.

At the runtime level:

- each individual Greek work remains a separately loadable Text-Fabric corpus;
- Agora must discover, address, acquire, cache, and load collection members independently;
- Context-Fabric MCP should be pointed at the selected member corpus, not at an artificial merged corpus unless an upstream collection explicitly supports that.

## Registry model

Collection resources need metadata distinct from ordinary corpus resources.

Conceptually:

```yaml
id: greek_literature
plugin: context-fabric
provider: context-fabric
resource:
  type: collection
upstream:
  repository: pthu/greek_literature
members:
  discovery: git-tree
  id_scheme: stable-relative-id
```

Individual members should have stable internal identifiers without becoming marketplace plugins. For `git-tree` discovery, the committed collection descriptor intentionally has no member snapshot; the resolver derives current members and stable IDs from upstream dataset paths. A future curated/indexed mode may record, where available:

- stable member ID;
- repository-relative corpus path;
- author;
- work title;
- language;
- edition/source identifier;
- CTS URN or other canonical identifier when available;
- TF version/data directory;
- node types and salient features where useful;
- load/test status;
- Agora-owned integration issues.

The member ID should be independent of the local checkout path. If a stable upstream identifier such as a CTS URN exists, prefer or preserve it. Otherwise derive a deterministic Agora ID from stable repository metadata.

## Discovery and snapshot consistency

Agents should be able to search collection members before loading one. The Context-Fabric integration therefore needs collection-aware discovery operations such as:

- list collections;
- search members by author/title/identifier;
- inspect member metadata;
- resolve a member ID to its upstream TF location;
- list locally cached members.

A user asking for Homer should not require Agora to load or enumerate every Greek corpus into an MCP process first.

Collection discovery is revision-addressed. Every member listing/search response carries the immutable upstream commit in `source_revision`, and each returned member repeats that revision for provenance. Callers should pass the returned token to subsequent pages and to `prepare_corpus` or `load_corpus` when they need the member they actually inspected.

When `source_revision` is omitted, a floating collection resolves its configured current upstream state before discovery or loading. When an immutable revision is supplied, Agora does not refresh or silently substitute a newer revision: member resolution and materialization operate against that exact cached commit. If the commit is not present in the cache repository, the operation fails deterministically and the caller may explicitly choose whether to resolve current upstream state instead.

This prevents a list → select → load time-of-check/time-of-use race. A member selected from revision A remains addressable at A even after upstream advances to B, so long as the A commit remains available in the local Git store. The same token should be reused across paginated discovery so pages cannot silently straddle different upstream revisions.

## Acquisition and loading

Collection members should be lazy by default:

```text
select collection member + source revision
→ resolve stable member ID at that revision
→ acquire/cache only the required TF corpus where practical
→ compile/load that member with Context-Fabric
→ expose it through Context-Fabric MCP
```

Do not require cloning, compiling, or loading an entire large Greek collection merely to use one work if the upstream layout allows narrower acquisition.

If Git sparse checkout or another repository-level mechanism is the only practical acquisition method, the collection adapter may use it internally. That is an implementation detail and must not leak into canonical resource IDs.

## MCP process model

The collection model must not assume that all member corpora share one uniform TF schema. Individual Greek corpora may have different node types, section models, feature sets, or malformed/problematic features.

Accordingly:

- member metadata should be inspected independently;
- loading should occur per selected member or compatible group;
- Agora should not promise one global query schema across all Greek works;
- feature discovery must happen after loading the selected corpus;
- members with broken Agora acquisition or loading paths may carry their own integration status without degrading the whole collection.

The exact process strategy — restart a Context-Fabric MCP process when switching members, maintain a bounded pool, or support dynamic loading in one process — can be chosen during implementation, but the public model must remain member-oriented.

## Verification

Verification should operate at three levels:

1. **Context-Fabric plugin** — MCP/runtime integration works.
2. **Collection resource** — discovery/indexing and member resolution work.
3. **Collection member** — a specific TF corpus loads and supports representative access.

It is neither necessary nor desirable to run full end-to-end tests for every member on every pull request. CI can combine:

- schema/index validation for all members;
- representative member smoke tests on normal PRs;
- batched/scheduled tests across the wider collection;
- explicit per-member integration-issue/status metadata.

Collection-resolution tests should additionally cover revision consistency with a local Git fixture: discover a member at commit A, advance the upstream fixture to B with that member moved or removed, and prove that the A token still resolves/materializes A while an unpinned request follows B. Invalid or unavailable revision tokens must fail without fallback.

## v0.1 requirement

Agora v0.1 must support this collection/member distinction for the Greek collection resources in the fixed Context-Fabric baseline. `pthu/greek_literature` is the primary case and should drive the design.

The implementation is not complete if `greek_literature` merely appears as one registry row but Agora cannot discover and load its individual TF works. Conversely, it is also not acceptable to represent every individual work as a separate marketplace plugin.
