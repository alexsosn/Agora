# Germanic Philology Backlog: Old Norse, Old Icelandic, and Gothic

This document supplements [`P0-research-ecosystem-expansion.md`](P0-research-ecosystem-expansion.md) with language-specific candidates and wanted integrations for Old Norse / Old Icelandic and Gothic. It is part of the post-v0.1 research backlog and does not change Agora's fixed v0.1 scope.

## Priority legend

- **P0 — investigate for the first post-v0.1 expansion:** unusually high scholarly value or an important capability gap.
- **P1 — strong candidate:** clearly useful and sufficiently concrete to justify verification or integration work.
- **P2 — experimental, narrow, or superseded candidate:** useful, but a stronger scholarly upstream should be preferred where possible.
- **Wanted integration:** no satisfactory MCP/plugin was found, but the upstream resource is important enough that Agora should track or solicit an implementation.

---

# P0 wanted integrations

## ONP — A Dictionary of Old Norse Prose

- **Upstream:** University of Copenhagen, *Ordbog over det norrøne prosasprog / A Dictionary of Old Norse Prose* (ONP).
- **Area:** Old Norse / Old Icelandic lexicography.
- **Scale:** roughly 65,000 headwords, around 60,000 identified senses, and approximately 840,000 citations.
- **Why P0:** this is the strongest lexicographic target found for Old Norse prose. Its citations connect lexical senses to actual source passages and manuscript/bibliographic metadata, enabling a particularly strong scholarly workflow:

  `lemma → sense → citation → work → manuscript`

- **Potential MCP capabilities:**
  - headword and inflected-form lookup;
  - sense hierarchy;
  - citations/attestations;
  - work and manuscript metadata;
  - chronological/genre filtering where upstream metadata permits;
  - citation-safe links back to ONP records.
- **Current status:** no satisfactory dedicated MCP was found.
- **Verification/integration focus:** determine whether a stable public query API or export exists, and document data/API licensing before implementation.

## Menota — Medieval Nordic Text Archive

- **Upstream:** Medieval Nordic Text Archive (Menota).
- **Area:** Old Norse / Old Icelandic / Old Norwegian manuscripts and digital editions.
- **Scope:** close to 100 Medieval Nordic texts and more than two million words in the current archive.
- **Why P0:** one of the most important machine-readable Old Norse textual resources, with manuscript-aware TEI encoding and multiple transcription levels.
- **Relevant features:**
  - facsimile/diplomatic/normalized representation depending on text;
  - lemma and grammatical annotation in some editions;
  - manuscript and facsimile links;
  - TEI-based encoding conventions designed specifically for Medieval Nordic philology.
- **Agora architecture:** Menota should be modelled as a scholarly provider/resource family; generic TEI operations can be supplied by the separate TEI MCP rather than reimplemented.
- **Potential MCP capabilities:** corpus/text discovery, passage retrieval by edition/manuscript, transcription-level selection, lemma/morphology search, manuscript links, and TEI-aware citation.
- **Current status:** no convincing dedicated Menota MCP found.

## Wulfila Project MCP

- **Upstream:** Wulfila Project.
- **Area:** Gothic, Germanic philology, Biblical Studies.
- **Why P0:** probably the clearest Gothic integration target. Wulfila provides a continuously maintained digital Gothic corpus centred on the Gothic Bible and minor fragments, together with linguistic and manuscript resources.
- **Machine-readable data:** downloadable TEI P5 and structured XML resources for text, grammar/annotation, lemmas/tokens, and lexicographic material.
- **Relevant resources:**
  - Gothic Bible and fragments;
  - lemmatization and POS information;
  - manuscript/facsimile links;
  - interlinear and linguistic resources;
  - Streitberg-related lexical material.
- **Potential MCP capabilities:** passage retrieval, lemma search, morphology, manuscript witness lookup, Gothic ↔ source/reference navigation, lexical lookup, and integration with TEI tooling.
- **Biblical Studies relevance:** exposes a major early Bible version as a linguistically annotated primary source rather than only as translation text.
- **Current status:** no satisfactory Wulfila MCP found.

