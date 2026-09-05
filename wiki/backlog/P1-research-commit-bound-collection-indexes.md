# Research: commit-bound Context-Fabric collection indexes

Issue: #13 (also resolves the discovery defect in #28)

## Scope and ownership

This is Agora-owned resource discovery/resolution work. The defect is in Agora's collection abstraction: the registry declares member indexes but runtime ignores them, rescans Git trees for every request, and guesses scholarly labels from repository path positions. No third-party Text-Fabric behavior needs to be patched.

The implementation must preserve the thin-plugin boundary: it may inspect upstream repository metadata and Text-Fabric feature headers to describe and select already-published corpora, but it must not invent author/work semantics or alter corpus contents.

## Current state

The four v0.1 collection indexes (`bible`, `patristics`, `greek_literature`, `translatin-manif`) are committed as `index_status: dynamic` with empty `members` lists. `scripts/validate_registry.py` currently enforces that `git-tree` collections remain empty.

`ContextFabricResolver.resolve_members()` and collection `prepare()` call `GitStore.dataset_roots()` for every request. `_collection_members_from_roots()` also assigns `author` and `title` whenever an identity path happens to have two components; repository depth is not a scholarly metadata contract.

The runtime catalog already carries `collection.member_index`, but the installed Context-Fabric plugin currently ships only `resources/catalog.yaml` and `resources/feature-modules.yaml`. Therefore canonical indexes cannot become a runtime dependency until generated installed copies are added.

## Upstream snapshots examined

The current upstream collection heads are:

| Collection | Repository | Source revision |
| --- | --- | --- |
| `bible` | `pthu/bible` | `f09ea5060761b372adf1ac1d70d7b96918f57757` |
| `patristics` | `pthu/patristics` | `75d0e305c4f88a9304a4cf524dc19b9a66b0ec9e` |
| `greek_literature` | `pthu/greek_literature` | `77d85bf71fc6f689f7faedc255666a2609ffe590` |
| `translatin-manif` | `HuygensING/translatin-manif` | `ab4df0d84d3480cee0cdaa41973c77ec7a0f99ed` |

The first three PTHU repositories expose independently loadable datasets below paths ending in `/tf/<version>`. `translatin-manif` uses `tf/<manifestation>/<version>`.

## Semantic metadata findings

### PTHU Greek literature

The TF data itself contains authoritative same-revision metadata. For the Iliad member at

`canonical-greekLit/tlg0012/tlg001/perseus-grc2/1/tf/1.0`

`_book.tf` contains, among other headers:

- `@author=Homer`
- `@title=Iliad (Greek). Machine readable text`
- `@filename=tlg0012.tlg001.perseus-grc2`
- edition/source metadata.

The original Perseus CTS repository independently confirms `tlg0012` as Homer and `tlg001` as Iliad, but Agora does not need a second floating metadata repository for normal index generation when the converted TF snapshot already carries the required labels.

### PTHU patristics and Bible

Patristics TF headers likewise carry `@author`, `@_book`, `@edition`, `@urn`, language, license, and source metadata. Bible members use the same conversion family and carry the same style of headers. These values are acceptable descriptive metadata because they are published inside the exact TF snapshot being indexed; they are not inferred from folder names.

### TransLatin

TransLatin has a different layout and a richer metadata model. Its repository contains manifestation metadata under `meta/0.1/manifestations.yaml`, work metadata, and TF features such as `author.tf`. The README explicitly describes the TF units as manifestations and notes that work/expression grouping is interpretive and still evolving. The safe v0.1 index therefore treats the manifestation ID (for example `M1043`) as the stable canonical identifier and does not synthesize author/title unless a dedicated same-revision metadata parser can establish them unambiguously.

## Member identity and stable IDs

Load identity and semantic labels must be separate.

For normal PTHU layout `.../<member>/tf/<version>`, the stable identity path is the path before `/tf/`. For TransLatin `tf/<manifestation>/<version>`, the stable identity path is `tf/<manifestation>`. The selected `tf_path` is the concrete dataset root for the preferred version.

Member IDs remain deterministic hashes/slugs of the stable identity path, never of author/title text or the selected TF version. Regenerating an index at a newer commit therefore preserves IDs for unchanged members even if a newer TF version becomes preferred.

Generic path components must never populate `author` or `title`. A member may receive semantic metadata only from an explicit parser of published same-revision metadata. Otherwise it exposes neutral path/canonical identifiers.

## Revision model and interaction with #7

