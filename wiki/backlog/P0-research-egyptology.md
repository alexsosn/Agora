# Egyptology Backlog

## Purpose

This document is a focused companion to [`P0-research-ecosystem-expansion.md`](P0-research-ecosystem-expansion.md). It tracks post-v0.1 Agora candidates relevant to Egyptology, Ancient Egyptian and Coptic linguistics, Demotic studies, Egyptian papyrology, hieroglyphic encoding, and HTR/OCR.

It does **not** expand the fixed v0.1 scope.

The main result of the August 2026 survey is that Egyptology has relatively few convincing dedicated MCP servers, but several unusually strong scholarly infrastructures are already machine-readable enough to support high-quality Agora integrations without scraping or inventing new data layers.

## Priority summary

### P0

1. Thesaurus Linguae Aegyptiae (TLA)
2. ORAEC + Ancient Egyptian Dictionary (AED)
3. Coptic SCRIPTORIUM + Coptic Dictionary Online

### P1

4. UD Egyptian-PC + GrewPT / Stanza
5. Ramses
6. Thot Sign List
7. JSesh
8. Trismegistos Data Services
9. Egyptological HTR/OCR datasets and models

### P2 / investigate first

10. Chicago Demotic Dictionary
11. Deir el-Medina documentary databases
12. Turin Papyrus Online Platform and related manuscript infrastructures

---

# P0 — first Egyptology integrations to investigate

## Thesaurus Linguae Aegyptiae (TLA)

- **Site:** <https://tla.digital/>
- **Area:** Ancient Egyptian corpus linguistics and lexicography
- **Scope:** major lemmatized corpus spanning Egyptian language stages and scripts, including hieroglyphic/hieratic and Demotic material.
- **Current status:** TLA corpus edition 20 was released on 20 August 2026.
- **Capabilities already exposed by the project:** text/corpus search, lemma search, lexical navigation, metadata, and machine-facing search infrastructure via SRU/FCS.
- **Interoperability direction:** project documentation/roadmap explicitly points toward raw JSON and TEI/EpiDoc-style XML access.
- **Why P0:** TLA is the most obvious flagship Egyptology provider for Agora: corpus + lexicon + annotation + stable scholarly provenance.

### Potential Agora surface

A TLA integration should aim for explicit scholarly operations rather than a generic full-text wrapper:

- `search_texts`
- `search_lemmas`
- `get_lemma`
- `get_attestations`
- `get_text`
- `get_text_metadata`
- `search_by_period`
- `search_by_genre`
- `search_by_provenance`
- `search_by_morphology`

### Verification concerns

- document the exact TLA edition/snapshot used;
- distinguish corpus text, editorial normalization, lemmatization, translation, and lexicographic layers;
- verify API/export licensing and redistribution rights independently from public web access;
- preserve TLA identifiers rather than introducing Agora-only citation IDs.

## ORAEC + Ancient Egyptian Dictionary (AED)

- **ORAEC raw corpus:** <https://github.com/oraec/corpus_raw_data>
- **AED TEI:** <https://github.com/simondschweitzer/aed-tei>
- **Area:** Ancient Egyptian texts, dictionary, TEI, linked scholarly identifiers
- **Why P0:** arguably the easiest serious Egyptology integration to implement because the relevant resources are already distributed as structured open data.

### ORAEC

The Open Richly Annotated Egyptian Corpus provides roughly 13,000 Egyptian texts with structured metadata and stable identifiers.

Important characteristics:

- machine-readable raw data;
- transcription and metadata;
- hieroglyphic encodings where available;
- mappings to TLA lemmas;
- mappings to Trismegistos and Wikidata where available;
- explicit open-data licensing;
- suitable structure for local indexing rather than scraping a website.

### AED

The Ancient Egyptian Dictionary TEI data provide more than 30,000 lexical entries with structured lexicographic information, including:

- lemmas;
- part of speech;
- translations/glosses;
- bibliography;
- controlled thesauri;
- morphology-related structures;
- links between lexical entries and encoded texts.

The TEI representation separates different annotation layers, including base text, sentence translation, word translation, and hieroglyphic encoding through stand-off annotation.

### Preferred Agora modelling

ORAEC and AED should probably be modelled as **one provider family with multiple resources**, rather than two unrelated plugins.

A useful first MCP could expose:

- text lookup/search;
- lemma lookup;
- dictionary sense/translation lookup;
- word → lemma resolution;
- lemma → attestation navigation;
- text metadata;
- TLA / Trismegistos / Wikidata cross-identifiers;
- hieroglyphic/transliteration representations;
- export of source TEI/JSON where licensing permits.

### Verification concerns

- record corpus and dictionary versions separately;
- preserve source identifiers and source-level citations;
- do not silently collapse transliteration, normalization, hieroglyphic encoding, and translation into one text field;
- verify whether all mapped external identifiers belong to the same snapshot/date.

## Coptic SCRIPTORIUM + Coptic Dictionary Online

