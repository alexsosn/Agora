---
name: sefaria-research
description: "Use this skill for research with Agora's Sefaria plugin: resolve canonical Jewish-text references, retrieve passages and translations, search the library, follow links/commentaries, use dictionaries, and interpret manuscript metadata without conflating these evidence types."
license: MIT
compatibility: "Requires the Agora Sefaria MCP integration and network access to Sefaria's hosted Texts MCP service."
metadata:
  provider: sefaria
  version: "0.1.0"
---

# Sefaria research workflow

Sefaria combines primary texts, translations, links, dictionaries, topics, structural metadata, and manuscript resources. Choose the tool that matches the evidence you need rather than treating all returned material as one undifferentiated text layer.

## Core rule

Resolve and preserve the **reference** used for every textual claim. Do not rely on a remembered English title, guessed folio/chapter syntax, or a search hit when an exact Sefaria reference can be established.

## Recommended workflow

### 1. Resolve names and references when uncertain

If a title, category, or topic name may be ambiguous, use the name-clarification/autocomplete tool before retrieval.

For a known canonical reference, go directly to `get_text`.

Keep the exact resolved reference in your notes and in reported results.

### 2. Retrieve the text layer you actually need

Use `get_text` for the passage itself.

Specify `version_language` deliberately when the research question depends on source text versus English translation. Do not quote an English rendering as though it were the source-language wording.

Use the English-translations tool when comparing available translations rather than assuming the default English version is unique or authoritative.

### 3. Search the library with language awareness

Use `text_search` for library-wide search and the book-specific search tool when the work is already known.

The upstream Sefaria MCP documentation explicitly warns that **Hebrew/Aramaic searches are generally more reliable than English searches**, because English wording varies across translations.

Therefore:

- prefer Hebrew/Aramaic search terms when the philological question permits it;
- treat an English no-hit as weak evidence;
- simplify an over-specific query before concluding a phrase is absent;
- state whether a result came from source-language or English search.

If search filters are needed, use the search-path clarification tool instead of guessing category paths.

### 4. Validate search hits by retrieving the passage

A search result is an index/search result, not yet a fully interpreted citation.

For claims based on search:

1. record the returned reference;
2. retrieve it with `get_text`;
3. inspect the relevant source/translation layer;
4. check surrounding context when interpretation depends on it.

Do not convert a search-result count directly into a philological frequency claim without understanding the search scope, versions, and indexing behavior.

### 5. Follow textual relationships explicitly

Use `get_links_between_texts` when the question concerns commentary, citation, intertextual linkage, or another Sefaria connection.

Do not describe every link as a direct quotation or historical dependency. Inspect the returned link/category metadata and distinguish commentary, cross-reference, related passage, and other relationship types when available.

### 6. Use dictionaries as lexical sources, not passage witnesses

Use the dictionary-search tool for lexical reference material.

A dictionary gloss is evidence about a lexicographic resource; it is not automatically the meaning required by a particular passage. Check the passage and context before selecting among senses.

### 7. Use structural/catalogue tools when scope matters

Use the shape/catalogue tools to establish work structure, hierarchy, and bibliographic metadata rather than inferring structure from a few references.

This is especially important for works whose citation systems differ from chapter-and-verse conventions.

### 8. Treat manuscript tools as a separate evidence layer

Use manuscript-availability and manuscript-image tools when the question concerns material witnesses.

Keep distinct:

- the normalized/digital Sefaria text;
- manuscript metadata;
- a manuscript image;
- your own reading of that image.

Do not claim that a manuscript image confirms a reading unless the relevant writing has actually been inspected.

## Tool selection guide

Use `get_text` when you know the reference and need text.

Use `text_search` when the text/reference is unknown and you are searching broadly.

Use the book-specific search when the work is known but the location is not.

Use `get_links_between_texts` for linked commentary/cross-references.

Use the dictionary tool for lexical entries.

Use translation tools for version comparison.

Use catalogue/shape tools for structure and bibliographic context.

Use manuscript tools only for manuscript-specific questions.

## Calendar data is situational, not textual evidence

The current-calendar tool reports present Jewish calendar/parashah/holiday information, including Diaspora versus Israel scheduling. Do not use this situational output as evidence for the historical dating or original context of an ancient text.

## Research cautions

### Translation variation

English search and translation results depend on available versions. When wording matters, identify the translation/version and compare source-language text where possible.

### Commentary versus primary text

Sefaria intentionally connects texts to commentaries and related sources. Always identify which work a returned passage belongs to before quoting or paraphrasing it.

### Absence claims

A failed search may reflect language, spelling, translation wording, filter scope, or indexing rather than true absence. Use alternative source-language forms and inspect search scope before making negative claims.

### Topics

Topic metadata is useful for discovery and orientation. Treat it as metadata/curation, not as a replacement for reading the cited primary and secondary sources.

## Reproducible reporting

For a substantive result, record:

- exact Sefaria reference(s);
- source-language versus translation layer;
- translation/version when relevant;
- search query and language;
- search filters or work restriction;
- link type/category when links support the argument;
- dictionary title/entry when lexical evidence is used;
- manuscript identifier when material-witness evidence is used.

If the question requires a historical-critical conclusion beyond what the tools directly establish, separate retrieved evidence from your interpretation.
