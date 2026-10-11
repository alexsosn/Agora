# Issue #170 — researcher first-success tutorials

## Research (2026-10-11)
- Four plugin families and existing first-success user prompts are in README.md and GUIDANCE.first_success in scripts/generate_plugin_docs.py. The four generated plugin detail pages must be changed by editing that generator as well as checked-in outputs, not directly.
- The Context-Fabric agent skill calls `describe_available_corpus`, `prepare_corpus`, `load_corpus`, and schema/feature inspection before corpus querying. The BHSA skill says `lex`, `sp`, `pdp`, `vs`, `vt` are distinct. Do not assume the Hebrew lexeme string MLK has a particular corpus spelling; resolve labels from the loaded version. Large BHSA cold loads and rights remain separate considerations.
- The Perseus skill documents `find_author_names`, `get_author_resources`/`get_work_resources` for legacy CTS, Scaife metadata when appropriate, and passage retrieval only with actual discovered URNs. Its legacy CTS metadata/navigation may be malformed; discovery is not evidence that CTS retrieval will work.
- Sefaria supports `get_text` with selected `version_language` and `get_links_between_texts` for linked sources. Indexed search duplicates can reflect separate versions; do not count search result rows as unique occurrences.
- SEDRA supports `lookup_word` on Syriac Unicode, then `get_lexeme` only for a returned numeric lexeme ID. Multiple analyses should remain visible, and a lexeme gloss does not prove a passage-level reading.
- Current generated Claude/Codex integration representative-operation smokes support use of these tool families but are **not literal end-to-end tutorial acceptance runs**. Therefore do not assert actual returned edition URNs, number of commentary links, matched BHSA word counts, or presence of a particular SEDRA analysis without live evidence.
- The new installation guide and #172 symptom guide are evolving; tutorials should link to stable user-facing plugin pages, skill sections, resource catalog, and generic troubleshooting, not brittle deep headings requiring a moving branch.

## Plan and gates
1. **RED**: require four bounded self-contained post-installation guides from user's front door and each generated plugin page. Assert tool sequencing, actual-returned-ID and feature selection, success evidence, next step and direct limitations. Guard against CTS blanket support, Sefaria duplicate search count, SEDRA first-candidate selection, made-up BHSA counts.
2. **GREEN**: add four concise Markdown tutorials in `wiki/guides/first-success/`, link them from the user guide and by changing `scripts/generate_plugin_docs.py` followed by regenerating/committing the four generated pages. Avoid copying agent skills; link authoritative deeper guidance.
3. Review each workflow as a skeptical first-time researcher and inspect known upstream semantic limits. Run focused doc tests and generated-page freshness; Foundation as required. Merge only exact-head green CI and after independent adversarial review.

Non-goals: upstream tool changes, large downloads, automatic corpus imports, exhaustive manual, invented experimental results.
