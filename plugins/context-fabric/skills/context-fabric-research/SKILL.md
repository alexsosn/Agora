---
name: context-fabric-research
description: Use this skill when researching with Agora's Context-Fabric plugin: discover a corpus or collection, select the right member, load it deliberately, inspect its schema, and avoid transferring assumptions between heterogeneous Text-Fabric datasets.
license: MIT
compatibility: Requires the Agora Context-Fabric MCP plugin and network access when a corpus must be acquired from its registered upstream Git source.
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
- you want to confirm the exact selected resource/member before loading.

Agora's collection model is intentionally lazy. Do not acquire an entire large collection merely because one work is needed.

### 5. Load the selected corpus

Use `load_corpus` with the exact `resource_id` and, for collections, the exact `member_id` returned by discovery.

If you request extra features, request only features you have evidence exist in that corpus.

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

### Greek collections

A Greek collection is not one giant homogeneous corpus. Discover the work, load that member, then inspect that work's schema.

Avoid workflows that assume every Greek work has the same section levels, node types, or feature filenames.

### TLHdig-TF

The Context-Fabric plugin may be Verified while TLHdig-TF remains an Experimental **resource**. Preserve resource-level warnings about conversion correctness, ambiguous markup, damaged text, and undocumented source fields in any research conclusion.

## Verification and provenance

Plugin status and resource status are different claims.

When reporting a result, record enough context for reproducibility:

- `resource_id`;
- `member_id` when applicable;
- selected TF dataset/version or source path if exposed;
- important features used;
- query logic;
- resource status and relevant known issues.

If a resource is Experimental, say so when the uncertainty could affect the result.

## Query-design principles

Prefer structured graph/feature queries when the research question is structurally defined. Prefer surface-text search when the question is genuinely lexical/string-based.

For counts and comparisons:

1. define the unit being counted;
2. state filters and node types;
3. inspect missing annotation;
4. distinguish zero from unavailable annotation;
5. spot-check returned passages/nodes before interpreting aggregate numbers.

For cross-corpus comparisons, first establish that the compared annotations are genuinely comparable. Identical labels do not guarantee identical annotation guidelines.

## Failure handling

If discovery fails, check the resource ID and catalog before changing paths manually.

If acquisition fails, distinguish upstream availability from local cache/filesystem problems.

If loading fails, report the selected resource/member and dataset root rather than masking the failure by trying unrelated versions.

If a requested linguistic feature does not exist, say that the corpus does not expose the required annotation rather than fabricating a proxy silently.