A committed-index-only runtime would conflict with #7. Callers may pin any still-available historical `source_revision`, and omission must continue to mean current/floating upstream resolution rather than silently forcing the revision that happened to be committed in Agora.

The required model is therefore:

1. Resolve the requested source revision exactly as today (`source_revision` supplied => exact cached commit; omitted => current upstream selected commit).
2. If the installed committed index has exactly that `source_revision`, use it directly.
3. Otherwise look for a locally generated index cached by `(collection_id, source_revision)`.
4. If absent, scan Git metadata once for that exact revision, read only small metadata/header blobs needed for member descriptions, generate the revision-bound index atomically, cache it, and use it.
5. Never substitute an index from another revision. An unavailable pinned commit retains #7's deterministic error behavior.

This policy preserves floating/current behavior and historical reproducibility while eliminating full-tree rescans on every list/search/prepare request. A new upstream revision may cause one index-generation scan, not repeated scans for every query.

## Runtime/index architecture

A small Agora-owned collection-index layer should own:

- parsing/validating collection index documents;
- selecting an installed or cached index for an exact source revision;
- generating an index from `GitStore.dataset_roots()` when necessary;
- reading TF header metadata through a public `GitStore` method backed by `git show`, rather than reaching across classes into private helpers;
- persistent cache storage below the Context-Fabric cache root, keyed by collection and immutable revision;
- exact lookup of `member_id -> tf_path` for prepare/load.

`resolve_members()` and collection `prepare()` should both consume this layer. Once an index exists for a revision, neither path should rescan the repository tree.

## Canonical and installed indexes

Canonical source of truth remains `registry/collections/*.yaml`. Each complete index must record an immutable top-level `source_revision` and non-empty members.

The Context-Fabric catalog generator should also produce `plugins/context-fabric/resources/collections/*.yaml` and rewrite the installed catalog's `member_index` paths to those plugin-root-relative copies. Foundation should check these generated copies for freshness without requiring network access.

A separate maintainer generator should be able to refresh canonical indexes from explicit/current upstream revisions. Remote source freshness belongs in source-audit/maintenance work, not in every deterministic Foundation run.

## Index/member schema direction

Top-level collection index:

- `schema_version`
- `collection_id`
- `source_revision` (full immutable commit)
- `index_status` (`complete` for the four generated v0.1 indexes)
- `members`

Member records should carry:

- stable `id`
- stable identity `path`
- concrete selected `tf_path`
- `languages`
- optional `canonical_id`
- optional `author` / `title` only when established by a metadata parser
- `verification.status`
- optional `verification.evidence` references plus notes

No member is promoted merely because indexing succeeded. Generated v0.1 members should retain conservative integration evidence/status unless a separate member-level check justifies more.

## Search behavior

Search should index identifiers, stable path, selected TF path, canonical ID, and metadata-backed author/title. This directly fixes #28: the Iliad member should match `Homer`, `Iliad`, and its CTS/TLG/path identifiers while retaining edition/path identity.

## Generation strategy

The generator can operate efficiently from a metadata-only Git clone already supported by `GitStore`:

1. resolve/pin the target commit;
2. enumerate `otype.tf` roots once;
3. group roots by stable identity and select the preferred TF version using existing version ordering;
4. read a small representative feature header (`_book.tf` or another deterministic feature candidate) for PTHU semantic metadata;
5. emit neutral identifiers when no supported parser succeeds;
6. sort deterministically and write YAML atomically.

Generation must not materialize complete corpora or run Text-Fabric itself.

## Tests required by the ticket

The implementation needs regressions for:

- deep CTS-like paths and metadata-backed Homer/Iliad search;
- arbitrary two-component repository paths remaining neutral;
- stable member IDs across regeneration when only TF version changes;
- TransLatin `tf/<manifestation>/<version>` identity handling;
- exact source revision recorded in the index;
- installed-index fast path with no `dataset_roots()` rescan;
- revision mismatch causing generation/use of the exact requested revision rather than silent fallback;
- cached generated index reuse;
- collection prepare resolving member path from the same index used for discovery;
- schema/reference validation, including member verification evidence references;
- generated installed-index freshness;
- all four committed indexes non-empty and `complete`.

## Scope exclusions

This ticket does not judge scholarly correctness of upstream metadata, normalize author names, merge duplicate works, decide preferred editions, repair upstream TF data, or create new domain capabilities. It indexes and exposes upstream-published identity/metadata while preserving exact revisions.