---

# P1 candidates and integration targets

## PROIEL / Syntacticus / Universal Dependencies provider

- **Upstreams:** PROIEL treebanks, Syntacticus infrastructure, and their Universal Dependencies conversions.
- **Area:** historical-language syntax and morphology.
- **Gothic resource:** PROIEL Gothic contains roughly 57,000 tokens from Wulfila's New Testament with lemmas, morphology, and dependency syntax.
- **Why P1:** a provider-level integration is more valuable than a Gothic-only parser. The same ecosystem can expose multiple historical languages under a common dependency/morphology model.
- **Potential resource languages include:**
  - Gothic;
  - Ancient Greek;
  - Latin;
  - Old Church Slavonic;
  - Classical Armenian;
  - Old English;
  - Old French;
  - Old Russian;
  - other treebanks available in PROIEL/Syntacticus/UD.
- **Potential MCP capabilities:** treebank discovery, sentence retrieval, lemma/morphology queries, dependency-pattern queries, parallel/treebank comparison, and citation to corpus sentence IDs.
- **Important modelling rule:** preserve the distinction between original PROIEL/Syntacticus annotation and derived UD conversions where their information content differs.

## IcePaHC — Icelandic Parsed Historical Corpus

- **Upstream:** Icelandic Parsed Historical Corpus (IcePaHC), CLARIN Iceland.
- **Area:** Old Icelandic → Modern Icelandic historical syntax.
- **Scale:** about one million manually corrected words spanning texts from the 12th to 21st centuries.
- **Why P1:** provides a long diachronic syntactic corpus with a substantial medieval Old Icelandic component.
- **Useful capabilities:** syntactic construction search, historical change, lemma/morphology queries, comparison between medieval and later Icelandic.
- **Licensing:** current release is CC BY 4.0.
- **Integration option:** preferably through a general historical-treebank/UD/Syntacticus provider rather than a one-off IcePaHC MCP if practical.

## Saga Corpus

- **Upstream:** Icelandic Saga Corpus / CLARIN Iceland distribution.
- **Area:** Old Icelandic literature and corpus linguistics.
- **Scope:** 41 Old Icelandic narrative texts, approximately 1.5 million words, including Íslendingasögur and major historical compilations; POS-tagged and lemmatized.
- **Why P1:** immediately useful for lexical, stylistic, frequency, collocation, authorship and narrative-language research.
- **Important caveat:** orthography and some inflectional forms were normalized toward Modern Icelandic. Agora must not present this corpus as a diplomatic textual witness.
- **Licensing:** CC BY 4.0 distribution in the surveyed release.
- **Potential integration:** generic corpus-linguistics tooling such as Kitconc may be sufficient if the corpus is registered cleanly as a resource.

## Cleasby–Vigfusson dictionary

