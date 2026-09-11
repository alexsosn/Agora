---
name: context-fabric-research
description: "Use this skill when researching with Agora's Context-Fabric plugin: discover a corpus or collection, select the right member, load it deliberately, inspect its schema, and avoid transferring assumptions between heterogeneous Text-Fabric datasets."
license: MIT
compatibility: "Requires the Agora Context-Fabric MCP plugin and network access when a corpus must be acquired from its registered upstream Git source."
metadata:
  provider: context-fabric
  version: "0.1.0"
---

# Context-Fabric research workflow

Use Agora's resource-management tools before treating a Text-Fabric corpus as if it were already loaded or as if its schema were known.

## Core rule

**Do not assume that two Text-Fabric corpora share node types, section models, feature names, tokenization, morphology, syntax, or annotation conventions.** Text-Fabric is a data model, not a universal philological schema.

A pattern that is correct for BHSA may be wrong for CUC, a Greek work, a Syriac corpus, a historical letter collection, or TLHdig-TF.

## Recommended workflow

### 1. Discover the resource

Start with `list_available_corpora`.

Useful filters include:

- free-text `query`;
- `language`;
- `discipline`;
- `kind="collection"` when looking for a repository that contains many independent corpora.

Do not guess repository-relative paths from memory when the catalog can resolve the resource for you.

### 2. Inspect the catalog record

Use `describe_available_corpus` before acquisition when provenance, resource kind, language, or collection status matters.

Keep the returned `resource_id`. Use it in later calls rather than inventing a path or local directory name.

### 3. If it is a collection, select a member explicitly

For collection resources, call `list_collection_members`.

Search or page through members rather than assuming a title maps to a predictable filesystem path.

Important examples include large Greek and Latin collection repositories. Individual members are independent TF corpora. Treat the returned `member_id` as the stable handle for later calls.

Do not infer a member's schema from another work in the same collection.

### 4. Acquire only what you need

Use `prepare_corpus` when you want to materialize/cache the selected TF dataset before loading it.

This is useful when:

- you want to separate network/acquisition problems from load problems;
- a corpus may be relatively large;
- you are debugging source/version selection;
- you want to confirm the exact selected resource/member before loading;
- you are selecting one or more optional feature modules and want to inspect the exact combination before paying cold-compile cost.

When modules are selected, inspect the returned `load_preflight` before calling `load_corpus`. It reports whether that exact derived overlay is currently warm, whether a full compile is currently required, direct source bytes, default compile byte/time guardrails, the host free-space reserve, and the parent's historical load-cost record when available. `cost_expectation="parent-scale-possible"` means a small module does not imply a small compile: the overlay is a complete TF source tree and a cold combination may compile at roughly parent scale. The historical parent record is context, not a machine-independent prediction.

Module precedence is `ordered-last-wins`. Agora overlays module feature files in the order requested; if two modules expose the same feature filename, the later module replaces the earlier one. Do not reorder a user's module list for cache deduplication. Reversing the same module set can intentionally produce a different overlay and result.

For release-scale context, the BHSA investigation behind Agora issue #46 observed that two small feature modules (about 6 MB each) could add roughly **1.14 GB** of cache and about **7.5 minutes** of extra cold compilation on the measured machine. Treat those values as historical evidence of parent-scale amplification, not as guaranteed current cost.

A practical expensive-module sequence is: `prepare_corpus(..., modules=[...])` → inspect `load_preflight` and `corpus_cache_status` → call `load_corpus` only if the disclosed state is acceptable. You may pass stricter `max_compile_gb` or `max_compile_minutes` values to `load_corpus`; those overrides do not reduce Agora's configured minimum-free-space reserve. Warmth in `load_preflight` is a point-in-time observation; `load_corpus` rechecks the exact combination under its compile lock before deciding whether to compile.

Agora's collection model is intentionally lazy. Do not acquire an entire large collection merely because one work is needed.

### 5. Load the selected corpus

