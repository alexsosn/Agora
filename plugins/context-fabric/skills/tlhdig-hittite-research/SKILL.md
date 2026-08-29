---
name: tlhdig-hittite-research
description: "Use this skill when inspecting or experimentally querying TLHdig-TF through Agora Context-Fabric: preserve its explicit prototype warning, query morphology on analysis nodes, distinguish zero-width damage points from damaged ranges, and keep ambiguous competing analyses visible."
license: MIT
compatibility: "Requires the Agora Context-Fabric MCP plugin and the registered alexsosn/TLHdig-TF resource. The pinned v0.1 dataset is explicitly unsuitable for dependable research conclusions."
metadata:
  provider: context-fabric
  resource: TLHdig-TF
  version: "0.1.0"
---

# TLHdig-TF / Hittite research workflow

TLHdig-TF converts TLHdig, the Thesaurus Linguarum Hethaeorum digitalis corpus, to Text-Fabric. The upstream repository currently labels the shipped `tf/0.1.0` build an **integration prototype — not a trustworthy conversion yet** and explicitly says not to rely on `0.1.0` for research.

Use this skill for testing the representation, developing queries, validating the converter, and exploring what future research workflows could look like. Do not turn current prototype output into a confident Hittitological result merely because the query executes.

## Load with the warning attached

Use `load_corpus` with the registered `TLHdig-TF` resource.

Agora pins a known upstream commit and `tf/0.1.0` for reproducibility. That pin means "same prototype build," not "validated edition."

Before interpreting any result, consult the upstream `KNOWN-ISSUES.md`, validation reports, and the current repository status.

## Morphology lives on `analysis` nodes

A central ontology rule is that morphology does **not** belong directly on `word` nodes.

The upstream project places fields such as:

- lemma;
- POS;
- morphology

on `analysis` nodes because one word can carry multiple competing analyses.

Therefore, a morphology query should conceptually traverse:

```text
word
  analysis ...
```

Do not write or describe a query as though `lemma`, `pos`, or `morph` were unambiguous word features.

## Ambiguity is first-class evidence

TLHdig source attributes can contain many competing morphological analyses. Some words are resolved by a selector; others remain genuinely undetermined.

Do not:

- take analysis 1 merely because it is first;
- count every candidate as an independent word occurrence without saying so;
- collapse unresolved alternatives into a single guessed morphology.

For a frequency result, state whether the count includes:

- only selected/resolved analyses;
- all candidate analyses;
- words with no selector;
- words with no analysis at all.

If the research question depends on disambiguation, current ambiguity should remain visible unless external evidence resolves it.

## Damage queries require range semantics

The upstream conversion represents damaged/editorial spans with `cluster` nodes.

A crucial current invariant is **`width>1`** when using cluster coverage as evidence that signs are damaged. Zero-width source markers such as `<del_in/><del_fin/>` are preserved as point events and anchored to a neighboring sign so Text-Fabric does not discard an unlinked node.

That structural anchor does not mean the neighboring sign is itself damaged.

So a conceptual exclusion such as "attestations not restored/damaged" must distinguish:

```text
cluster type=del width>1
```

from zero-width point markers.

Do not equate "cluster structurally covers this sign" with "the source says this sign is damaged" without checking range width and cluster type.

## Unclosed damage is convention-dependent

The upstream README explains that an unclosed `del_in` has no explicit closing marker. The current conversion convention extends such a range to the end of its line.

Any damage-rate statistic that depends on those extents inherits that convention. State the convention when it matters; do not present the resulting percentage as a direct fact encoded by the source XML.

## Editorial evidence versus linguistic evidence

When testing linguistic queries, consider whether a candidate occurrence is:

- directly read;
- reconstructed;
- uncertain;
- excised/redundant;
- inside another editorial range;
- supported only by an unresolved morphological candidate.

One value of the TF model is that these dimensions can eventually be combined explicitly. Do not erase them merely to obtain a cleaner frequency table.

## Cross-document aggregation

The prototype makes corpus-wide aggregation technically easy, but technical ease does not validate the underlying conversion.

If using a cross-document count to test the implementation:

1. define the node/analysis unit;
2. document ambiguity handling;
3. document damage/editorial filters;
4. spot-check source XML or TLHdig for representative hits;
5. label the result as prototype/validation output unless the relevant conversion gates have passed.

## Cuneiform limitations

The upstream project states that Unicode cuneiform is line-level rather than sign-aligned unless upstream alignment exists.

Do not claim a one-to-one sign-to-Unicode-cuneiform alignment from TF structure when the source does not supply one.

TLHdig-TF also does not become a critical edition merely by converting the corpus to a graph model.

## Reproducibility

For any reported experiment, record:

- Agora resource ID `TLHdig-TF`;
- pinned TF version `0.1.0` and source commit when exposed;
- current upstream prototype/known-issue status;
- node types/features queried;
- treatment of competing `analysis` nodes;
- damage cluster type and whether **`width>1`** was required;
- assumptions for unclosed ranges;
- examples checked against source TLHdig/AOxml.

Until upstream validation changes the status, phrase conclusions as tests of the conversion or provisional corpus observations, not established facts about Hittite.
