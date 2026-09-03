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

Use `load_corpus` with Agora's `cuc` resource.

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

## Reproducibility

For a substantive result, record:

- Agora resource ID `cuc`;
- selected TF version;
- resolved source revision and matching upstream documentation;
- node type(s) counted;
- whether `g_cons`, `sign`, or another representation supplied the match;
- treatment of `emen`, `cert`, `alt`, and damaged/uncertain material;
- tablet/line references for spot-checked examples.

## License

The upstream CUC repository currently identifies the dataset as CC BY-NC 4.0. Treat that data license separately from Agora's MIT plugin/skill code.
