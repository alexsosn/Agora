# P1 — Corpus licensing and redistribution audit

Tracks [#17](https://github.com/alexsosn/Agora/issues/17).

Status: **research complete**. This document records the evidence gate before registry licensing values are changed.

## Scope snapshot

Audit baseline: Agora `main` at `c7bd2b7d0f08ba4ace4a15218bff76d24726f701`, checked 2026-09-06. A later comparison through current `main` (`302178da1f85c6097950d1bb4c0986bd10c3c141`) found no intervening changes to `registry/resources.yaml`, so the inventory remains current.

The canonical registry contains **37** `corpus`/`collection` resources whose licensing was unknown, partially unknown, upstream-dependent, or insufficiently evidenced.

### Status vocabulary

- `resolved` — primary upstream evidence states terms that Agora can represent directly.
- `component-specific` — materially different embedded components have different terms.
- `member-specific` — collection licensing is carried at member/file level.
- `unresolved` — authoritative sources were checked but do not establish a defensible data/redistribution licence.

A repository-level software licence is not treated as a corpus-data licence unless upstream documentation explicitly applies it to the dataset.

## Complete evidence matrix

| Resource | Upstream | Status | Registry conclusion |
|---|---|---|---|
| `bhsa` | ETCBC/bhsa | resolved | data `CC-BY-NC-4.0`; non-commercial redistribution with attribution/DOI |
| `dss` | ETCBC/dss | resolved | data `CC-BY-NC-4.0` |
| `sp` | DT-UCPH/sp | resolved | data `CC-BY-NC-4.0`; preserve dataset/publication citation |
| `extrabiblical` | ETCBC/extrabiblical | resolved | data `CC-BY-NC-4.0` |
| `targum` | ETCBC/targum | resolved | repository ships full `CC-BY-NC-4.0` licence text |
| `lxx` | CenterBLC/LXX | component-specific | MIT is software-only; Rahlfs/CATSS-derived text and BibleOL-derived features require component notes; no single data licence established |
| `n1904` | CenterBLC/N1904 | component-specific | repository labels TF dataset MIT but source layers include MACULA/Clear-Bible, Berean glosses and UBS MARBLE; preserve component provenance/terms |
| `SBLGNT` | CenterBLC/SBLGNT | component-specific | SBLGNT text subject to SBLGNT EULA; MorphGNT morphology/lemmatization `CC-BY-SA-3.0`; BibleOL-derived features separately sourced |
| `nestle1904` | ETCBC/nestle1904 | component-specific | historical repo is superseded by CenterBLC/N1904 and derives from MACULA LowFat; treat with the same component caveat, not repository MIT |
| `Nestle1904GBI` | tonyjurg/Nestle1904GBI | resolved | repository explicitly licenses **software and data** `CC-BY-4.0`; MACULA source data also `CC-BY-4.0` with attribution |
| `tischendorf_tf` | codykingham/tischendorf_tf | resolved | root licence states text and analysis are public domain and may be copied freely |
| `bible` | pthu/bible | unresolved | root Unlicense expressly covers software/source code; heterogeneous biblical editions have no collection-data licence statement |
| `patristics` | pthu/patristics | unresolved | heterogeneous collection has no root data licence/rights statement found; do not infer terms from public availability |
| `greek_literature` | pthu/greek_literature | member-specific | repository says TEI licence notes are propagated to each `.tf` file as `@availability`; collection-wide scalar would be misleading |
| `athenaeus` | pthu/athenaeus | unresolved | root Unlicense is software text; README identifies conversion but no corpus-data licence |
| `peshitta` | ETCBC/peshitta | resolved | plain text + TF conversion `CC-BY-NC-4.0`; converter MIT; Brill critical apparatus excluded |
| `syrnt` | ETCBC/syrnt | unresolved | SEDRA III export provenance is clear; SEDRA describes III as non-commercial open source but gives no formal licence; current site is all-rights-reserved |
| `syriac` | ETCBC/syriac | resolved | data `CC-BY-NC-4.0`; preserve source-edition acknowledgements |
| `quran` | q-ran/quran | component-specific | resulting TF corpus `CC-BY-4.0`, but QAC/Tanzil components carry stricter no-change/BY-ND/attribution conditions |
| `fusus` | among/fusus | unresolved | repository MIT covers software; corpus is OCR/alignment of modern printed editions and no data licence was found |
| `nena_tf` | CambridgeSemiticsLab/nena_tf | resolved | TF repo software MIT; underlying `nena_corpus` is `CC-BY-4.0`, which governs corpus data |
| `uruk` | Nino-cunei/uruk | resolved | Agora loads the `tf/<version>` dataset only; latest TF tree contains textual/metadata `.tf` files and no image assets; CDLI permits transliteration/translation reuse under normal academic practice with attribution requested for substantial reuse |
| `oldassyrian` | Nino-cunei/oldassyrian | resolved | transliterations derive from CDLI; current CDLI terms permit textual reuse with normal academic attribution |
| `oldbabylonian` | Nino-cunei/oldbabylonian | resolved | transliterations derive from CDLI; current CDLI terms permit textual reuse with normal academic attribution |
| `ninmed` | Nino-cunei/ninmed | unresolved | JSON source was supplied by personal communication and contains NinMed/BabMed/eBL material; no data redistribution licence is stated |
| `cuc` | DT-UCPH/cuc | resolved | data `CC-BY-NC-4.0` with dataset DOI |
| `dhammapada` | ETCBC/dhammapada | unresolved | source is Fausböll 1900 edition/transcription; repository MIT is software-only and no TF-data licence statement was found |
| `translatin-manif` | HuygensING/translatin-manif | unresolved | repository distributes processed manifestations and says publication has no legal obstacle, but states no explicit data licence |
| `wp6-missieven` | CLARIAH/wp6-missieven | unresolved | repository MIT covers software; TF/XML data derive from supplied TEI/PDF sources with no corpus-data licence stated |
| `wp6-daghregisters` | CLARIAH/wp6-daghregisters | unresolved | repository MIT covers software; TF derives from archive.org/Google digitization/OCR with no data licence stated |
| `wp6-ferdinandhuyck` | CLARIAH/wp6-ferdinandhuyck | unresolved | TF derives from DBNL TEI; repository MIT does not establish DBNL/corpus data terms |
| `mondriaan` | annotation/mondriaan | unresolved | Huygens TEI and RKD thumbnails have explicit provenance but no corpus-data licence in the TF repository |
| `descartes-tf` | CLARIAH/descartes-tf | unresolved | 1998 ASCII → 2011 TEI → 2023 TF provenance is documented; repository software licence does not establish source-data rights |
| `suriano` | HuygensING/suriano | unresolved | transcriptions/thumbnails are publicly distributed with detailed provenance, but no corpus-data licence statement was found |
| `mobydick` | annotation/mobydick | unresolved | TF derives from DBNL TEI; repository licence is software-only and DBNL data terms are not stated in the corpus repo |
| `banks` | annotation/banks | unresolved | 99-word excerpt from a 1987 copyrighted novel; repository MIT is software-only and no content permission/licence is stated |
| `TLHdig-TF` | alexsosn/TLHdig-TF | resolved | upstream source and generated TF/TF-provenance data `CC-BY-4.0`; code/docs MIT |

## Evidence by family

### ETCBC / CACCHT corpora

Primary evidence:

- https://github.com/ETCBC/bhsa/blob/master/README.md
- https://github.com/ETCBC/dss/blob/master/README.md
- https://github.com/DT-UCPH/sp/blob/main/README.md
- https://github.com/ETCBC/extrabiblical/blob/master/README.md
- https://github.com/ETCBC/targum/blob/main/LICENSE.md
- https://github.com/ETCBC/peshitta/blob/master/docs/about.md
- https://github.com/ETCBC/syriac/blob/master/README.md
- https://github.com/DT-UCPH/cuc/blob/main/README.md

These sources explicitly license the named datasets. BHSA is the clearest software/data split: its root `LICENSE` is MIT software while the README assigns the corpus data `CC BY-NC 4.0`. Peshitta likewise separates `CC BY-NC 4.0` textual/TF data from MIT conversion code and excludes Brill's critical apparatus. Targum ships the full `CC BY-NC 4.0` licence despite a misleading historical README badge.

For `syrnt`, the repository documents a SEDRA database export but only ships MIT software text. SEDRA's authoritative history describes SEDRA III as a **non-commercial open-source database** without naming a formal licence, while current SEDRA pages are copyright Beth Mardutho / All Rights Reserved. That is insufficient to invent a licence identifier or exact redistribution rule.

### Greek biblical corpora

Primary evidence:

- https://github.com/CenterBLC/LXX/blob/main/README.md
- https://github.com/CenterBLC/LXX/blob/main/LICENSE
- https://github.com/CenterBLC/SBLGNT/blob/main/README.md
- https://github.com/morphgnt/sblgnt/blob/master/README.md
- https://github.com/CenterBLC/N1904/blob/main/docs/about.md
- https://github.com/CenterBLC/N1904/blob/main/LICENSE.md
- https://github.com/ETCBC/nestle1904/blob/master/README.md
- https://github.com/tonyjurg/Nestle1904GBI/blob/main/LICENSE.md
- https://github.com/tonyjurg/Nestle1904GBI/blob/main/resources/sourcedata/README.md
- https://github.com/codykingham/tischendorf_tf/blob/master/LICENSE
- https://github.com/EzerIT/BibleOL/blob/master/LICENSE

`LXX`, `SBLGNT`, and `N1904` are composites. CenterBLC repository MIT files do not automatically relicense external text/annotation layers. MorphGNT explicitly separates the SBLGNT EULA from `CC BY-SA 3.0` morphology/lemmatization. BibleOL's root licence explicitly covers software, not the extracted lexical data. `Nestle1904GBI` is different: its licence expressly covers “software and data” under `CC BY 4.0`, and its MACULA source notice gives the same CC licence plus attribution. Tischendorf's root licence places text and analysis in the public domain.

### PTHU collections

Primary evidence:

- https://github.com/pthu/greek_literature/blob/master/LICENSE
- https://github.com/pthu/greek_literature/blob/master/README.md
- https://github.com/pthu/bible/blob/master/LICENSE
- https://github.com/pthu/bible/blob/master/README.md
- https://github.com/pthu/athenaeus/blob/master/LICENSE
- https://github.com/pthu/athenaeus/blob/master/README.md
- https://github.com/pthu/patristics

`greek_literature` explicitly delegates rights metadata to individual converted TEI files through `@availability`; it is therefore member-specific. `bible` and `athenaeus` use an Unlicense text that explicitly describes software/source code and do not state a data licence. `patristics` is a large heterogeneous collection for which no root data-rights statement was found. Public-domain authorship is not enough to infer rights in modern transcriptions/editions.

### Arabic corpora

Primary evidence:

- https://github.com/q-ran/quran/blob/master/README.md
- https://github.com/q-ran/quran/blob/master/docs/about.md
- https://github.com/among/fusus/blob/master/README.md
- https://github.com/among/fusus/blob/master/LICENSE

The Quran TF corpus is declared `CC BY 4.0`, while its provenance file preserves source-specific restrictions including no-change/BY-ND requirements. `fusus` is generated from OCR and alignment of printed editions; its MIT licence covers software and no corpus-data licence is stated.

### Neo-Aramaic

Primary evidence:

- https://github.com/CambridgeSemiticsLab/nena_tf/blob/master/README.md
- https://github.com/CambridgeSemiticsLab/nena_tf/blob/master/LICENSE
- https://github.com/CambridgeSemiticsLab/nena_corpus/blob/master/LICENSE

The TF repository points to `nena_corpus` as its underlying corpus. The TF repository's MIT text governs software; `nena_corpus` supplies `CC BY 4.0` for the data.

### Cuneiform corpora

Primary evidence:

- https://github.com/Nino-cunei/uruk/blob/master/README.md
- https://github.com/Nino-cunei/oldassyrian/blob/master/README.md
- https://github.com/Nino-cunei/oldbabylonian/blob/master/README.md
- https://github.com/Nino-cunei/ninmed/blob/master/docs/about.md
- https://cdli.earth/terms-of-use
- https://github.com/alexsosn/TLHdig-TF/blob/main/README.md#licensing

Current CDLI terms permit textual transliterations/translations to be copied, aggregated, and reused under normal academic practice with attribution requested for substantial reuse; images/line art have separate ownership/reuse restrictions. The latest `uruk` TF dataset tree (`tf/1.0`) contains only `.tf` textual/metadata feature files plus a checkout marker, with no image assets, so Agora's materialized Uruk resource falls under the textual-data terms just like Old Assyrian/Old Babylonian. Repository-level image restrictions remain relevant to the upstream repository but not to the `tf/<version>` payload Agora loads. `ninmed` is different: its source JSON came by personal communication and combines NinMed/BabMed/eBL work, so CDLI terms cannot be assumed. TLHdig-TF expressly licenses source and generated TF data `CC BY 4.0` and code/docs MIT.

### Pali and historical/modern European corpora

Primary evidence:

- https://github.com/ETCBC/dhammapada/blob/master/docs/about.md
- https://github.com/HuygensING/translatin-manif/blob/main/README.md
- https://github.com/CLARIAH/wp6-missieven/blob/master/README.md
- https://github.com/CLARIAH/wp6-daghregisters/blob/master/README.md
- https://github.com/CLARIAH/wp6-ferdinandhuyck/blob/main/docs/about.md
- https://github.com/annotation/mondriaan/blob/master/docs/about.md
- https://github.com/CLARIAH/descartes-tf/blob/main/docs/about.md
- https://github.com/HuygensING/suriano/blob/main/README.md
- https://github.com/annotation/mobydick/blob/main/README.md
- https://github.com/annotation/banks/blob/master/README.md

These repositories document provenance well but generally use MIT for conversion/software and omit corpus-data terms. The correct audit result is `unknown` with those sources recorded. This is particularly important for `banks`, whose tiny test corpus quotes a modern copyrighted novel, and for DBNL/Huygens-derived datasets where public GitHub availability is not evidence of a specific redistribution licence.

## Research conclusions

1. **Software licence detection is unsafe for corpus rights.** MIT/Unlicense files repeatedly apply to converters or repository software while data terms differ or remain unstated.
2. **`unknown` is a legitimate researched state.** Sixteen resources still lack a defensible data/redistribution licence after their authoritative repository/provenance documentation was checked.
3. **Collections can require member-level semantics.** `greek_literature` explicitly carries rights metadata in individual TF files.
4. **Some corpora require component-level semantics.** Quran and several Greek biblical corpora combine layers with materially different terms.
5. **Agora needs durable licence evidence.** `source_snapshot` records catalog provenance, not the evidence supporting `licenses`, so it should not be overloaded for this purpose.

## Research gate

- [x] Enumerated all current corpus/collection resources from the canonical registry (37).
- [x] Checked every resource against its upstream repository/provenance documentation.
- [x] Separated software licences from corpus data/content terms.
- [x] Identified member-specific and component-specific cases.
- [x] Preserved genuine ambiguity instead of choosing the most permissive plausible licence.
- [x] Recorded primary evidence sufficient for another reviewer to reproduce each conclusion.
- [x] Independent adversarial cross-section review completed across biblical, classical, Syriac/Aramaic, Arabic, modern-copyright, and cuneiform cases.

## Handoff to design

The implementation must support four evidence outcomes (`resolved`, `component-specific`, `member-specific`, `unresolved`) and must make future unexamined `unknown` values invalid. The design and TDD plan are tracked in [`P1-design-corpus-licensing-metadata.md`](P1-design-corpus-licensing-metadata.md).