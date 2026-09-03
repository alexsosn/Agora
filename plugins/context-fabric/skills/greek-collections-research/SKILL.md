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

The upstream `pthu/greek_literature` repository says it contains Text-Fabric packages of Greek texts available from the **Perseus Digital Library** and the **Open Greek and Latin Project**. Agora discovers the current dataset roots dynamically from upstream Git metadata.

That scale makes discovery and schema inspection mandatory.

## Discover the work first

Use `list_collection_members` on the appropriate registered collection rather than guessing a repository path from an author/title.

Search the returned members for the author/work you need and retain the returned `member_id`.

Then call `load_corpus` with both the collection resource ID and that exact member ID.

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
2. the PTHU Text-Fabric conversion;
3. the underlying textual source/edition represented by that member.

Do not cite "Agora" or "PTHU Greek literature" as though that uniquely identifies the ancient-text edition used.

Where edition-sensitive wording matters, recover and record the underlying edition/resource metadata exposed by the selected corpus or upstream source.

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

- compare their repository-relative identity paths and metadata;
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
- author/title and repository-relative member path;
- selected TF version/path if exposed;
- resolved upstream source revision;
- underlying edition/source when identifiable;
- node types/features used;
- whether the same work was compared against the separate Perseus plugin.

When a collection changes upstream, member discovery should be rerun rather than relying indefinitely on a remembered filesystem path.
