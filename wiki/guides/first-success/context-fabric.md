# First success: BHSA through Context-Fabric

## Start after installation

Open your installed **Context-Fabric** plugin. BHSA is a scholarly corpus selected *inside* that plugin, not another plugin to install. The first cold load can take time and use disk space. Begin with a version-aware preflight; the resource catalog records historical, machine-specific costs.

## Try this

Ask the agent: “In registered BHSA, inspect the available word features, then find up to five occurrences of the Hebrew lexeme MLK and explain which features and count unit you used.”

1. Use `list_available_corpora` or `describe_available_corpus(resource_id="bhsa")` to confirm the registered corpus and version (normally **2021**) and inspect its source and licenses.
2. Run `prepare_corpus(resource_id="bhsa", version="2021")` before `load_corpus(resource_id="bhsa", version="2021")`. Inspect preflight costs and any active load using `corpus_cache_status`; do not start duplicate cold loads.
3. After loading, **inspect** the reported schema, word node type and actual feature values before building a Text-Fabric **query**. Relevant BHSA word features include `lex` (lexeme), `sp` (part of speech) and `pdp` (phrase-dependent category). Do not assume the display string “MLK” exactly matches the corpus's encoding.
4. Construct a bounded word-level search with the *observed* `lex` value. Show at most five matching word locations and identify the exact query, counted unit **word**, actual matched spelling, feature names, corpus version and source revision.

## What success looks like

A small reproducible table of zero to five returned word locations with a traceable query and feature interpretation, or an explicit no-match explanation if the proposed lexeme spelling does not match the selected corpus version. The result is not a made-up total frequency; a sample limit is not a whole-corpus count.

## Interpretation limits

`sp` and `pdp` must not be interchanged. Likewise `vs` is a verbal stem and `vt` a different grammatical dimension. Record the selected source revision when available, and respect BHSA's recorded **CC BY-NC 4.0** rights; a verified integration path does not certify the corpus's scholarly interpretation.

## Next steps

Read the maintained [BHSA scholarly guidance](../../../plugins/context-fabric/skills/bhsa-research/SKILL.md#counting-and-comparison) or choose another corpus in the [resource catalog](../resources.md). For slow loads, follow [cache safety](../context-fabric-cache.md) or the [Context-Fabric plugin page](../plugins/context-fabric.md).
