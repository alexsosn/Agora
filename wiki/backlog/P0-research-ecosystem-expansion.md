# Ecosystem Backlog: Post-v0.1 Expansion Candidates

## Purpose

This document tracks candidate plugins, providers, resources, skills, and missing integrations for Agora **after the fixed v0.1 scope**.

It is deliberately separate from [`v0.1-scope-frozen.md`](../releases/v0.1-scope-frozen.md) and does not expand the first-release requirement. The v0.1 plugin families remain Context-Fabric, Perseus, Sefaria, and SEDRA.

The backlog is based on ecosystem research conducted in August 2026 across MCP servers, scholarly corpora, NLP projects, lexica, digital libraries, manuscript infrastructure, and agent skills relevant to philology and adjacent disciplines.

The main lesson from the survey is that useful projects are often not labelled `philology` or `digital humanities`. They appear under the names of a canon, language, archive, NLP toolkit, dictionary, museum, or technical standard. Agora therefore needs category-driven discovery rather than relying on repository keywords alone.

## Backlog principles

Candidates should be evaluated on more than whether an MCP endpoint starts successfully.

For every candidate, Agora should record separately:

- **integration/runtime status** — installability, MCP initialization, tool health, transport, versioning;
- **scholarly/data status** — provenance, editorial authority, corpus quality, annotation quality, reproducibility;
- **software license**;
- **content/data license**;
- **redistribution rights**;
- **remote-service terms and authentication requirements**;
- **citation/publication information**;
- **maintenance/activity**;
- **scope and overlap with existing Agora plugins**;
- **epistemic profile**, where relevant: critical scholarly resource, institutionally curated resource, community resource, confessional/devotional resource, generated/experimental layer, or mixed.

Star counts are useful only as weak evidence. Several of the most relevant projects are new and technically substantial despite having very little GitHub adoption.

## Priority legend

- **P0 — investigate for the first post-v0.1 expansion**: unusually high scholarly value, broad utility, strong institutional provenance, or an important capability gap.
- **P1 — strong candidate**: clearly useful and sufficiently concrete to justify verification work.
- **P2 — experimental or narrower candidate**: useful niche, young project, overlapping implementation, or quality/provenance requiring substantial validation.
- **Wanted integration**: no satisfactory MCP/plugin was found, but the upstream scholarly resource is important enough that Agora should track or solicit an implementation.

---

# P0 — first post-v0.1 investigation batch

## Scholarly text and philology infrastructure

### TEI MCP

