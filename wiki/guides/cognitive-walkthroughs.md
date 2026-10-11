# Researcher documentation: five cognitive walkthroughs

These routes were checked against the repository's public README, researcher guide, generated catalog and plugin pages on 11 October 2026. **Clicks** count link selections starting at the root README, not words searched or calls to a plugin. All answers are available without repository code or registry YAML; operational results still require the installed plugin and actual upstream data.

## 1. Find the ETCBC Targum corpus and what to install

**Shortest path:** [Root README](../../README.md) → [researcher guide](README.md) → [resource catalog](resources.md) → [Context-Fabric plugin](plugins/context-fabric.md).

**Observed route:** The resource catalog lists **ETCBC Targum Corpus** under the `targum` resource ID as Aramaic, **Community** integration evidence, lazily acquired and **CC BY-NC 4.0** (noncommercial). Click its new direct Context-Fabric plugin link and follow that plugin's [installation path](installation.md).

**Clicks:** 2 to identify the corpus; 3 to identify the plugin; 4 to reach installation.

**Recall burden:** None beyond the recognizable name “Targum”; the researcher guide explains that a corpus is not a plugin.

**Wrong turns:** No raw resource metadata or developer guide required. Searching only the plugin list would miss an independently selectable corpus.

**Answer without raw YAML/source:** Yes. Install **Context-Fabric**, then select registered resource `targum` when needed; its Community status is not a verified scholarly-quality claim.

## 2. Install BHSA and complete a first result

**Shortest path:** [Root README](../../README.md) → [researcher guide](README.md) → [Context-Fabric plugin](plugins/context-fabric.md) → [BHSA first-success tutorial](first-success/context-fabric.md).

**Observed route:** The plugin page links directly to the new tutorial. It gives the required `describe_available_corpus` → `prepare_corpus` → `load_corpus` progression; inspect the actual corpus word features (`lex`, `sp`, `pdp`) before constructing a bounded query. Record the selected version, source revision, word count unit and feature names.

**Clicks:** 3 to reach the tutorial after opening the README.

**Recall burden:** Recognize “BHSA” as a corpus to use *through* Context-Fabric; the researcher guide supplies that distinction.

**Wrong turns:** No architecture, CLI development setup or guessed raw lexeme format needed. An expensive cold load is preflighted rather than blindly repeated.

**Answer without raw YAML/source:** Yes. Actual word matches depend on the loaded data, so the tutorial deliberately does not invent output.

## 3. Decide whether Perseus CTS navigation is reliable

**Shortest path:** [Root README](../../README.md) → [researcher guide](README.md) → [Perseus plugin](plugins/perseus.md).

**Observed route:** The plugin's “Important limitations” distinguishes supported passage retrieval and Scaife search/discovery from **malformed legacy CTS navigation**. The [compatibility advisory](compatibility.md#current-upstream-limitations) explains why generic CTS reference enumeration is not claimed and links the safe recovery.

**Clicks:** 2 for the conclusion; 3 for the detailed compatibility advisory.

**Recall burden:** “CTS” and “Scaife” appear as visible labels; there is no need to remember provider internals before finding the limitation.

**Wrong turns:** A working passage request must not be mistaken for provider-wide navigation support; no upstream XML debugging is needed to answer the usability decision.

**Answer without raw YAML/source:** Yes. **Do not** depend on legacy CTS navigation generally; use independently supported passage and Scaife paths.

## 4. Find the historical first BHSA load cost and cache controls

**Shortest path:** [Root README](../../README.md) → [researcher guide](README.md) → [resource catalog](resources.md) → [Context-Fabric cache guide](context-fabric-cache.md).

**Observed route:** The catalog lists BHSA with an *historical, environment-specific* measured first-load observation (source 165 MB; compiled 866 MB; total cache 1,100 MB; first load 630 seconds, measurement dated 2026-09-04). It links to the cache guide for `corpus_cache_status`, active leases, cancellation and cleanup. Those numbers are neither a current-time requirement nor a prediction for another machine.

**Clicks:** 2 to inspect the cost entry; 3 for cache guidance.

**Recall burden:** Recognize BHSA's name in the catalog; “load cost” and “cache” headings are visible rather than implicit.

**Wrong turns:** No infrastructure diagram or raw measurements file is needed. The user must distinguish historical observation from a new machine's actual cost.

**Answer without raw YAML/source:** Yes. Inspect current usage with `corpus_cache_status`, not by assuming historical figures are current.

## 5. Interpret repeated Sefaria search hits

**Shortest path:** [Root README](../../README.md) → [researcher guide](README.md) → [Sefaria plugin](plugins/sefaria.md).

**Observed route:** The plugin page describes version-indexed duplicates and has a direct [Sefaria recovery guide](troubleshooting.md#sefaria-search-repeats-a-reference). The [compatibility advisory](compatibility.md#current-upstream-limitations) preserves the upstream known-issue ID and safe interpretation.

**Clicks:** 2 to see the caveat; 3 to reach symptom-specific recovery.

**Recall burden:** None: search duplication is described by observable behavior, not solely by a registry issue ID.

**Wrong turns:** Treating duplicate result rows as different textual occurrences would create a false frequency. Reinstalling a plugin will not correct upstream version indexing.

**Answer without raw YAML/source:** Yes. Deduplicate references for passage selection, retrieve the version/passage, and **do not** interpret raw row count as exact occurrence frequency.
