# Issue #172 — researcher installation and symptom-based recovery

## Research (2026-10-11)
- `wiki/guides/installation.md` mixes host install, full local Codex development/testing (~24 lines), runtime requirements, corpus lifecycle, evidence and a six-item generic troubleshooting paragraph. User guide and generated plugin pages route virtually all failures to this one section.
- The four structured known issues in `registry/plugins.yaml` and the detailed decision-first `wiki/guides/compatibility.md` are the source for the Sefaria duplicate, Perseus legacy CTS, Context-Fabric 10k count and CUC sign/usign semantic caveats. These are *upstream limitations*; Agora must not repair results by inventing semantics.
- `wiki/guides/plugins/*.md` are generated from `scripts/generate_plugin_docs.py`; update both generator and checked-in pages. The current source `wiki/guides/README.md` is handwritten and can route directly to the symptom index.
- Host authority: OpenAI's updated [GitHub marketplace import and sync guide](https://help.openai.com/en/articles/20001504-importing-and-syncing-plugin-marketplaces-from-github) and [Plugins in ChatGPT](https://help.openai.com/en/articles/20001256-plugins-in-chatgpt) confirm admin import, managed access, Desktop-only web restriction, Sync now and marketplace deletion semantics. Codex's [official package instructions](https://developers.openai.com/plugins/build/plugins) document local plugin marketplace commands. Keep Agora-specific root path and plugin names, avoid copying volatile host UI steps where the help links suffice.
- `CONTRIBUTING.md` is the contributor landing page; move the local clone/Codex testing commands into a dedicated developer section with a contributor entrypoint. Keep user-facing host-owned update/remove commands and Context-Fabric's `describe_available_corpus → prepare_corpus → load_corpus`, status, cancellation and cache cleanup.

## Plan
1. Preserved RED test: all eleven requested observable symptoms have self-contained cause/action/deeper reference sections; installation and contributor areas are separated; generated plugin pages deep-link to relevant recoveries and canonical output stays fresh; known-issue compatibility rows link directly to their symptom.
2. GREEN: add a compact `wiki/guides/troubleshooting.md` index using stable human headings; shorten install page by relocating local dev testing and replacing generic recovery bullets with an index link; update compatibility and generator/plugin outputs; preserve previous limitations and rights.
3. Validate focused contracts, docs generators, Foundation as appropriate, independent skeptical walkthroughs starting only from symptom wording, and merged exact-head review.

Do not add an Agora package manager/uninstaller, claim untested platforms, modify upstream behavior, or promote plugin integration to scholarly suitability.
