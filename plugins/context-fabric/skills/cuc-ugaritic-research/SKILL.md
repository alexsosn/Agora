---
name: cuc-ugaritic-research
description: "Use this skill for Ugaritic research with the Copenhagen Ugaritic Corpus through Agora Context-Fabric: load CUC, record its resolved source revision, distinguish transliteration and sign/editorial features, and consult the matching upstream documentation."
license: MIT
compatibility: "Requires the Agora Context-Fabric MCP plugin and access to the registered DT-UCPH/cuc source when the corpus is not already cached."
metadata:
  provider: context-fabric
  resource: cuc
  version: "0.1.0"
---

# CUC / Ugaritic research workflow

The Copenhagen Ugaritic Corpus (CUC) is a Text-Fabric corpus developed by the CACCHT project. Agora owns discovery, acquisition, and loading; the [upstream CUC repository](https://github.com/DT-UCPH/cuc) owns corpus semantics, coverage, data-quality statements, and suitability guidance.

## Load the registered corpus

Use Agora's `cuc` resource. For a first load, run `prepare_corpus` and then `load_corpus`, as described in the `context-fabric-research` skill. If a call is interrupted, inspect `corpus_cache_status` before retrying.

Record the returned `source_revision`, then consult the upstream documentation at that revision. After loading, inspect node types and feature metadata before building linguistic queries. Do not import BHSA feature expectations merely because both corpora are Text-Fabric datasets developed in an ancient-Semitic research context.

## Text and sign representation

Important documented CUC features include:

- `g_cons` — consonantal representation of a word in Latin script;
- `sign` — a letter/sign represented in Latin script;
- `trailer` — spacing or word-divider representation;
- `tablet`, `column`, `line`, `side` — document/inscription structure;
- `language` — language marking.

Choose the representation that matches the question. A search over `g_cons` is a search over the corpus's consonantal word representation, not automatically a search over every editorial or sign-level variant.

For epigraphic questions, inspect sign-level information instead of relying only on normalized word strings.

## Editorial and uncertainty features

CUC documents several sign-level editorial features:

- `emen` — emendations/reconstructions and related editorial states, including reconstructed, missing, excised, or redundant signs/letters;
- `cert` — certainty marking corresponding to KTU italics;
- `alt` — alternative reading;
- `cont` — line-continuation marking.

These features carry evidence about the reading itself. Do not strip them away before deciding whether an attestation is suitable for a linguistic count.

A form that is reconstructed, uncertain, or supplied as an alternative reading should not silently contribute to the same evidential category as an unproblematic reading unless the research design explicitly says so.

## Recommended query discipline

For lexical or morphological frequency work:

1. define whether the counted unit is a word, sign, line, or tablet occurrence;
2. state whether uncertain/reconstructed readings are included;
3. decide how `alt` readings are handled;
4. inspect the relevant editorial features on representative hits;
5. record the CUC version/selected TF dataset.

For orthographic work, distinguish word-level `g_cons` from individual `sign` sequences and from editorial metadata.

For line-based questions, use the explicit tablet/column/line structure rather than reconstructing line boundaries from punctuation or spacing strings.

## Transliteration cautions

Do not normalize Ugaritic transliteration ad hoc inside a query without recording the transformation. Distinctions in scholarly transliteration can affect matching.

If comparing CUC with another Ugaritic database, establish a mapping between their transliteration/tokenization conventions first. Identical-looking strings do not guarantee identical segmentation or editorial policy.

## Optional Burns cultic-vocabulary module (`cuc-burns`)

Agora registers `cuc-burns`, a feature-only module that attaches Duncan Burns's *Contents, Texts and Contexts* (2003) Workbook annotations to existing CUC nodes: `burns_headwords`, `burns_sections`, `burns_semantic_statuses`, `burns_worksheet_roles`, `burns_annotation_ids`, and the lossless `burns_annotations` payload. The [upstream CTC-TF repository](https://github.com/alexsosn/CTC-TF) owns the alignment method, the label semantics, and the module report.

Agora does not fetch this module. Its source is CC BY-NC-ND, so the user materializes it locally with the upstream `ugarit-context-parsing module` CLI against CUC `tf/0.2.8` and places the output under `<AGORA_CORPUS_CACHE>/local-modules/cuc-burns/tf/0.2.8`; `describe_available_corpus("cuc-burns")` shows the acquisition strategy and the required parent commit. Select it with `load_corpus("cuc", modules=["cuc-burns"])`. Agora refuses to compose it onto any other CUC revision than the one the module declares as its `parent-base`; once CUC HEAD has moved past that commit, pass it explicitly as `source_revision` (the module description lists it) so the reviewed parent is loaded from the cache instead of upstream HEAD.

When using it:

- treat the module's status labels (for example `homograph_excluded`, `probable_cultic`) and archive roles (`prime_gp`, `prime_ph`, `derived_*`) as Burns's classifications as documented upstream, not as CUC editorial features;
- an annotation on a `line` rather than a `word` means the upstream aligner anchored it structurally, not lexically; read `burns_annotations` before counting it as a word attestation;
- occurrences in tablets absent from CUC stay in the upstream module report and never appear in the corpus, so Burns totals are not recoverable from CUC queries alone;
- record the module's `source_revision` fingerprint from the load result together with the CUC revision.

## Reproducibility

For a substantive result, record:

- Agora resource ID `cuc`;
- selected TF version;
- resolved source revision and matching upstream documentation;
- selected feature modules (for example `cuc-burns`) and their fingerprints;
- node type(s) counted;
- whether `g_cons`, `sign`, or another representation supplied the match;
- treatment of `emen`, `cert`, `alt`, and damaged/uncertain material;
- tablet/line references for spot-checked examples.

## License

The upstream CUC repository currently identifies the dataset as CC BY-NC 4.0. Treat that data license separately from Agora's MIT plugin/skill code.