- **Corpora:** <https://github.com/CopticScriptorium/corpora>
- **NLP:** <https://github.com/CopticScriptorium/coptic-nlp>
- **Lexicon data:** <https://github.com/KELLIA/dictionary>
- **Area:** Coptic corpus linguistics, NLP, syntax, lexicography, early Christian texts
- **Why P0:** one of the strongest ready-made philological/NLP ecosystems found in any language.

### Corpus layer

Coptic SCRIPTORIUM distributes annotated corpora in several research formats, including:

- CoNLL-U;
- TEI;
- PAULA;
- relANNIS;
- TreeTagger-style formats.

Depending on corpus/version, annotation includes:

- tokenization/segmentation;
- lemmas;
- morphology/POS;
- syntactic dependencies;
- named entities and other higher-level annotation in some resources.

### NLP layer

The `coptic-nlp` project provides a reproducible processing pipeline for Coptic. Agora should distinguish **gold/manual corpus annotations** from **predicted NLP output**.

### Lexicon layer

The Comprehensive Coptic Lexicon / Coptic Dictionary Online data are distributed in structured TEI and combine native Coptic vocabulary with Greek loanwords. Stable lexical identifiers and mappings to broader Egyptian lexical infrastructure make this potentially useful for diachronic Egyptian → Coptic research.

### Preferred Agora modelling

One `coptic-scriptorium` provider could expose multiple resources/capabilities:

- corpora;
- dictionary/lexicon;
- NLP pipeline;
- syntax/treebank queries;
- text/entity search.

Do not create separate marketplace plugins for each data format.

### Biblical/Christian-studies relevance

This is also a high-value Biblical Studies / early-Christianity integration because the corpora include biblical, monastic, patristic, documentary, and related Coptic material.

---

# P1 — strong candidates

## UD Egyptian-PC + GrewPT / Stanza

- **Treebank:** <https://github.com/UniversalDependencies/UD_Egyptian-PC>
- **Area:** pre-Coptic Egyptian syntax and NLP
- **Scope:** manually annotated Pyramid Text material in Universal Dependencies format.
- **Initial survey scale:** about 34,000 manually annotated tokens / 3,000+ sentences.
- **Capabilities:** lemmas, morphology, POS, dependency syntax.
- **Related tooling:** queryable through UD/Grew infrastructure and usable as the basis for Stanza parsing models.

### Why P1

This is the clearest path to an **Egyptian syntax/NLP provider** rather than text-only search.

### Preferred architecture

Avoid a one-off Egyptian-PC MCP if Agora later gains a generic **Universal Dependencies / Syntacticus / historical treebanks provider**. Egyptian-PC should then be a first-class resource under that provider.

## Ramses

- **Site:** <https://ramses.ulg.ac.be/>
- **Area:** Late Egyptian corpus linguistics
- **Scope:** large annotated Late Egyptian corpus with thousands of texts and hundreds of thousands of word occurrences.
- **Annotation includes:** hieroglyphic spelling, transliteration, lemma, morphology, translation, and metadata.
- **Why P1:** one of the richest language-stage-specific Egyptian corpora.

### Caveat

The public interface/beta exposes only part of the complete project corpus, so Agora needs to verify:

- what is openly queryable;
- what can be programmatically accessed;
- whether bulk or API access is permitted;
- citation/provenance granularity;
- redistribution restrictions.

## Thot Sign List

- **Site:** <https://thotsignlist.org/>
- **Area:** hieroglyphic sign ontology and palaeographic/sign-function research
- **Provider context:** collaborative Liège/Berlin Egyptological infrastructure.
- **Why P1:** substantially richer than a simple Gardiner sign list.

### Important distinction

The resource distinguishes concepts such as:

- abstract signs;
- graphic variants;
- functions/values;
- actual contextual sign tokens;
- scholarly references and attestations.

This ontology should be preserved in Agora rather than flattened to `sign -> transliteration`.

### Potential Agora capabilities

- sign lookup by identifier;
- search by value/function;
- variant navigation;
- attestations/examples;
- sign-family relations;
- mapping to Unicode/Gardiner/JSesh identifiers where supported.

## JSesh

- **Project:** <https://github.com/rosmord/jsesh>
- **Area:** hieroglyphic encoding, Manuel de Codage, rendering
- **Why P1:** deterministic technical infrastructure useful across many Egyptology workflows.

### Potential Agora role

JSesh should be treated as a **tool provider**, not a scholarly corpus.

Possible capabilities:

- MdC parsing;
- MdC ↔ Unicode conversion where supported;
- hieroglyphic rendering;
- sign lookup;
- sign-list conversion/normalization;
- validation of encoded strings.

This could complement TLA/ORAEC rather than duplicate them.

## Trismegistos Data Services

- **Site:** <https://www.trismegistos.org/dataservices/>
- **Area:** texts, people, places, archives, identifiers, papyrology
- **Why P1 for Egyptology:** Trismegistos is foundational infrastructure for documentary texts from Egypt and the wider ancient world.

### Relevant capabilities

