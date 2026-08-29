---
name: sedra-research
description: Use this skill for Syriac lexical research with Agora's SEDRA plugin: distinguish word-form lookup from lexeme lookup, preserve ambiguous candidate analyses, follow returned lexeme IDs, and avoid inventing morphology or attestation evidence not supplied by SEDRA IV.
license: MIT
compatibility: Requires the Agora SEDRA MCP plugin and network access to Beth Mardutho's public SEDRA IV JSON endpoints.
metadata:
  provider: sedra
  version: "0.1.0"
---

# SEDRA research workflow

Agora's SEDRA integration is intentionally narrow and transparent. It exposes Beth Mardutho's SEDRA IV word and lexeme data without trying to replace the upstream lexical model with Agora-specific interpretation.

## Core rule

A **word form is not the same thing as a lexeme**.

Do not collapse candidate word analyses into one dictionary entry, and do not treat a lexeme record as evidence that a particular surface form has only one possible analysis.

## Recommended workflow

### 1. Start from the observed form

Use `lookup_word` with the Syriac form you actually have.

The tool accepts Syriac Unicode in consonantal, partially vocalized, or fully vocalized form; it can also accept a SEDRA word ID.

Prefer copying the form from the source under study rather than silently normalizing spelling first. If you also want to test a normalized or unvocalized form, run it as a separate lookup and report that normalization.

### 2. Preserve all plausible candidates

Word lookup can return multiple candidate forms/analyses.

Do not select the first result automatically. Compare candidates using the grammatical and lexical metadata returned by SEDRA and the syntax/context of the passage being studied.

If the available context does not resolve the ambiguity, preserve the ambiguity in the conclusion.

### 3. Follow lexeme IDs explicitly

When a candidate points to a lexeme, use `get_lexeme` with the returned numeric lexeme ID.

A lexeme record may include information such as:

- Syriac lexical form;
- root;
- lexical/category information;
- glosses;
- etymological information;
- linked word forms.

Treat these as fields supplied by SEDRA. Do not add unattested root derivations, semantic histories, or morphological categories and then present them as SEDRA data.

### 4. Compare lexical data with passage context

A dictionary/lexicon entry lists lexical possibilities. It does not by itself establish which sense or grammatical analysis is correct in one passage.

For passage-level interpretation:

1. retain the exact Syriac word form;
2. inspect all relevant SEDRA candidates;
3. retrieve candidate lexemes;
4. compare returned grammatical metadata with the surrounding syntax;
5. distinguish SEDRA's data from your contextual inference.

## Input handling

Use Unicode Syriac directly when possible.

Do not transliterate into Latin characters merely because the model finds Latin text easier to manipulate: transliteration may lose vocalization or orthographic distinctions relevant to lookup.

If a lookup fails:

- retry an explicitly unvocalized form if vocalization may differ;
- check Unicode characters and combining marks;
- distinguish "no result" from a network/API error;
- do not invent a SEDRA numeric ID.

## Word IDs and lexeme IDs

Keep IDs typed by role:

- a **word ID** identifies a SEDRA word-form record;
- a **lexeme ID** identifies a lexical entry.

Use `lookup_word` for word-form lookup and `get_lexeme` for a numeric lexeme ID.

Do not pass an arbitrary numeric identifier between tools without confirming what kind of ID it is.

## Ambiguity is data

Multiple analyses are not an error condition.

For philological work, ambiguity may reflect:

- consonantal homography;
- vocalization differences;
- inflectional ambiguity;
- distinct lexemes with similar forms;
- limitations of the available context or upstream analysis.

Report the candidates that matter and explain the contextual reason for preferring one if you resolve the ambiguity.

## Limits of this plugin

Agora's SEDRA adapter is a read-only lexical lookup interface. Do not imply that it provides capabilities it does not expose, such as:

- corpus-wide concordance counts;
- syntactic search;
- manuscript collation;
- automatic contextual disambiguation;
- exhaustive historical attestations;
- a new Agora-authored morphological analysis.

If the research question requires those capabilities, combine SEDRA lexical evidence with an appropriate Syriac corpus or another specialized source.

## Reproducible reporting

For a substantive lexical claim, record:

- exact Syriac query form;
- whether the input was normalized/unvocalized;
- relevant word-form candidate(s);
- lexeme ID(s) followed with `get_lexeme`;
- SEDRA fields supporting the statement;
- contextual reasoning that goes beyond the upstream record.

When quoting a gloss or category, attribute it to SEDRA rather than presenting it as an independent conclusion from the model.