Use `load_corpus` with the exact `resource_id` and, for collections, the exact `member_id` returned by discovery.

If you request extra features, request only features you have evidence exist in that corpus.

For module overlays, preserve the module order used during prepare. While a cold load runs, `corpus_cache_status` exposes its progress and limits; `cancel_corpus_load` can cancel a load owned by the current server process. After unload, unused overlays remain independently visible as `kind="overlay"` cache entries and can be reclaimed through prune/remove operations.

### 6. Inspect before querying

After loading, inspect the Context-Fabric tools and the loaded corpus's node types/features before writing a substantive query.

Before relying on a feature, establish at least:

- the relevant node type;
- the feature name;
- what values mean;
- whether the feature applies to slots, words, phrases, clauses, sentences, documents, or another node type;
- whether missing values are meaningful or merely absent annotation.

Do not silently substitute a similarly named feature from another corpus.

## Corpus-specific caution

### BHSA and ETCBC-derived corpora

BHSA has rich morphology and syntax, but its feature vocabulary is not a generic Text-Fabric standard. Features such as part of speech, verbal stem, verbal tense, phrase function, or clause type should be interpreted according to the ETCBC/BHSA documentation for that corpus/version.

Do not transfer BHSA conventions automatically to DSS, Syriac, Ugaritic, Greek, or other TF datasets.

### CUC / Ugaritic

Confirm transliteration, tokenization, node types, and feature meanings from the CUC schema before doing linguistic counts. Orthographic segmentation and morphological representation can change what a naive "word count" or form search means.

In cfabric-mcp 0.1.7, generic text-format discovery only recognizes paired `fmt:*` metadata following the expected original/translation naming pattern. CUC instead exposes its Latin and Ugaritic representations through the `sign` and `usign` features, so `get_text_formats` can report no usable pair even though both representations are present. Inspect the CUC schema/features directly; a negative `get_text_formats` result is not evidence that CUC lacks a text representation.

### Greek collections

A Greek collection is not one giant homogeneous corpus. Discover the work, load that member, then inspect that work's schema.

Avoid workflows that assume every Greek work has the same section levels, node types, or feature filenames.

### TLHdig-TF

Load the registered resource, record its resolved source revision, and use the documentation and schema at that upstream revision for corpus semantics, data-quality information, and research-suitability guidance. Agora does not maintain a parallel assessment of those upstream-owned concerns.

## Verification and provenance

Plugin status and resource status describe different Agora-owned integration paths; neither is a scholarly-quality assessment.

When reporting a result, record enough context for reproducibility:

- `resource_id`;
- `member_id` when applicable;
- selected TF dataset/version or source path if exposed;
- resolved upstream source revision;
- important features used;
- query logic;
- upstream documentation consulted for corpus interpretation.

## Query-design principles

Prefer structured graph/feature queries when the research question is structurally defined. Prefer surface-text search when the question is genuinely lexical/string-based.

For counts and comparisons:

1. define the unit being counted;
2. state filters and node types;
3. inspect missing annotation;
4. distinguish zero from unavailable annotation;
5. spot-check returned passages/nodes before interpreting aggregate numbers.

With cfabric-mcp 0.1.7, `return_type="count"` is derived after the search cache has been capped at 10,000 results. A returned count of 10,000 can therefore mean 10,000 or more; do not report it as an exact corpus-wide frequency. Narrow the query or validate the aggregate with a corpus-native method when an exact count above that boundary is required.

For cross-corpus comparisons, first establish that the compared annotations are genuinely comparable. Identical labels do not guarantee identical annotation guidelines.

## Failure handling

If discovery fails, check the resource ID and catalog before changing paths manually.

If acquisition fails, distinguish upstream availability from local cache/filesystem problems.

If loading fails, report the selected resource/member and dataset root rather than masking the failure by trying unrelated versions.

If a requested linguistic feature does not exist, say that the corpus does not expose the required annotation rather than fabricating a proxy silently.