- **Project:** [`Pantagrueliste/tei-mcp`](https://github.com/Pantagrueliste/tei-mcp)
- **Area:** TEI, digital editions, textual encoding
- **Why P0:** one of the clearest generic digital-philology MCPs found.
- **Capabilities:** TEI P5 element/class/macro/module lookup, inherited attributes, content-model expansion, nesting checks, document/element validation, ODD support, deprecated construct detection, regex search, attribute suggestions, and span-locked composition that preserves source text bytes.
- **Initial status:** strong candidate for Verified after runtime/tool testing.
- **License:** MIT.

### IIIF MCP

- **Project:** [`code4history/IIIF_MCP`](https://github.com/code4history/IIIF_MCP)
- **Area:** manuscripts, images, digital collections
- **Capabilities:** IIIF Presentation v2/v3, Content Search, Image API, annotations/transcriptions, ranges/TOC, collections/canvases, Content State, Change Discovery, authentication, AV, image regions.
- **Why P0:** generic access layer for many manuscript and rare-book repositories without one plugin per institution.
- **Verification focus:** compatibility across several independent IIIF providers and versions.

### Transkribus MCP

- **Project:** [`lazyants/transkribus-mcp-server`](https://github.com/lazyants/transkribus-mcp-server)
- **Area:** HTR/OCR, manuscripts, transcription workflows
- **Capabilities:** large tool surface covering collections, documents, transcription, layout, recognition models, jobs, users, search, PyLaia/P2PaLA workflows, keyword spotting.
- **Why P0:** the most substantial HTR-oriented MCP found.
- **Caveat:** currently targets the legacy Transkribus TrpServer REST API rather than the newer Processing API v2.
- **License:** FSL-1.1-MIT for current versions; older 1.x versions MIT.

### Zotero MCP

- **Project:** [`54yyyu/zotero-mcp`](https://github.com/54yyyu/zotero-mcp)
- **Area:** bibliography, research workflow
- **Capabilities:** local/Web Zotero integration, semantic search, PDFs, annotations, citation-aware research workflows.
- **Why P0:** strong adoption and obvious cross-disciplinary value.
- **Policy:** choose one canonical/default Zotero integration rather than listing many near-equivalent wrappers as peers.

### Wikidata MCP

- **Project:** [`wmde/WikidataMCP`](https://github.com/wmde/WikidataMCP)
- **Area:** linked data, entities, prosopography, authority control
- **Provider:** Wikimedia Deutschland.
- **Why P0:** institutionally maintained and preferable as the default Wikidata entry over personal wrappers.
- **Hosted endpoint:** `https://wd-mcp.wmcloud.org/`.

## Islamic studies and Arabic textual scholarship

### Quran Foundation MCP

- **Project:** [`quran/quran-mcp`](https://github.com/quran/quran-mcp)
- **Area:** Qurʾānic studies, Arabic NLP, tafsir
- **Provider:** Quran Foundation / Quran.com ecosystem.
- **Capabilities:** Arabic text in multiple qirāʾāt, many translations, classical and modern tafsir, full-text search, morphology, roots, paradigms, mushaf rendering.
- **Why P0:** broad, maintained, domain-native Qurʾān integration.
- **Verification focus:** distinguish textual data, exegetical resources, generated layers, and licensing by resource.

### Tafsir Center MCP

- **Project:** [`tafsircenter/tafsir-mcp`](https://github.com/tafsircenter/tafsir-mcp)
- **Area:** Qurʾānic studies, tafsir, qirāʾāt, Arabic linguistics
- **Provider:** Tafsir Center for Quranic Studies.
- **Capabilities:** classical tafsirs, word-level linguistic analysis, qirāʾāt, asbāb al-nuzūl, Arabic search.
- **Why P0:** unusually strong institutional/domain provenance for a specialized religious-studies MCP.
- **License:** MIT code; verify data terms separately.

### Shamela MCP

- **Project:** [`alhoqbani/shamela-mcp`](https://github.com/alhoqbani/shamela-mcp)
- **Area:** Islamic studies, classical Arabic, bibliography
- **Backend:** Maktaba al-Shamela 4.
- **Capabilities:** search, books/authors/categories, page/chapter/index retrieval, root/morphological search, Qurʾān/tafsir/hadith linking, citation formatting.
- **Why P0:** broad access to a major Arabic/Islamic textual library; active development and nontrivial adoption.
- **Verification focus:** local data requirements, source editions, content rights, and reproducible citation addressing.

### Turath MCP

- **Project:** [`opin22/turath-mcp`](https://github.com/opin22/turath-mcp)
- **Area:** Islamic studies, classical Arabic
- **Backend:** Turath / Nuqayah ecosystem.
- **Claimed scope:** 8,500+ books across tafsir, hadith, fiqh, usul, Arabic language, biography, and history.
- **Why P0:** potentially very high scholarly utility despite low current adoption.
- **Verification focus:** upstream data provenance, API stability, edition metadata, licensing, and search/citation granularity.

## Buddhist studies

### FoJin MCP

- **Project:** [`xr843/fojin`](https://github.com/xr843/fojin)
- **Area:** Buddhist studies, Chinese/Pāli/Tibetan/Sanskrit textual research
- **Scope:** aggregates CBETA, SuttaCentral, 84000, BDRC, SAT, GRETIL and other sources.
- **Capabilities:** cross-canon search, passage retrieval, parallels, dictionaries, entities, stable URNs.
- **Claimed scale:** 10,500+ texts from hundreds of sources, dozens of dictionaries, and a large entity graph.
- **Why P0:** one of the broadest specialist religion/philology MCPs found.
- **License:** Apache-2.0 code; verify data licenses per upstream.

### Tripitaka MCP

- **Project:** [`dhamma-seeker/tripitaka-mcp`](https://github.com/dhamma-seeker/tripitaka-mcp)
- **Area:** Pāli, Buddhist studies
- **Capabilities:** full Pāli Tipiṭaka search, Sutta/Vinaya/Abhidhamma, aligned translations, keyword/trigram/semantic/hybrid search, cross-references, citations, dictionary bridge, inflection fallback.
- **Lexica:** DPD, PTS, DPPN, Payutto-related layers depending on installation/data.
- **Why P0:** strong corpus + lexicon + retrieval integration.
- **Caveat:** code and textual data have different licensing/usage terms, including non-commercial restrictions in some distributed content.

## Ancient Near East and ancient-language NLP

### eme-gir

- **Project:** [`jenova-marie/eme-gir`](https://github.com/jenova-marie/eme-gir)
- **Area:** Sumerian, Assyriology
- **Components:** ePSD2, ETCSL, CDLI, OGSL, and teaching/grammar surfaces.
- **Capabilities:** dictionary and corpus lookup, attestations, transliteration/morphology, sign information, artifact metadata, source/provenance links.
- **Why P0:** unusually coherent bridge from lexicon → attestation → text → artifact.
- **Verification focus:** confirm data snapshots and licensing for each bundled/upstream resource.

### pyaegean / aegean-mcp

- **Project:** [`ryanpavlicek/pyaegean`](https://github.com/ryanpavlicek/pyaegean)
- **Area:** Ancient Greek NLP, Aegean scripts, epigraphy, papyrology
- **MCP:** installed via the package's MCP extra as `aegean-mcp`.
- **Capabilities:** Ancient Greek tokenization, POS, morphology, lemmatization, dependency parsing, scansion, IPA, dialect/register, inflection synthesis, dictionaries, corpus loading, EpiDoc/CoNLL-U/JSON-LD export, NLP interoperability.
- **Additional resources:** Linear A, Linear B, Cypriot, Cypro-Minoan; fetchable Greek literature; several inscription corpora; DDbDP papyri; EDH Greek subset.
- **Why P0:** combines language-specific NLP with actual scholarly corpora and provenance-aware interchange.
- **Caveat:** young project; undeciphered-script analysis is explicitly exploratory and should remain so in Agora metadata.

### UralicMCP / UralicNLP

- **Project:** [`mikahama/uralicNLP`](https://github.com/mikahama/uralicNLP)
- **Area:** historical/endangered language NLP, Uralic languages
- **Capabilities:** deterministic morphological analysis, generation, lemmatization and dictionaries across many Uralic languages.
- **Why P0:** established academic NLP project with an MCP layer and published research, not merely an LLM wrapper.

## Corpus linguistics

### Kitconc

- **Project:** [`ilexistools/kitconc`](https://github.com/ilexistools/kitconc)
- **Area:** corpus linguistics
- **Capabilities:** corpus creation, frequency lists, keywords, KWIC, collocations, clusters, n-grams, dispersion, semantic search.
- **Why P0:** complements prebuilt scholarly corpora by analyzing arbitrary researcher-provided corpora.

---

# P1 — strong candidates

## Libraries, archives, newspapers, and collection access

### Gallica MCP

- **Project:** [`nestordemeure/gallica-mcp`](https://github.com/nestordemeure/gallica-mcp)
- **Area:** historical books, periodicals, OCR, bibliography
- **Capabilities:** Gallica/BnF search with creator/type/year/language/title/subject/publisher/library/OCR-quality filters; page OCR retrieval and caching.
- **Bundled skill:** Gallica search workflow.
- **License:** Apache-2.0.

### Internet Archive MCP

- **Project:** [`smeet666/mcp-archiveorg`](https://github.com/smeet666/mcp-archiveorg)
- **Area:** digitized books, historical documents, OCR
- **Capabilities:** metadata search plus `search_inside` over OCR text; Open Library and Wayback-related functionality.
- **Why P1:** full-text OCR search is substantially more useful for philology than metadata-only archive wrappers.

### Historical Newspapers MCP

- **Project:** [`raphink/newspapers-mcp`](https://github.com/raphink/newspapers-mcp)
- **Area:** reception history, historical linguistics, cultural history
- **Scope:** unified search across many national newspaper archives including Europeana, Gallica, DDB, ANNO, Delpher, Chronicling America, Trove and others.
- **Capabilities:** archive search, snippets/OCR/image retrieval where supported.

### OpenArchives MCP

- **Project:** [`coret/openarchieven-mcp-server`](https://github.com/coret/openarchieven-mcp-server)
- **Area:** Dutch historical archives, genealogy, local history
- **Capabilities:** archive records, census, transcribed historical pages, hierarchy browsing, IIIF transcription viewer.

### History Lab MCP

- **Project:** [`history-lab/history-lab-mcp`](https://github.com/history-lab/history-lab-mcp)
- **Area:** modern historical archives
- **Scope:** declassified/FOIA historical-document corpus.
- **Why P1:** useful adjacent research infrastructure, though less philology-specific.

## Prosopography, objects, and material culture

### DPRR MCP

- **Project:** [`gillisandrew/dprr-mcp`](https://github.com/gillisandrew/dprr-mcp)
- **Area:** Roman prosopography
- **Capabilities:** natural-language prosopographic queries → validated SPARQL over Digital Prosopography of the Roman Republic RDF, with uncertainty/source handling.
- **Caveat:** DPRR data CC BY-NC 4.0; code license/provenance needs review.

### acsearch MCP

- **Project:** [`wushanyun64/acsearch-mcp`](https://github.com/wushanyun64/acsearch-mcp)
- **Area:** numismatics
- **Capabilities:** ancient coin auction search, lot details, price history, comparables.
- **Caveat:** some functionality requires paid acsearch access; remote-service terms matter.

### Rijksmuseum MCP+

- **Project:** [`kintopp/rijksmuseum-mcp-plus`](https://github.com/kintopp/rijksmuseum-mcp-plus)
- **Area:** art history, inscriptions, provenance, museum objects
- **Capabilities:** semantic/full-text search, provenance, inscriptions/marks, similarity, spatial search, research scenarios.
- **Note:** inscription search is based on catalog-entered data, not OCR.

### Smithsonian MCP

- **Project:** [`molanojustin/smithsonian-mcp`](https://github.com/molanojustin/smithsonian-mcp)
- **Area:** museum collections, material culture
- **Scope:** Smithsonian collections across many museums.

### Metropolitan Museum MCP

- **Project:** [`mikechao/metmuseum-mcp`](https://github.com/mikechao/metmuseum-mcp)
- **Area:** museum collections, archaeology, art history

### Städel MCP

- **Project:** [`topoftheblock/staedel-mcp`](https://github.com/topoftheblock/staedel-mcp)
- **Area:** museum collections
- **Backend:** OAI-PMH/LIDO.

## Biblical studies, Judaica, and Christian studies

### SHEBANQ MCP

- **Project/source:** original `Jossifresben/shebanq-mcp`; fork known as [`tonyjurg/FORK_shebanq-mcp`](https://github.com/tonyjurg/FORK_shebanq-mcp)
- **Area:** Biblical Hebrew, BHSA, syntax
- **Capabilities:** natural-language → MQL, direct read-only MQL, BHSA feature lookup, and newer TF conversion/equivalent workflows in surfaced versions.
- **Why P1:** reproducible query generation over BHSA is highly relevant.
- **Verification focus:** locate/choose a maintained canonical upstream before registry inclusion.

### bible-mcp

- **Project:** [`nirajagarwal/bible-mcp`](https://github.com/nirajagarwal/bible-mcp)
- **Area:** Biblical studies, patristics, historical theology
- **Current resources:** Bible translations, Greek LXX, MACULA Hebrew/Aramaic/Greek morphology, cross-references, Apostolic Fathers, Irenaeus, Justin Martyr, Augustine and other public-domain works.
- **Capabilities:** semantic/hybrid search, word study, interlinear display, patristic → scripture citation graph, entity lookup, research prompts/skills.
- **Why P1:** unusually research-oriented despite being very new.
- **Caveat:** non-commercial licensing layers and generated research-output layers must be clearly separated from primary sources.

### unfoldingWord Translation Helps MCP

- **Project:** [`unfoldingWord/translation-helps-mcp`](https://github.com/unfoldingWord/translation-helps-mcp)
- **Area:** Bible translation, translation studies
- **Why P1:** organization-maintained integration of Door43 translation resources.

### Torch & Lily

- **Project/data:** [`joshx2415/torch-data`](https://github.com/joshx2415/torch-data)
- **Area:** Catholic theology, patristics, commentary traditions
- **Known scope:** Vulgate/Douay-Rheims, Summa Theologiae, patristic/medieval commentary and intertextual links.
- **Backlog action:** verify the advertised MCP endpoint/surface separately before registering.

## Other religious studies

### Open Granth

- **Project:** [`opengranth/open-granth`](https://github.com/opengranth/open-granth)
- **Area:** Sikh studies, Punjabi/Gurmukhi
- **Capabilities:** Guru Granth Sahib text, transliteration, English layer, source-location verification for quotations.
- **Why P1:** unusually clear provenance distinction between authoritative text, generated transliteration and third-party translation.
- **Caveat:** very new project.

### buddha-cli / daizo MCP

- **Project:** [`sinryo/buddha-cli`](https://github.com/sinryo/buddha-cli)
- **Area:** Buddhist studies, Sanskrit, Pāli, Tibetan, Chinese
- **Sources:** CBETA, Tipiṭaka, GRETIL, SARIT, SAT, MUKTABODHA, BUDA/BDRC, Adarshah and others.
- **Why P1:** broad local/search tooling complementary to FoJin and Tripitaka MCP.

### Chinese History MCP

- **Project:** [`lizhuojunx86/chinese-history-mcp`](https://github.com/lizhuojunx86/chinese-history-mcp)
- **Area:** Classical Chinese, Chinese historiography
- **Scope:** several canonical historical/philosophical works with citable book/chapter/paragraph addressing.
- **Positive feature:** machine punctuation/translation and review status are explicitly labelled rather than silently mixed with source text.

## Lexicons and dictionaries

### Logeion MCP

- **Project:** [`Corykidios/logeionicon_mcp`](https://github.com/Corykidios/logeionicon_mcp)
- **Area:** Ancient Greek lexicography
- **Resources:** LSJ, Middle Liddell, Autenrieth, Cunliffe, Slater, Abbott-Smith, DGE, Bailly, Betant and morphology-related lookup depending on source.
- **Why P1:** best current route found toward the Logeion lexicographic ecosystem.
- **Verification focus:** upstream/API method, source-edition attribution, exact dictionary coverage, and licensing.

### Greek Lexicon / morphosyntax MCP

- **Project:** [`wmotte/llm_tool_greek_lexicon`](https://github.com/wmotte/llm_tool_greek_lexicon)
- **Area:** Ancient/Koine Greek lexicography and morphosyntax
- **Capabilities:** scholarly Greek lexicon represented as a Neo4j graph for LLM tool use.
- **Why P1:** language-specific analytical lexicon rather than a generic dictionary wrapper.

### Arabic Dictionary MCP

- **Project:** [`arnizamani/arabic-dict-mcp`](https://github.com/arnizamani/arabic-dict-mcp)
- **Area:** Arabic lexicography and morphology
- **Data:** Arramooz plus Lane-derived Qurʾānic-root material.
- **Capabilities:** diacritic-insensitive surface lookup, roots, POS, wazn, definitions/search.
- **Positive feature:** explicitly documents code/data license asymmetry and treats optional Hans Wehr ingestion as copyrighted personal-use material rather than redistributable data.

### Digital Pāli Dictionary MCP

- **Project:** [`thiravadhano/DPD-MCP-Server`](https://github.com/thiravadhano/DPD-MCP-Server)
- **Area:** Pāli lexicography
- **Capabilities:** DPD lookup, inflected forms, compounds, sandhi.
- **Caveat:** very small/new project and no clearly declared license in the initial survey; verify before inclusion.

### Valksor dictionary provider

- **Provider hub:** [`mcp.valksor.com`](https://mcp.valksor.com/)
- **Area:** language-specific dictionaries/morphology
- **Resources found:** Latin, Old Church Slavonic, Old Norse, Old English, Livonian, Latgalian, Proto-Scythian, Interslavic.
- **Preferred Agora modelling:** one provider/plugin family with separate language resources, not unrelated marketplace entries.
- **Quality note:** provenance varies substantially by language. Some are Wiktionary-based; the Livonian integration is notably stronger because it uses University of Latvia Livonian Institute lexicographic/morphology databases.
- **Verification focus:** audit each resource independently; do not assign one scholarly status to the whole provider.

### Sefaria lexicon resources

- **Existing Agora plugin:** Sefaria.
- **Backlog action:** expose/tag dictionary capability explicitly rather than treating it as incidental.
- **Important resources:** Jastrow, BDB Hebrew, BDB Aramaic, Klein, Kimhi's Sefer ha-Shorashim, Sefer he-Arukh and other historical lexical works available through Sefaria's lexicon APIs.
- **Modelling implication:** lexica can be resources under an existing plugin rather than separate plugins.

## NLP and language technology

### Sketch Engine MCP + skill

- **Skill/project:** [`techczech/sketchengine-skill`](https://github.com/techczech/sketchengine-skill)
- **Area:** corpus linguistics, CQL, Word Sketch, frequency/keywords
- **Why P1:** powerful scholarly corpus infrastructure and useful domain skill.
- **Caveat from initial survey:** several upstream MCP tools reportedly failed smoke testing, including concordance/CQL paths. Treat as Community/Experimental until independently verified.

## Generic scholarly research infrastructure

### OpenAlex MCP

Candidate implementations:

- [`oksure/openalex-research-mcp`](https://github.com/oksure/openalex-research-mcp)
- [`carsten-streb/openalex-mcp`](https://github.com/carsten-streb/openalex-mcp)
- [`cyanheads/openalex-mcp-server`](https://github.com/cyanheads/openalex-mcp-server)

**Backlog action:** benchmark and select one canonical/default OpenAlex integration. Do not list all three as equivalent without a reason.

### OpenPapers MCP

- **Project:** [`Kaago/openpapers-mcp`](https://github.com/Kaago/openpapers-mcp)
- **Area:** scholarly literature discovery and OA retrieval
- **Backends:** OpenAlex, Crossref, Unpaywall.
- **Positive feature:** explicit legal/OA PDF retrieval and security checks.

### Open Library MCP

- **Project:** [`8enSmith/mcp-open-library`](https://github.com/8enSmith/mcp-open-library)
- **Area:** bibliography/book metadata
- **Note:** metadata access rather than full-text research; lower priority than Internet Archive for text-centric use.

### MediaWiki MCP

- **Project:** [`ProfessionalWiki/MediaWiki-MCP-Server`](https://github.com/ProfessionalWiki/MediaWiki-MCP-Server)
- **Area:** generic scholarly/community wikis
- **Why P1:** provider-level integration could expose many research wikis without bespoke wrappers.

---

# P2 — experimental, overlapping, or narrow candidates

## Ancient Near East

### cuneiform-mcp

- **Project:** [`Hugegreencandle/cuneiform-mcp`](https://github.com/Hugegreencandle/cuneiform-mcp)
- **Area:** Assyriology/cuneiform
- **Claimed scope:** large tool inventory spanning CDLI, ORACC, OGSL, eBL/Fragmentarium-related workflows, entities, manuscripts, joins, geospatial analysis and palaeographic/source-aware queries.
- **Why P2 despite scope:** the surface is unusually broad for a young project and needs serious end-to-end verification before Agora should attach a high trust label.
- **Action:** test a representative sample against authoritative upstreams and check whether claimed joins are reproducible.

### Harris Matrix MCP

- **Project:** [`openhistorymap/harris-mcp`](https://github.com/openhistorymap/harris-mcp)
- **Area:** archaeology, stratigraphy
- **Capabilities:** parse/audit/edit Harris matrices and related formats.
- **Why P2:** useful niche adjacent to philology rather than core textual work.

## Biblical studies

### textual-criticism-mcp

- **Project:** [`NoveltyDreams/textual-criticism-mcp`](https://github.com/NoveltyDreams/textual-criticism-mcp)
- **Claimed resources:** BHSA/N1904 morphology/syntax, STEPBible apparatus-like data, variants, lexica/concordance.
- **Caveat:** young, no adoption, and README/template signs require source-level validation before trust.

### biblical-linguistics-mcp

- **Project:** [`mpduarte/biblical-linguistics-mcp`](https://github.com/mpduarte/biblical-linguistics-mcp)
- **Claimed capabilities:** Hebrew/Greek word study, morphology, roots, cross-references, LXX alignment, translations.
- **Caveat:** very young and some claimed provenance/alignments were not immediately explained by listed sources.

### PTXprint MCP

- **Project:** [`klappy/ptxprint-mcp`](https://github.com/klappy/ptxprint-mcp)
- **Area:** Bible typesetting and production workflows
- **Why P2:** valuable for translation/edition production but peripheral to textual analysis.

## Chinese / Sanskrit / scripture wrappers

### Shuge MCP

- **Project:** [`Mocooa/shuge-mcp-server`](https://github.com/Mocooa/shuge-mcp-server)
- **Area:** Chinese rare books
- **Capabilities:** search/details/categories/tags/download/latest over the Shuge digital library.
- **Caveat:** very young/small MCP wrapper.

### Sacred Scriptures MCP

- **Project:** [`Traves-Theberge/sacred-scriptures-mcp`](https://github.com/Traves-Theberge/sacred-scriptures-mcp)
- **Area:** comparative religion
- **Why P2:** currently broad but shallow; several advertised traditions are roadmap items rather than scholarly corpus integrations. Do not treat it as equivalent to domain-specific projects such as FoJin or Quran MCP.

### Sanskrit demo/tooling wrappers

- **Example surfaced:** `akulasairohit/Sanskrit`
- **Reason for low priority:** appears closer to a demo/LLM wrapper with limited curated passages and model-generated analysis than a stable scholarly Sanskrit corpus or lexicon service.

## Low-information classics wrappers

### MIT Classics MCP

- **Project:** [`Awzy11/mit-classics-mcp`](https://github.com/Awzy11/mit-classics-mcp)
- **Area:** classical texts
- **Reason for low priority:** tiny wrapper around the MIT Internet Classics Archive; much weaker scholarly/data surface than Perseus, First1KGreek, or pyaegean.

### Latin-only older Logeion wrapper

- **Project:** [`philipaidanbooth/Logeion-mcp-server`](https://github.com/philipaidanbooth/Logeion-mcp-server)
- **Reason for low priority:** narrower/older implementation, requires separate SQLite data, and is less compelling than the broader Logeion-oriented candidate above.

---

# Research skills backlog

Skills should be catalogued separately from data/tool providers when they add reusable scholarly procedure rather than new data access.

## P1 skills

### Digital Humanity Skills

- **Project:** [`Shuke1999/digital-humanity-skills`](https://github.com/Shuke1999/digital-humanity-skills)
- **Scope:** corpus building, digital editions, archival work, cultural analytics, DH writing/review workflows.
- **Caveat:** prompt-only suite and no declared license in the initial survey; verify redistribution terms.

### OCR Skill

- **Project:** [`hec-ovi/ocr-skill`](https://github.com/hec-ovi/ocr-skill)
- **Scope:** local image/PDF → Markdown OCR using DeepSeek-OCR-2; portable `SKILL.md`, CLI, paging and explicit fencing of untrusted OCR content.
- **Why useful:** scholarly workflow skill without pretending OCR output is authoritative source text.

### Research Hub / Zotero skills ecosystem

- **Projects:** Wenyu Chiou's `research-hub`, `zotero-skills`, `ai-research-skills` and related academic workflow skills.
- **Use:** research organization, Zotero/Obsidian/NotebookLM integration, academic writing and review.
- **Agora position:** `Research workflow`, not core philology.

### Zotero-specific skills

Examples surfaced:

- `dougwyu/claude-zotero-skills`
- `Bubble-OoO/zotero-research-assistant-skill`
- `guoxh/zotero-interface-skill`
- `ketthub/zotero-skill`

**Backlog action:** evaluate as companion skills to the selected canonical Zotero MCP rather than independent marketplace priorities.

### Academic writing/review skills

Examples:

- `YSLAB-ai/manuscript-writing`
- `mronkko/claude-academic-research`
- `AlterLab-IEU/AlterLab-Academic-Skills`
- `drarunmitra/research-skills`

**Agora position:** broad research workflow; useful but lower priority than domain data and language tools.

---

# Wanted integrations — important upstreams without satisfactory MCPs

These are not failures of the upstream projects. They are opportunities where a major scholarly resource currently lacks a convincing agent-facing integration.

## Papyrology and epigraphy

### papyri.info / DDbDP / HGV / DCLP / APIS

- **Upstream:** [`papyri/idp.data`](https://github.com/papyri/idp.data) and papyri.info infrastructure.
- **Why wanted:** core papyrological source data in EpiDoc/RDF, with major integrated collections.
- **Opportunity:** open GitHub-hosted data makes a principled MCP possible without scraping rendered pages.
- **Partial coverage:** pyaegean can already fetch/search DDbDP, but this is not a substitute for the full papyri.info semantic model.

### Trismegistos

- **Why wanted:** identifiers, metadata, people/places/texts and cross-database linkage are foundational for papyrology and epigraphy.
- **Constraint:** investigate API/licensing/access terms before proposing implementation.

### Pleiades

- **Why wanted:** standard ancient-world gazetteer useful across epigraphy, papyrology, prosopography and archaeology.
- **Opportunity:** provider-level geospatial plugin rather than language-specific integration.

### EDH / EDCS / EAGLE

- **Why wanted:** major epigraphic databases.
- **Partial coverage:** pyaegean can fetch the EDH Greek subset, but Agora lacks a general epigraphic MCP.

## Islamic and Islamicate studies

### OpenITI

- **Upstream:** [`OpenITI`](https://github.com/OpenITI)
- **Why wanted:** one of the most important open scholarly corpora of premodern Islamicate texts; excellent fit for corpus search, metadata, citation and NLP workflows.
- **Priority:** very high.

### Corpus Coranicum / Qurʾān manuscript infrastructure

- **Why wanted:** critical-historical Qurʾānic scholarship and manuscript evidence are not equivalent to devotional/canonical Qurʾān APIs.
- **Backlog action:** investigate machine-readable access and licensing before proposing an MCP.

## Lexica and dictionaries

### Comprehensive Aramaic Lexicon (CAL)

- **Why wanted:** central lexicographic and parsed-text resource for Aramaic across periods/dialects.
- **Potential capabilities:** headword lookup, dialect filtering, parsed citation retrieval, attestation navigation, morphology.
- **Priority:** very high for Agora because it bridges Biblical, Jewish, Syriac and other Aramaic traditions.

### Full Syriac lexica

- **Targets:** Comprehensive Syriac Lexicon / Payne Smith-related resources where licensing/access permits.
- **Existing coverage:** SEDRA should remain the initial Syriac lexicon plugin, but Agora should not assume it exhausts Syriac lexicography.

### Latin scholarly lexica

- **Wanted:** proper Lewis & Short and other legally distributable scholarly resources rather than Wiktionary-only Latin lookup.
- **Potential provider:** Logeion ecosystem if a stable/legal machine interface can be established.

### Sanskrit lexica

High-value targets include:

- Monier-Williams;
- Cologne Digital Sanskrit Dictionaries;
- Apte;
- Sanskrit Heritage lexical resources.

No convincing research-grade dedicated MCP emerged from the survey.

### Akkadian lexica

- **Wanted:** reliable Akkadian dictionary access.
- **Constraint:** CAD and AHw have significant rights/licensing limitations; ORACC glossaries and other open resources may be a more realistic first integration.

### Coptic lexica

- **Targets:** Crum, Coptic Dictionary Online, TLA lexical layers where permitted.

### Egyptian lexica

- **Targets:** TLA/Wörterbuch-related lexical access where an API/data license permits it.

### Avestan and Middle Persian lexica

- **Why wanted:** major gap in Iranian religious/textual studies.

### Classical Armenian and Georgian lexica

- **Why wanted:** major patristic/translation traditions with little agent-facing language infrastructure found in the survey.

### Old Norse scholarly lexica

- **Wanted:** ONP and/or Cleasby–Vigfusson quality access.
- **Existing partial coverage:** Valksor's Old Norse service is useful but mainly Wiktionary-based.

### Old English scholarly lexica

- **Wanted:** general Bosworth–Toller MCP rather than access tied to a single corpus/workflow.

## NLP and language technology

### CLTK MCP

- **Upstream:** [`cltk/cltk`](https://github.com/cltk/cltk)
- **Why wanted:** obvious generic NLP backend for premodern languages.
- **Potential:** language-specific tokenization, lemmatization, morphology, embeddings/NLP pipelines exposed through a stable MCP surface.

### Universal Dependencies / UDPipe

- **Why wanted:** standardized morphology/syntax across many historical and modern languages; could provide corpus-independent parsing and treebank inspection.

### Stanza MCP

- **Why wanted:** robust multilingual tokenization, POS, morphology, lemmas and dependency parsing; useful when language-specific scholarly pipelines are unavailable.
- **Agora rule:** generic model output should be clearly distinguished from gold/curated annotations.

### CAMeL Tools MCP

- **Why wanted:** high-quality Arabic NLP backend for morphology, tokenization, NER and dialect/MSA processing.

### Hebrew NLP

Potential targets:

- HebPipe;
- Dicta tools/resources;
- other morphology/NER/parsing backends with clear licenses and reproducible models.

## Religious traditions with weak MCP coverage

### Hindu / Sanskrit textual traditions

Wanted integrations for Vedas, Upaniṣads, Mahābhārata, Rāmāyaṇa, Purāṇas and related critical/open corpora. Generic "sacred scripture" wrappers should not substitute for scholarly editions and language-aware resources.

### Jain studies

Wanted integrations for Jain Āgamas, Prakrit corpora and lexica.

### Zoroastrian studies

Wanted integrations for Avesta, Middle Persian/Pahlavi corpora and lexica.

---

# Suggested taxonomy extensions

The research suggests that Agora's category vocabulary should explicitly include at least the following cross-cutting classes in addition to disciplinary labels:

- `corpus`
- `lexicon-dictionary`
- `nlp-language-technology`
- `corpus-linguistics`
- `digital-edition-tei`
- `textual-criticism`
- `papyrology-epigraphy`
- `manuscript-images-iiif`
- `htr-ocr`
- `prosopography-linked-data`
- `bibliography-literature-discovery`
- `archive-library-search`
- `museum-material-culture`
- `research-workflow-skill`

These should be capabilities/categories, not mutually exclusive plugin types. One plugin can legitimately expose several resource kinds.

## Lexicon-specific metadata

Lexica need richer metadata than generic corpora. Candidate fields:

- language;
- language stage/dialect;
- headword count;
- source edition;
- lexicographic authority/status;
- nested sense structure;
- morphology/paradigms;
- lookup from inflected forms;
- etymology;
- attestation links;
- citation granularity;
- script/transliteration support;
- dictionary data license;
- generated vs editorially curated fields.

## NLP-specific metadata

NLP resources should record:

- supported languages/language stages;
- tasks: tokenization, sentence segmentation, POS, morphology, lemmatization, dependency parsing, NER, coreference, alignment, embeddings, generation;
- deterministic/rule-based vs statistical/neural vs LLM-generated;
- model/version identifier;
- training/evaluation corpus;
- benchmark metrics where available;
- gold vs predicted annotations;
- local vs remote inference;
- hardware/runtime requirements;
- output standard: UD/CoNLL-U, TEI/EpiDoc, Text-Fabric, custom JSON, etc.

## Religious-studies provenance metadata

For religion-related resources, Agora should avoid collapsing different epistemic roles into one `verified` badge. Useful metadata includes:

- critical scholarly edition;
- institutional scholarly curation;
- traditional/confessional edition;
- devotional resource;
- translation;
- commentary/exegesis;
- generated analytical layer;
- manuscript witness/data;
- explicit denominational/institutional provenance where material to interpretation.

This is descriptive provenance, not a quality ranking.

---

# Recommended first expansion sequence

Subject to verification results, a practical first post-v0.1 sequence is:

1. TEI MCP
2. Zotero MCP
3. Wikidata MCP
4. IIIF MCP
5. Transkribus MCP
6. Quran Foundation MCP
7. Tafsir Center MCP
8. Shamela MCP
9. FoJin MCP
10. pyaegean / aegean-mcp
11. UralicMCP
12. Gallica MCP
13. Internet Archive MCP
14. Historical Newspapers MCP
15. eme-gir
16. Tripitaka MCP
17. Kitconc
18. SHEBANQ MCP
19. DPRR MCP
20. Logeion MCP
21. acsearch MCP
22. bible-mcp
23. Chinese History MCP
24. unfoldingWord Translation Helps MCP

In parallel, start feasibility research for the highest-value missing integrations:

1. OpenITI
2. Comprehensive Aramaic Lexicon
3. papyri.info / DDbDP-HGV-DCLP-APIS
4. Pleiades
5. major epigraphic databases
6. CLTK
7. Sanskrit lexica
8. Latin scholarly lexica
9. CAMeL Tools / Hebrew NLP backends
10. Coptic, Egyptian, Iranian, Armenian and Georgian lexicographic resources

---

# Verification workflow for backlog promotion

A candidate should not move from backlog to a release plan based on README claims alone.

Minimum promotion workflow:

1. identify the canonical upstream repository/provider;
2. inspect license files and data-source provenance;
3. enumerate MCP tools/resources/prompts/skills;
4. install or connect using the documented supported path;
5. run initialization and tool-list smoke tests;
6. run representative scholarly queries against known expected answers;
7. test error behavior and citation/provenance output;
8. verify whether data are local, remotely fetched, generated, cached, or bundled;
9. document authentication, paid-service, redistribution and rate-limit constraints;
10. assign separate plugin/runtime and resource/data statuses;
11. only then add canonical registry entries.

For projects with very large tool surfaces, use a stratified test set rather than assuming one successful call validates the whole server.

---

# Notes on overlap and canonical defaults

Agora should avoid becoming an uncurated MCP directory.

Where several projects wrap the same upstream, choose a canonical/default integration when possible and record alternatives only when they offer materially different behavior.

Known overlap groups include:

- Zotero MCPs;
- Wikidata wrappers;
- OpenAlex MCPs;
- Gallica MCPs;
- Logeion wrappers;
- Qurʾān search wrappers;
- generic scripture wrappers;
- Zotero/academic workflow skills.

Criteria for selecting a default should include:

- institutional/upstream maintenance;
- scholarly provenance;
- breadth and correctness of tool surface;
- reproducible tests;
- clear software and data licenses;
- active maintenance;
- stable installation/hosting;
- transparent handling of generated data;
- meaningful advantages over competing wrappers.

The marketplace should remain curated: breadth is useful only if users can tell which integration is canonical, experimental, redundant, or domain-specific.
