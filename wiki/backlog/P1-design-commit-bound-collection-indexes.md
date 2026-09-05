# Design plan: commit-bound Context-Fabric collection indexes

Issues: #13, #28

Research gate: `P1-research-commit-bound-collection-indexes.md`

## Goal

Make collection discovery and prepare/load use exact-revision indexes instead of rebuilding member lists from repository paths on every request. Populate the four v0.1 indexes, derive semantic labels only from published metadata, preserve #7 snapshot semantics, and make Homer/Iliad discoverable without guessed identifiers.

## Gate order

Implementation follows research -> plan -> RED/GREEN slices -> full test gate -> independent review. Review findings restart a RED/GREEN/retest/re-review cycle before merge.

## RED/GREEN 1 — index model and deterministic generation primitives

### RED

Add focused tests for a collection-index module using local synthetic repository inventories/headers:

- deep PTHU/CTS-like root `canonical-greekLit/tlg0012/tlg001/perseus-grc2/1/tf/1.0` produces a stable identity independent of TF version;
- `tf/M1043/0.1.2` produces stable TransLatin identity `tf/M1043`;
- member ID is unchanged when the selected TF version changes;
- arbitrary two-component path names do not become `author`/`title`;
- PTHU `_book.tf` headers populate `author`, `title`, `canonical_id`, and `edition` where present;
- missing/unsupported metadata leaves semantic fields null;
- generation records the exact immutable `source_revision`, selects one preferred TF root per stable identity, sorts deterministically, and emits conservative member verification metadata.

### GREEN

Create a small `agora_context_fabric.collection_index` module with:

- immutable index/member dataclasses;
- stable identity/ID helpers;
- TF header parser;
- deterministic index builder from one tree inventory plus a metadata-reader callback;
- YAML load/dump helpers.

Expose a public read-only GitStore API for exact-revision tree names and small text blobs/headers instead of using GitStore private methods from the new module.

No runtime behavior changes in this slice.

## RED/GREEN 2 — exact-revision runtime index selection and cache

### RED

Extend local-Git snapshot tests with instrumentation proving:

- first discovery of revision A may scan the tree once;
- repeated list/search/prepare/load at A reuses the revision-bound index and does not rescan `dataset_roots()`/tree inventory;
- after upstream moves to B, unpinned discovery resolves B and generates/uses B rather than silently using A;
- an explicit pinned A request still uses A and remains loadable if the commit is available;
- a generated index is reused from the persistent cache by a fresh resolver instance;
- an installed index is used directly when its `source_revision` matches;
- an installed index for the wrong revision is never silently substituted;
- prepare resolves `member_id -> tf_path` from the same exact-revision index used for discovery.

Keep the existing #7 unavailable/malformed revision fail-closed regressions.

### GREEN

Add a resolver-owned/index-manager layer that:

1. resolves the exact requested commit through existing collection revision semantics;
2. loads the installed index when its revision matches;
3. otherwise loads `cache/collection-indexes/<collection>/<revision>.yaml` when present;
4. otherwise builds once from exact Git metadata, writes atomically, then reuses it;
5. feeds both `resolve_members()` and collection `prepare()`.

The generated-index cache is metadata-sized and separate from corpus snapshot eviction. Concurrent generation may race, but writes must be atomic and deterministic so no partial index can be observed.

Remove generic path-depth `author/title` inference from the resolver.

## RED/GREEN 3 — registry/schema and installed packaging contract

### RED

Add registry/packaging tests requiring:

- every complete v0.1 collection index has a full immutable `source_revision` and at least one member;
- `collection.discovery` is `indexed` for the four v0.1 collections;
- collection schema supports `tf_path`, optional `canonical_id`, `edition`, metadata-backed `author/title`, and member `verification.evidence` references;
- invalid/missing member verification check references are rejected when evidence is present;
- installed plugin catalog points at plugin-root-relative `resources/collections/*.yaml`;
- installed index copies are exact generated projections of canonical registry indexes;
- catalog/index generation `--check` detects stale/missing installed copies.

