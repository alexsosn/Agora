# Issue #173 — user docs integrity and cognitive walkthroughs

## Research (2026-10-11; pre-merge integration base #245)
- Existing tests already compare all canonical registered resources/modules to the generated resource catalog, all four plugin pages with registry capabilities/advisories and freshness, and validate the landing guide's local links. The curated scholarly guide independently checks eight SKILL.md heading anchors. Do not duplicate these coverage checks.
- Missing invariant: links in generated plugin pages, first-success tutorials, compatibility, troubleshooting, and resource catalog can break while the landing page's link checker stays green. A small curated set of user-facing Markdown documents should have file and fragment validation. External provider URLs are out of scope.
- Targum user route: README → researcher guide → resource catalog (ETCBC Targum Corpus, `targum`) → install Context-Fabric. It is a lazily acquired noncommercial Aramaic corpus, not a standalone plugin.
- BHSA route: README → researcher guide → Context-Fabric plugin page → first-success BHSA tutorial → describe/prepare/load, inspect features then search. No registry YAML required.
- Perseus route: README → plugin page or compatibility → documented malformed legacy CTS navigation; independently supported passage/Scaife operation remains separate.
- Cost route: README → resource catalog (BHSA's historical measurement dated 2026-09-04, not a prediction) → cache guidance.
- Sefaria route: README → Sefaria plugin page/compatibility → duplicate indexed-version search references are not exact occurrences.

## Plan / gates
1. **RED**: bounded test for all local links/fragments in enumerated researcher-facing surfaces and for a cognitive walkthrough record with five reproducible routes, observed click count, terminology/recall burden, wrong turns and no raw YAML requirement.
2. **GREEN**: add `wiki/guides/cognitive-walkthroughs.md` recording the five paths and links, with an entry from researcher guide. Reuse existing plugin/catalog/skill semantic checks.
3. Run focused tests, generator freshness, full CI as required after #245 merges and branch reconciliation, then independent adversarial review.

Non-goals: full Markdown renderer, external link monitoring, scholarly certification, duplicating every existing schema/generator assertion.
