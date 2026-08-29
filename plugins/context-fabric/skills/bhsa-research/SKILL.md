---
name: bhsa-research
description: "Use this skill for linguistic and philological research with the BHSA corpus through Agora Context-Fabric: load the registered BHSA resource, interpret ETCBC morphology and syntax features correctly, design reproducible queries, and preserve the corpus's licensing and annotation scope."
license: MIT
compatibility: "Requires the Agora Context-Fabric MCP plugin and access to the registered ETCBC/bhsa source when BHSA is not already cached."
metadata:
  provider: context-fabric
  resource: bhsa
  version: "0.1.0"
---

# BHSA research workflow

BHSA is the Text-Fabric representation of the Hebrew Bible Database with linguistic annotations produced by the Eep Talstra Centre for Bible and Computer (ETCBC). Its feature vocabulary is corpus-specific; it is not a generic Text-Fabric morphology standard.

## Start with the registered resource

Load BHSA with `load_corpus` using Agora's registered `bhsa` resource rather than a manually guessed local path.

Before a substantive query, inspect the loaded corpus and confirm the feature names and node types present in the selected BHSA version.

## Core feature vocabulary

Common word-level BHSA features include:

- `lex` — lexeme;
- `sp` — part of speech;
- `pdp` — phrase-dependent part of speech;
- `ps` — person;
- `gn` — gender;
- `nu` — number;
- `st` — state;
- `vs` — verbal stem;
- `vt` — verbal tense/aspect category.

Higher-level syntax includes features such as `function` and `typ` on appropriate phrase/clause nodes.

Do not infer a feature's node type from its English name. Inspect the corpus metadata or feature documentation before combining word morphology with phrase/clause syntax.

## `sp` and `pdp` are not interchangeable

Use `sp` when the question concerns the lexically/morphologically assigned part of speech.

Use `pdp` only when the phrase-dependent classification is relevant to the syntactic analysis. A difference between `sp` and `pdp` is information, not an inconsistency to normalize away automatically.

When reporting POS counts, state which feature was counted.

## Verbal analysis

For verbal research, distinguish at least:

- lexeme: `lex`;
- verbal stem: `vs`;
- verbal tense/aspect category: `vt`;
- person: `ps`;
- gender: `gn`;
- number: `nu`.

Do not collapse `vs` and `vt`: stem and tense/aspect encode different dimensions of the ETCBC analysis.

If a category label is unfamiliar, resolve it against the BHSA feature documentation rather than expanding an abbreviation from intuition.

## Syntax

BHSA contains phrase- and clause-level annotation in addition to word morphology.

When querying `function` or `typ`:

1. verify which node type carries the feature;
2. establish the documented value inventory;
3. inspect representative matching passages;
4. distinguish an annotated syntactic function from a semantic interpretation supplied by you.

Do not assume that a similarly named feature in another ETCBC-derived corpus has identical coverage or guidelines.

## Counting and comparison

Before publishing a count, define the counted unit explicitly: slots, words, lexemes, phrases, clauses, verses, or occurrences matching a structural pattern.

For morphology distributions:

- inspect missing values;
- distinguish absent annotation from a genuine grammatical category;
- state whether ketiv/qere or other textual layers affect the query if relevant to the selected representation;
- spot-check examples before interpreting aggregate differences.

For cross-corpus comparisons, do not transfer BHSA feature semantics automatically to DSS, Extrabiblical, Syriac, Ugaritic, or unrelated Text-Fabric corpora.

## Reproducibility

Record:

- Agora resource ID `bhsa`;
- selected BHSA/TF version if exposed by the runtime;
- node types queried;
- every feature used, especially `sp` versus `pdp`, `vs`, `vt`, `function`, and `typ`;
- search constraints and exclusions;
- representative passages used for validation.

## License and attribution

The BHSA repository states that its data is licensed **CC BY-NC 4.0** and provides a persistent citation identifier. Agora's plugin code license does not replace the corpus data license.

For published research or redistributed derived data, follow the BHSA/ETCBC attribution and non-commercial conditions recorded by the upstream project.