- **Machine-readable project:** [`stscoundrel/cleasby-vigfusson-dictionary`](https://github.com/stscoundrel/cleasby-vigfusson-dictionary)
- **Area:** Old Norse / Old Icelandic lexicography.
- **Scale:** 35,000+ entries in a machine-readable public-domain dictionary implementation.
- **Why P1:** comparatively easy integration with a well-known scholarly lexicographic source.
- **Potential use:** either a dedicated MCP or, preferably, part of an `old-norse-lexica` provider together with Zoëga and other legally distributable resources.

## Zoëga — A Concise Dictionary of Old Icelandic

- **Machine-readable project:** [`stscoundrel/old-icelandic-zoega`](https://github.com/stscoundrel/old-icelandic-zoega)
- **Area:** Old Icelandic lexicography.
- **Scale:** about 29,000 structured entries.
- **Why P1:** complementary to Cleasby–Vigfusson and straightforward to expose through a shared lexicon provider.
- **Preferred Agora modelling:** one `old-norse-lexica` plugin/provider with separate dictionary resources and source-edition metadata.

## Streitberg Gothic dictionary data

- **Machine-readable project:** [`loanwordbank/streitberggothic`](https://github.com/loanwordbank/streitberggothic)
- **Area:** Gothic lexicography.
- **Format:** CLDF dataset derived from the Wulfila digitization of Streitberg's Gothic dictionary material.
- **License:** CC BY 4.0 in the surveyed repository.
- **Why P1:** clean machine-readable Gothic lexical data with explicit source provenance.
- **Preferred integration:** resource under a future Wulfila/Gothic or historical-Germanic lexicon provider rather than an isolated tiny MCP.

## OICEN-HTR

- **Project:** [`NKCZ/OICEN-HTR`](https://github.com/NKCZ/OICEN-HTR)
- **Area:** HTR, Old Icelandic/Norse manuscripts.
- **Why P1:** unusually language- and manuscript-specific HTR models trained on Old Icelandic/Norse materials rather than generic handwriting models.
- **Surveyed model material includes:** Möðruvallabók, Codex Wormianus, Codex Regius of the Poetic Edda, Menota-derived material and related manuscript data.
- **Agora role:** HTR model/resource, not necessarily a standalone MCP. It could be exposed through a generic OCR/HTR plugin or skill that can select language/manuscript-specific models.
- **Verification focus:** model licenses, training-data licenses, supported transcription conventions, CER/WER evaluation, and compatibility with current OCR/HTR runtimes.

---

# P2 — existing but weaker integration

## Valksor Old Norse MCP

- **Provider:** `mcp.valksor.com` Old Norse service.
- **Area:** Old Norse dictionary/morphology.
- **Capabilities:** lemma lookup and substantial nominal/verbal paradigms, including definite forms and active/mediopassive verb morphology.
- **Why useful:** this is currently one of the few readily available Old Norse MCP surfaces.
- **Why P2:** lexical provenance is mainly Wiktionary; it should not be presented as equivalent to ONP, Cleasby–Vigfusson or other scholarly lexica.
- **Agora use:** acceptable as a Community/utility integration while stronger scholarly resources remain wanted integrations.

---

# Suggested provider architecture

## `old-norse-lexica`

Rather than one plugin per historical dictionary, a provider could expose:

- ONP, if API/data terms allow;
- Cleasby–Vigfusson;
- Zoëga;
- optionally additional scholarly/open lexica later.

Each dictionary should remain a separate Agora resource with its own:

- source edition;
- date;
- language stage/coverage;
- headword/sense structure;
- citation/attestation capabilities;
- data license;
- scholarly status.

## `historical-treebanks` or `syntacticus`

A shared treebank provider is preferable to separate Gothic, Old Icelandic, OCS, Latin and Greek syntax plugins when the underlying infrastructure and query model are common.

Candidate resources can include PROIEL/Syntacticus/UD Gothic, IcePaHC and other historical-language treebanks. Agora should preserve source annotation provenance and identify conversions rather than silently flattening all treebanks to UD.

## `gothic` / Wulfila provider

Gothic has enough tightly connected material to justify a coherent provider:

- Wulfila texts and annotation;
- manuscript/facsimile links;
- PROIEL/UD syntax as an associated resource;
- Streitberg dictionary data;
- TEI-aware workflows.

This would also create a natural bridge between Germanic philology and Biblical Studies.

---

# Recommended order

For Germanic philology specifically:

1. **Wulfila Project MCP — P0 wanted**
2. **ONP MCP — P0 wanted**
3. **Menota — P0 wanted**
4. **PROIEL/Syntacticus historical-treebank provider — P1**
5. **IcePaHC — P1**
6. **Cleasby–Vigfusson + Zoëga shared lexicon provider — P1**
7. **Saga Corpus — P1**
8. **OICEN-HTR — P1**
9. **Streitberg Gothic CLDF dictionary — P1**
10. **Valksor Old Norse MCP — P2 / interim utility**

The main strategic point is that Agora should not infer ecosystem weakness from the small number of dedicated MCP repositories. In Old Norse/Old Icelandic and Gothic, the scholarly digital resources are already strong; the missing layer is mostly agent-facing integration.