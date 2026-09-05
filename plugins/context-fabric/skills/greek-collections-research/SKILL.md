---
name: greek-collections-research
description: "Use this skill for research with Agora's large Greek Text-Fabric collections: discover an individual work before loading it, preserve its repository provenance, inspect each work's schema independently, and avoid treating Perseus/OpenGreekAndLatin conversions as one homogeneous Greek corpus."
license: MIT
compatibility: "Requires the Agora Context-Fabric MCP plugin and access to registered PTHU Greek collection sources when a selected member is not already cached."
metadata:
  provider: context-fabric
  resource-family: greek-collections
  version: "0.1.0"
---

# Greek Text-Fabric collection workflow

Agora models large PTHU repositories as **collections of independent Text-Fabric corpora**, not as one giant Greek dataset and not as one marketplace plugin per work.

The upstream `pthu/greek_literature` repository contains Text-Fabric packages of Greek texts available from the **Perseus Digital Library** and the **Open Greek and Latin Project**. Agora's normal discovery path uses a complete member index bound to an exact upstream Git commit. If a caller requests another exact/current revision, Agora may generate and cache a revision-bound local index rather than rescanning the repository for every query.

That scale makes discovery and schema inspection mandatory.

## Discover the work first

Use `list_collection_members` on the appropriate registered collection rather than guessing a repository path from an author/title.

The query can match source-backed author/title metadata, canonical/provider identifiers, explicit edition identifiers, Agora member IDs, identity paths, and exact TF paths. For the committed Greek-literature snapshot, searches such as `Homer`, `Iliad`, or the corresponding TLG/provider identifier can locate the indexed Iliad member.

Not every upstream member supplies human-readable metadata. When `author`, `title`, or `edition` is missing, use `canonical_id`, `identity_path`, and `relative_path` to distinguish candidates. Do **not** infer author/work semantics from path positions.

Retain both the selected `member_id` and the returned `source_revision`. Pass that exact revision to later pages and to `prepare_corpus`/`load_corpus` so the work you load is the same upstream snapshot you inspected.

Do not acquire or load the whole collection just to work with one text.

## A collection member is its own corpus

Treat every selected work as an independent Text-Fabric corpus.

Do not assume that two works share:

- node types;
- section levels;
- feature names;
- TEI-to-TF conversion details;
- edition identifiers;
- tokenization;
- punctuation treatment;
- morphology or lemma annotation.

Even works in the same repository may originate from different source projects or conversion histories.

Inspect the schema after every corpus switch.

## Provenance matters

The repository aggregates conversions ultimately based on sources from Perseus and Open Greek and Latin / First1KGreek.

For a substantive result, distinguish:

1. Agora's collection/member identifier;
2. the exact PTHU collection `source_revision` and TF member path;
3. the underlying textual source/edition represented by that member.

Do not cite "Agora" or "PTHU Greek literature" as though that uniquely identifies the ancient-text edition used.

`canonical_id` preserves a provider/source identifier where the same-revision TF metadata supplies one. `edition` is exposed only when upstream metadata explicitly provides an edition field; absence of that field is not evidence that two similarly named members are the same edition. Use the canonical identifier and repository paths to keep variants distinct, and consult the selected corpus/upstream source when edition-sensitive wording matters.

## Do not confuse this provider with Perseus-MCP

Agora also has a separate Perseus plugin.

The two routes have different strengths:

- **Context-Fabric/PTHU member** — local graph/feature querying once the converted TF corpus is acquired and loaded;
- **Perseus-MCP** — live CTS navigation, passage retrieval, discovery, and Scaife-backed search against current Perseus/Scaife services.

A work being discoverable through one route does not guarantee an identical edition or identifier through the other.

If comparing results across the two providers, establish edition identity before treating the texts as equivalent.

## Schema-first workflow

After `load_corpus`:

1. inspect node types and section structure;
2. list available features;
3. determine whether lemma/morphology exists at all;
4. inspect a few nodes/passages manually;
5. only then construct the full research query.

Do not infer morphology from the fact that the source website may offer morphological tools. The Text-Fabric conversion must actually contain the relevant annotation for it to be queryable locally.

Likewise, do not assume a feature named `lemma`, `pos`, or similar has the same encoding across independent conversions without inspection.

## Collection discovery and duplicates

Large source collections may contain multiple representations, recensions, editions, translations, or similarly titled works.

When multiple members match an author/title:

- compare `canonical_id` when available;
- compare `identity_path` and exact `relative_path`;
- compare explicit `edition` metadata when present;
- determine whether they are duplicates or distinct editions/works;
- select explicitly rather than accepting the first match.

Preserve ambiguity if the available metadata is insufficient to establish identity.

## Counting across works

Cross-work aggregation is possible, but comparability must be demonstrated first.

Before pooling counts from several Greek members, establish that they use compatible:

- token units;
- text normalization;
- feature semantics;
- morphological/lemmatization coverage;
- treatment of punctuation and non-lexical tokens.

Otherwise report per-corpus results rather than a misleading pooled frequency.

## Reproducibility

Record:

- collection resource ID;
- member ID returned by `list_collection_members`;
- resolved collection `source_revision`;
- source-backed author/title when present;
- `canonical_id` when present;
- `edition` when explicitly present;
- `identity_path` and exact TF `relative_path`;
- node types/features used after loading;
- whether the same work was compared against the separate Perseus plugin.

When a collection changes upstream, rerun discovery and retain the new returned revision rather than relying indefinitely on a remembered filesystem path or human label.
