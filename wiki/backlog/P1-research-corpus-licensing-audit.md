# P1 — Corpus licensing and redistribution audit

Tracks [#17](https://github.com/alexsosn/Agora/issues/17).

Status: **research in progress**. This document records evidence before any registry licensing value is changed.

## Scope snapshot

Audit baseline: Agora `main` at `c7bd2b7d0f08ba4ace4a15218bff76d24726f701`, checked 2026-09-06.

The current `registry/resources.yaml` contains **37** `corpus`/`collection` resources for which licensing is unknown, partially unknown, upstream-dependent, or otherwise insufficiently evidenced. The old fixed count in #17 is therefore obsolete; this inventory is generated from the current canonical registry.

### Status vocabulary

- `resolved` — primary upstream evidence states terms that can be represented in Agora.
- `component-specific` — the distributed corpus combines components under materially different terms; a single scalar without notes would be misleading.
- `member-specific` — a collection explicitly carries licensing at member/file level.
- `unresolved` — authoritative evidence checked so far does not establish the data/redistribution terms.
- `pending` — not yet researched in this audit.

A repository-level software license is not treated as a corpus-data license unless upstream documentation explicitly applies it to the dataset.

## Inventory

| Resource | Upstream | Research status | Current conclusion |
|---|---|---|---|
| `bhsa` | ETCBC/bhsa | resolved | CC BY-NC 4.0 data; redistribution allowed under licence, attribution required; commercial use requires separate consent |
| `dss` | ETCBC/dss | resolved | CC BY-NC 4.0 dataset |
| `sp` | DT-UCPH/sp | resolved | CC BY-NC 4.0 dataset; citation requested |
| `extrabiblical` | ETCBC/extrabiblical | resolved | CC BY-NC 4.0 dataset |
| `targum` | ETCBC/targum | unresolved | README shows an MIT badge but no corpus-data licence statement was found; do not infer data=MIT |
| `lxx` | CenterBLC/LXX | component-specific | repository software is MIT; corpus derives Rahlfs/CATSS material and BibleOL features whose terms must be checked separately |
| `n1904` | CenterBLC/N1904 | component-specific | dataset docs point to MIT, but source layers come from MACULA/Clear-Bible and other projects; source terms still need reconciliation |
| `SBLGNT` | CenterBLC/SBLGNT | component-specific | derives MorphGNT SBLGNT plus BibleOL features; source licences still need reconciliation |
| `nestle1904` | ETCBC/nestle1904 | unresolved | historical/moved dataset based on Clear-Bible/MACULA LowFat; current authoritative terms need following upstream |
| `Nestle1904GBI` | tonyjurg/Nestle1904GBI | pending | — |
| `tischendorf_tf` | codykingham/tischendorf_tf | pending | — |
| `bible` | pthu/bible | unresolved | root Unlicense explicitly describes software; no evidence yet that it licenses the collection data |
| `patristics` | pthu/patristics | pending | — |
| `greek_literature` | pthu/greek_literature | member-specific | repository LICENSE says licence notes, when available, are copied from TEI metadata into each `.tf` file's `@availability` metadata |
| `athenaeus` | pthu/athenaeus | unresolved | root Unlicense explicitly describes software; corpus-data source/terms still need checking |
| `peshitta` | ETCBC/peshitta | resolved | plain text + TF conversion CC BY-NC 4.0; MIT applies to converter; Brill critical apparatus is copyrighted and excluded |
| `syrnt` | ETCBC/syrnt | unresolved | source is a SEDRA export; repository LICENSE is MIT software text; corpus docs checked so far contain no data licence |
| `syriac` | ETCBC/syriac | resolved | CC BY-NC 4.0 dataset; source editions acknowledged separately |
| `quran` | q-ran/quran | component-specific | resulting TF corpus declared CC BY 4.0, but source components include GPL/no-change and Tanzil CC BY-ND/no-change terms; redistribution must preserve source restrictions |
| `fusus` | among/fusus | pending | — |
| `nena_tf` | CambridgeSemiticsLab/nena_tf | pending | — |
| `uruk` | Nino-cunei/uruk | component-specific | TF material derives from CDLI; current CDLI terms permit textual reuse with academic attribution, while images have separate non-commercial/owner restrictions; Agora's loaded TF path must be distinguished from images |
| `oldassyrian` | Nino-cunei/oldassyrian | component-specific | transliterations derive from CDLI; apply CDLI textual-data terms, not repository software licence |
| `oldbabylonian` | Nino-cunei/oldbabylonian | component-specific | transliterations derive from CDLI; apply CDLI textual-data terms, not repository software licence |
| `ninmed` | Nino-cunei/ninmed | unresolved | corpus provenance still needs tracing to its textual source/terms; README alone does not state a data licence |
| `cuc` | DT-UCPH/cuc | resolved | CC BY-NC 4.0 dataset |
| `dhammapada` | ETCBC/dhammapada | pending | — |
| `translatin-manif` | HuygensING/translatin-manif | pending | — |
| `wp6-missieven` | CLARIAH/wp6-missieven | pending | — |
| `wp6-daghregisters` | CLARIAH/wp6-daghregisters | pending | — |
| `wp6-ferdinandhuyck` | CLARIAH/wp6-ferdinandhuyck | pending | — |
| `mondriaan` | annotation/mondriaan | pending | — |
| `descartes-tf` | CLARIAH/descartes-tf | pending | — |
| `suriano` | HuygensING/suriano | pending | — |
| `mobydick` | annotation/mobydick | pending | — |
| `banks` | annotation/banks | pending | — |
| `TLHdig-TF` | alexsosn/TLHdig-TF | resolved | upstream source and generated TF datasets CC BY 4.0; converter/code/docs MIT |

## Evidence gathered

### `bhsa` — resolved

Primary evidence:

- https://github.com/ETCBC/bhsa/blob/master/README.md
- https://github.com/ETCBC/bhsa/blob/master/LICENSE

The repository `LICENSE` is MIT and expressly speaks about "Software". The README separately states that the BHSA work/data are licensed under **CC BY-NC 4.0**, permits processing/copying/modification/research publication, requires attribution via DOI `10.17026/dans-z6y-skyh`, and requires consent for commercial applications. This is a direct example of why GitHub's repository licence cannot be copied into `licenses.data`.

Recommended registry direction:

- `licenses.data: CC-BY-NC-4.0`
- redistribution: permitted under CC BY-NC 4.0
- notes: preserve attribution DOI and commercial-use condition

### `dss` — resolved

Primary evidence:

- https://github.com/ETCBC/dss/blob/master/README.md

The README explicitly states: "This dataset is licensed under a Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0)." It also identifies the CACCHT project and credits Martin Abegg for source data.

Recommended registry direction: `CC-BY-NC-4.0`, with redistribution subject to licence attribution/non-commercial terms.

### `sp` — resolved

Primary evidence:

- https://github.com/DT-UCPH/sp/blob/main/README.md

The README carries a **CC BY-NC 4.0** badge, says the dataset may be used freely for research and education, and requests citation of the dataset DOI `10.5281/zenodo.7734632` and the associated publications. It also records that the text was provided by the Samaritanus project and identifies the manuscript/editorial basis.

Recommended registry direction: `CC-BY-NC-4.0`; preserve dataset citation/attribution in notes.

### `extrabiblical` — resolved

Primary evidence:

- https://github.com/ETCBC/extrabiblical/blob/master/README.md

The README explicitly states that the **dataset** is licensed under **CC BY-NC 4.0**.

### `peshitta` — resolved

Primary evidence:

- https://github.com/ETCBC/peshitta/blob/master/docs/about.md
- https://github.com/ETCBC/peshitta/blob/master/README.md

The corpus documentation distinguishes layers:

- plain Peshitta text and its TF conversion: **CC BY-NC 4.0**;
- conversion program: **MIT**;
- Brill/VTS critical apparatus: copyrighted by Brill and **not included** in the repository.

The docs request citation of the archived repository and direct commercial users to ETCBC/Brill.

Recommended registry direction: `CC-BY-NC-4.0`; notes should preserve the exclusion of the critical apparatus and the commercial-use contact statement.

### `syrnt` — unresolved

Primary evidence checked:

- https://github.com/ETCBC/syrnt/blob/master/README.md
- https://github.com/ETCBC/syrnt/blob/master/docs/about.md
- https://github.com/ETCBC/syrnt/blob/master/LICENSE

The docs establish that the corpus source is a **SEDRA database export** made by George A. Kiraz and James W. Bennett, based on ABMC manuscripts. The repository `LICENSE` is MIT and expressly covers "Software". Unlike the Peshitta `about.md`, the SyrNT `about.md` section checked here contains no data licensing statement. Until SEDRA/ABMC terms or another authoritative corpus-specific statement are established, `data` and redistribution should remain unresolved rather than being set to MIT.

Follow-up: check SEDRA's current licence/terms and archived documentation applicable to the exported database version used here.

### `syriac` — resolved

Primary evidence:

- https://github.com/ETCBC/syriac/blob/master/README.md

The README explicitly licenses the work under **CC BY-NC 4.0** and states that users may download, process, copy, modify, and use it for research. It separately lists the editions on which component texts are based and thanks editors for permission. Those source acknowledgements should remain in notes/provenance rather than being erased by the top-level CC identifier.

### `cuc` — resolved

Primary evidence:

- https://github.com/DT-UCPH/cuc/blob/main/README.md

The Copenhagen Ugaritic Corpus README carries an explicit **CC BY-NC 4.0** dataset licence badge and a Zenodo DOI (`10.5281/zenodo.10695308`).

Recommended registry direction: `CC-BY-NC-4.0`, with DOI/citation retained in notes.

### `quran` — component-specific

Primary evidence:

- https://github.com/q-ran/quran/blob/master/README.md
- https://github.com/q-ran/quran/blob/master/docs/about.md

The README declares the TF-format corpus **CC BY 4.0**. The detailed provenance file then records materially different source terms:

- Quranic Arabic Corpus morphology: GPL-labelled source plus explicit verbatim/no-change and attribution/link requirements;
- Tanzil Uthmani text and translations: CC BY-ND / no-change terms in the source notices;
- the generated corpus: CC BY 4.0, with the explicit warning that modified TF redistribution is permitted only while respecting source licences.

Recommended registry direction: top-level `CC-BY-4.0` only with `licenses.notes` recording the component/source restrictions. A bare `CC-BY-4.0` value without those notes would overstate modification rights over every embedded component.

### `lxx` — component-specific, not yet resolved

Primary evidence checked:

- https://github.com/CenterBLC/LXX/blob/main/README.md
- https://github.com/CenterBLC/LXX/blob/main/LICENSE

The repository `LICENSE` is MIT software text. The README states that the TF data derive from Rahlfs 1935 via Eliran Wong/CATSS and that dictionary entry forms and English features come from BibleOL, explicitly directing readers to BibleOL for licences. The data licence therefore cannot be inferred from the MIT repository licence.

Follow-up: establish the exact CATSS/Rahlfs-derived source terms used by Eliran Wong and the BibleOL terms that apply to the copied features.

### `SBLGNT` — component-specific, not yet resolved

Primary evidence:

- https://github.com/CenterBLC/SBLGNT/blob/main/README.md

The TF corpus is derived from `morphgnt/sblgnt` and enriched with BibleOL dictionary/gloss features. The README itself directs users to BibleOL for those feature licences. Follow both upstream chains before choosing a scalar licence.

### `n1904` / `nestle1904` — component-specific, research continuing

Primary evidence:

- https://github.com/CenterBLC/N1904/blob/main/docs/about.md
- https://github.com/CenterBLC/N1904/blob/main/LICENSE.md
- https://github.com/ETCBC/nestle1904/blob/master/README.md

CenterBLC's current `N1904` documentation labels the **Text-Fabric dataset** with a licence link to its MIT `LICENSE.md`, but also states that the TF files were produced from MACULA Greek LowFat data and enumerate source layers including Nestle1904 transcription/morphology, Clear Bible syntax, Berean Study Bible glosses, UBS MARBLE word-sense data, semantic roles, and participant referents. The historical ETCBC repository points users to CenterBLC/N1904 and to Clear-Bible/MACULA as the source.

Follow-up: check the MACULA Greek source licence and the terms on the listed third-party layers before treating the whole TF dataset as unqualified MIT.

### `greek_literature` — member-specific

Primary evidence:

- https://github.com/pthu/greek_literature/blob/master/LICENSE
- https://github.com/pthu/greek_literature/blob/master/README.md

The repository's `LICENSE` does not assign one collection-wide licence. It says that, when available, original TEI licence notes are copied into the metadata `@availability` attribute of each `.tf` file, and asks for modules that violate original rules to be reported/removed. The collection is built from Perseus and OpenGreekAndLatin TEI corpora.

Recommended registry direction: represent the data/redistribution state as **member-specific** (or extend the schema to model collection-member licences) rather than `unknown` or a guessed collection-wide Creative Commons licence.

### `bible` / `athenaeus` — unresolved software/data conflation

Primary evidence:

- https://github.com/pthu/bible/blob/master/LICENSE
- https://github.com/pthu/bible/blob/master/README.md
- https://github.com/pthu/athenaeus/blob/master/LICENSE
- https://github.com/pthu/athenaeus/blob/master/README.md

Both repositories carry the Unlicense text, but it explicitly describes **software/source code**. Their READMEs do not establish that the underlying Greek editions/textual datasets are placed in the public domain. Do not set `licenses.data: Unlicense` on this evidence alone.

### Nino-cunei / CDLI family

Primary evidence:

- https://github.com/Nino-cunei/uruk/blob/master/README.md
- https://github.com/Nino-cunei/oldassyrian/blob/master/README.md
- https://github.com/Nino-cunei/oldbabylonian/blob/master/README.md
- https://cdli.earth/terms-of-use

`uruk`, `oldassyrian`, and `oldbabylonian` identify CDLI as the source of the transliterations. Current CDLI terms distinguish content types:

- transliterations/translations may be freely copied, aggregated, and reused under normal academic practice, with CDLI attribution requested for substantial reuse;
- photographs and line art carry separate ownership/non-commercial restrictions.

Agora loads the TF corpus path, not the repository's image assets, so the registry should describe the terms governing the **material actually acquired/loaded** while preserving the source distinction. A generic repository MIT licence would be wrong for the corpus data.

`ninmed` still needs its direct textual provenance established before it can inherit any CDLI conclusion.

### `TLHdig-TF` — resolved

Primary evidence:

- https://github.com/alexsosn/TLHdig-TF/blob/main/README.md#licensing

The repository explicitly distinguishes:

- `corpus/**`: **CC BY 4.0** upstream TLHdig source data;
- `tf/**` and `tf-provenance/**`: **CC BY 4.0** generated adaptations;
- converter code/repository documentation: **MIT**.

It also states that each `.tf` file carries source attribution/licence metadata and provides the upstream TLHdig citation (`10.5281/zenodo.20328284`).

Recommended registry direction: `licenses.data: CC-BY-4.0`; redistribution permitted under CC BY 4.0; notes/citation point to the upstream TLHdig release.

## Pending families

The following remain to be researched before the implementation gate:

1. `targum` — reconcile the README's MIT badge with the actual Targum text/edition sources and any dataset-specific terms.
2. Greek/New Testament family — finish MorphGNT, SBLGNT, MACULA/Clear-Bible, BibleOL, Nestle1904GBI, and Tischendorf source-term tracing.
3. PTHU collections — inspect `patristics` member metadata and establish whether `bible`/`athenaeus` carry data-level rights beyond software Unlicense.
4. Arabic/Aramaic — `fusus`, `nena_tf`.
5. Cuneiform — establish `ninmed` provenance/terms and verify whether any TF modules include restricted CDLI image-derived material (expected not, but must be checked).
6. `dhammapada`.
7. Huygens/CLARIAH/annotation modern-text family: `translatin-manif`, `wp6-missieven`, `wp6-daghregisters`, `wp6-ferdinandhuyck`, `mondriaan`, `descartes-tf`, `suriano`, `mobydick`, `banks`.

## Implementation constraints discovered so far

The current schema permits only scalar `licenses.data`, `licenses.redistribution`, plus free-form `licenses.notes`. The audit already contains two cases where that is barely sufficient:

- heterogeneous collections (`greek_literature`);
- composite corpora with source-specific restrictions (`quran`, LXX/SBLGNT family).

Before registry edits, decide whether `member-specific` / `component-specific` scalar values plus notes are acceptable canonical vocabulary, or whether the licence model needs a small structured extension. Do not force these cases into a misleading single SPDX-style identifier merely to avoid a schema change.

## Research gate progress

- [x] Enumerate all current corpus/collection resources from the canonical registry.
- [x] Establish the software-vs-data distinction with concrete upstream examples.
- [x] Identify at least one heterogeneous collection (`greek_literature`).
- [x] Identify derived/composite corpora where a single top-level licence is misleading (`quran`, LXX/SBLGNT/N1904 family).
- [ ] Complete primary-source evidence for all 37 resources.
- [ ] Independently review the required cross-section before implementation.
- [ ] Only then edit `registry/resources.yaml` and validation/schema behavior.