### GREEN

Update:

- `registry/schema/collection-index.schema.json`;
- registry validation and collection-discovery rules;
- the four collection resource records from `git-tree` to `indexed`;
- `scripts/generate_context_fabric_catalog.py` to copy canonical collection indexes and rewrite only installed `member_index` paths;
- `Catalog`/`ResourceSpec` so runtime resources carry a resolved local `member_index_path` while preserving the documented relative path;
- packaging/freshness documentation and tests.

The canonical registry continues to reference `registry/collections/*.yaml`; generated plugin artifacts do not become canonical inputs.

## RED/GREEN 4 — real upstream index generator and committed v0.1 indexes

### RED

Add generator tests against local Git fixtures proving:

- exact revision is required/recorded;
- all independently loadable roots are grouped correctly;
- stable IDs survive regeneration;
- PTHU same-revision TF headers provide real metadata;
- neutral fallback works;
- output is deterministic and `complete`;
- `--check`/comparison can detect changed output without modifying files.

### GREEN

Add `scripts/generate_context_fabric_collection_indexes.py` using the production index builder and metadata-only GitStore. It must not materialize entire corpora or invoke Text-Fabric.

Generate and commit canonical indexes at the researched upstream revisions:

- `bible` — `f09ea5060761b372adf1ac1d70d7b96918f57757`;
- `patristics` — `75d0e305c4f88a9304a4cf524dc19b9a66b0ec9e`;
- `greek_literature` — `77d85bf71fc6f689f7faedc255666a2609ffe590`;
- `translatin-manif` — `ab4df0d84d3480cee0cdaa41973c77ec7a0f99ed`.

Then regenerate installed copies through the catalog generator.

## RED/GREEN 5 — #28 discovery UX and MCP surface

### RED

Add regressions using a Greek fixture with real-style TF headers:

- query `Homer` returns the Iliad member;
- query `Iliad` returns it;
- TLG/CTS/path/edition identifiers still return it;
- output exposes metadata-backed author/title plus canonical/edition/path identity;
- members with no semantic metadata remain discoverable by neutral identifiers;
- pagination retains `source_revision`.

### GREEN

Extend `CollectionMember`/service serialization/search haystack with default-compatible optional fields:

- `canonical_id`;
- `edition`;
- member verification status/evidence/notes.

Update the Greek collection facilitation skill and collection architecture docs so users search human labels when available and fall back to exposed canonical/path identifiers otherwise. Do not teach guessed identifiers.

## Full test gate

Before review, require the final candidate SHA to pass:

- `python scripts/validate_registry.py`;
- `python scripts/generate_context_fabric_catalog.py --check`;
- complete unittest discovery via Foundation;
- cross-platform Context-Fabric cache regressions;
- any source-audit workflow triggered by collection source/index changes.

If CI reveals a behavioral defect, add a focused RED regression before the fix.

## Independent review gate

Review the exact final SHA from scratch using:

- `CONTRIBUTING.md`;
- `AGENTS.md`;
- `.agents/skills/agora-pr-review/SKILL.md`;
- `.agents/skills/agora-plugin-review/SKILL.md`;
- `wiki/architecture/ref-plugin-boundary.md`;
- issue #13 and #28 acceptance criteria.

Review must specifically challenge:

- whether metadata labels are truly source-backed rather than path guesses;
- whether arbitrary/historical source revisions preserve #7 semantics;
- whether prepare and discovery can diverge to different revisions;
- whether generated indexes can become stale or partial without validation detecting it;
- whether generated plugin copies remain non-canonical;
- whether tests stay at Agora-owned discovery/integration boundaries rather than assessing upstream scholarship.

Any blocker gets a new RED regression where practicable, a GREEN fix, full retest, and another independent review. Merge only after a compliant review and green final gates.