- identifier resolution;
- people/person attestations;
- place resolution;
- text metadata;
- archives;
- RDF/linked-data workflows.

Agora should prefer the newer open **Data Services/API** layer over scraping normal Trismegistos pages.

### Architecture note

This should remain one provider usable by Egyptology, papyrology, epigraphy, Biblical Studies, Classics, and prosopography rather than becoming an Egyptology-only plugin.

## Hieroglyphic HTR/OCR datasets and models

- **Example data project:** <https://github.com/imak-ai-lab/egyptian-hieroglyph-datasets>
- **Area:** hieroglyph recognition, line/sign detection, multimodal transcription
- **Recent datasets:** MEH, MMM, MuMMy and related resources surfaced in the 2025–2026 survey.

### Why P1

These resources make it possible to build reproducible OCR/HTR evaluation and manuscript/inscription workflows rather than relying on opaque image-to-text LLM prompting.

### Agora policy

HTR/OCR resources must expose:

- model/dataset version;
- training/evaluation provenance;
- sign inventory;
- segmentation assumptions;
- confidence where available;
- explicit distinction between recognized hieroglyphs, transliteration, and translation.

An image model that detects signs and then asks an LLM to “translate hieroglyphs” should remain Experimental and must not be presented as equivalent to scholarly TLA/AED data.

---

# P2 / investigate before promoting

## Chicago Demotic Dictionary (CDD)

- **Site:** <https://isac.uchicago.edu/research/projects/chicago-demotic-dictionary-cdd-0>
- **Area:** Demotic lexicography
- **Scholarly value:** extremely high.
- **Why not P0/P1 implementation yet:** much of the public dictionary is distributed as letter-by-letter PDF publication rather than a clearly documented machine-readable lexicon/API.

### Backlog action

Investigate whether structured internal/public data or an API is available before considering OCR/PDF extraction. A PDF-scraped MCP would be a poor substitute for cooperation with the source project.

## Deir el-Medina documentary databases

- **Area:** ostraca, papyri, workmen's community, Late Egyptian documentary texts
- **Why relevant:** unusually rich contextual/documentary material combining texts, people, objects and provenance.

### Backlog action

Identify the best maintained databases, machine interfaces, licensing, and stable identifiers before choosing a provider.

## Turin Papyrus Online Platform and related manuscript infrastructures

- **Area:** Egyptian papyri/manuscripts, cataloguing, images
- **Why relevant:** strong object/manuscript metadata and image context.
- **Backlog action:** verify programmatic access, IIIF support, licensing and reusable identifiers before ranking higher.

---

# Candidate Agora taxonomy for Egyptology

Egyptology resources cross several existing Agora categories and should not be forced under a single `egyptology` type.

Useful tags/capabilities include:

- `egyptology`
- `ancient-egyptian`
- `middle-egyptian`
- `late-egyptian`
- `demotic`
- `coptic`
- `hieroglyphic`
- `hieratic`
- `lexicon-dictionary`
- `corpus`
- `morphology`
- `dependency-syntax`
- `transliteration`
- `sign-ontology`
- `tei`
- `epidoc`
- `papyrology`
- `prosopography`
- `htr-ocr`
- `manuscript-images-iiif`

## Egyptology-specific metadata

Useful resource fields include:

- language stage;
- script(s);
- transliteration convention;
- encoding convention: MdC, Unicode, project-specific sign IDs;
- text type/genre;
- chronological range;
- findspot/provenance;
- object/manuscript identifier;
- TLA identifier;
- Trismegistos identifier;
- lemma inventory/version;
- lexical source/version;
- annotation status: manual/editorial vs predicted/generated;
- hieroglyphic representation availability;
- translation status/source;
- palaeographic/sign-level annotation;
- image/IIIF availability.

## Representation rule

Agora should avoid a single ambiguous `text` field for Egyptian resources.

Where available, preserve separately:

- source transcription;
- transliteration;
- normalized linguistic form;
- lemma;
- hieroglyphic encoding;
- translation;
- editorial/restoration markup;
- token/sign alignment.

This is particularly important because different resources intentionally represent different editorial layers.

---

# Recommended Egyptology implementation sequence

Subject to licensing/API verification:

1. **ORAEC/AED** — easiest high-quality local/open-data integration.
2. **Coptic SCRIPTORIUM + Coptic Dictionary Online** — mature corpus + lexicon + NLP stack.
3. **TLA** — flagship scholarly provider; API/export feasibility first.
4. **UD Egyptian-PC** through a generic UD/historical-treebank provider.
5. **Thot Sign List**.
6. **JSesh** tooling.
7. **Trismegistos Data Services**.
8. **Ramses**, depending on programmatic access terms.
9. **HTR/OCR datasets/models** as research resources rather than default transcription authorities.
10. **CDD / Deir el-Medina / Turin papyri** after access/licensing investigation.

The preferred architecture is therefore not one giant `egyptology-mcp`. Agora should combine several provider types: corpus/lexicon providers, a sign/encoding tool provider, generic papyrological linked data, generic historical treebanks, and HTR/OCR resources.
