# Troubleshooting Agora by symptom

Choose the behavior you observe. Each section separates the likely cause from a safe recovery action and the authoritative deeper documentation. Agora integration issues, remote provider failures and upstream scholarly limitations should not be conflated.

## Choose the symptom

- [Marketplace or plugin is not visible](#marketplace-or-plugin-is-not-visible)
- [MCP server does not start](#mcp-server-does-not-start)
- [uv, uvx or Python is not found](#uv-uvx-or-python-is-not-found)
- [Remote lookup fails](#remote-lookup-fails)
- [Corpus acquisition or compilation appears stuck](#corpus-acquisition-or-compilation-appears-stuck)
- [Corpus cache uses unexpected disk space](#corpus-cache-uses-unexpected-disk-space)
- [Search count stops at 10,000](#search-count-stops-at-10000)
- [CUC text formats appear missing](#cuc-text-formats-appear-missing)
- [Perseus passage works but navigation fails](#perseus-passage-works-but-navigation-fails)
- [Sefaria search repeats a reference](#sefaria-search-repeats-a-reference)
- [Plugin works in one client but not another](#plugin-works-in-one-client-but-not-another)

## Marketplace or plugin is not visible

**Likely cause:** The plugin may not have been imported, made available to your workspace role, installed for your client, or displayed on this surface.

**Safe next action:** Check the marketplace/import results and plugin installation policy with your workspace administrator; for Claude Code, inspect the installed marketplace through the host's plugin controls. Do not delete an entire marketplace as a single-plugin recovery.

**Details:** [Installation](installation.md#chatgpt--managed-codex-workspace-import), [OpenAI's marketplace import guidance](https://help.openai.com/en/articles/20001504-importing-and-syncing-plugin-marketplaces-from-github), and [compatibility](compatibility.md#can-i-use-this-plugin).

## MCP server does not start

**Likely cause:** The configured local process may not resolve its interpreter or environment, or the selected transport may differ from this client's supported path.

**Safe next action:** Capture the startup error and check the generated plugin launch metadata plus the documented runtime prerequisites; test the appropriate supported client/transport rather than changing provider semantics.

**Details:** [Runtime prerequisites](installation.md#runtime-prerequisites) and [client paths](compatibility.md#generated-client-paths).

## uv, uvx or Python is not found

**Likely cause:** The host cannot locate uv/uvx, or uv cannot obtain the plugin's required Python interpreter.

**Safe next action:** Install uv using the upstream supported method, confirm it is on PATH, and let uv resolve an eligible Python version; do not rewrite generated launch commands as a workaround.

**Details:** [Runtime prerequisites](installation.md#runtime-prerequisites) and [plugin integration guidance](plugins/context-fabric.md#prerequisites).

## Remote lookup fails

**Likely cause:** A hosted service or upstream endpoint may be temporarily unavailable, unreachable, or returning a provider-specific error.

**Safe next action:** Preserve the provider response and check network/provider status; retry a bounded representative operation when service is healthy. Reinstalling Agora cannot repair a remote provider outage.

**Details:** [Compatibility limitations](compatibility.md#current-upstream-limitations), [Perseus](plugins/perseus.md#upstream), [Sefaria](plugins/sefaria.md#upstream), and [SEDRA](plugins/sedra.md#upstream).

## Corpus acquisition or compilation appears stuck

**Likely cause:** A cold acquisition/compilation can consume considerable time or an existing load may hold a Git/cache lease; client timeouts can interrupt an otherwise valid request.

**Safe next action:** Use describe_available_corpus → prepare_corpus → load_corpus and inspect corpus_cache_status before reattempting. Do not launch duplicate loads blindly; use documented cancellation and preflight limits.

**Details:** [Context-Fabric cache and cold-load guide](context-fabric-cache.md#recommended-first-load-workflow) and [installation timeouts](installation.md#troubleshooting).

## Corpus cache uses unexpected disk space

**Likely cause:** Compiled corpus artifacts and cached Git source snapshots are separately retained, and active leases prevent premature deletion.

**Safe next action:** Use corpus_cache_status to inspect size and active loads; unload unused corpora before prune_corpus_cache or targeted remove_cached_corpus. Never delete an actively leased snapshot manually.

**Details:** [Cache management](context-fabric-cache.md) and [installation cache overview](installation.md#context-fabric-first-load-and-cache).

## Search count stops at 10,000

**Likely cause:** The pinned cfabric-mcp count-only search is computed after the result cache cap of 10,000, so that count can be a lower bound.

**Safe next action:** Narrow the query or verify the intended exact aggregate with a corpus-native Text-Fabric method; do not report 10,000 as an exact total for potentially larger matches.

**Details:** [Verified known-issue statement](compatibility.md#current-upstream-limitations) and [Context-Fabric limitations](plugins/context-fabric.md#important-limitations).

## CUC text formats appear missing

**Likely cause:** CUC may expose representations in sign and usign features without paired fmt metadata recognized by generic text-format discovery.

**Safe next action:** Inspect CUC sign and usign features directly; a negative generic-format result is not evidence that the Latin or Ugaritic representations are absent. Avoid fabricating a format registry.

**Details:** [Known CUC discovery limitation](compatibility.md#current-upstream-limitations) and [Context-Fabric research method](plugins/context-fabric.md#typical-research-tasks).

## Perseus passage works but navigation fails

**Likely cause:** Upstream legacy CTS GetLabel/GetValidReff metadata/navigation can return malformed content even when passage retrieval or Scaife-backed discovery works.

**Safe next action:** Continue with independently supported passage retrieval and Scaife discovery; do not invent adjacent CTS references or claim reliable provider-wide CTS navigation.

**Details:** [Perseus limitations](plugins/perseus.md#important-limitations) and [structured known issue](compatibility.md#current-upstream-limitations).

## Sefaria search repeats a reference

**Likely cause:** Sefaria search may return multiple version-indexed hits for one textual reference without version identity in the result rows.

**Safe next action:** Treat hits as ambiguous; deduplicate references for passage selection, retrieve the specific text/version, and do not interpret raw row count as exact frequency.

**Details:** [Sefaria limitations](plugins/sefaria.md#important-limitations) and [known issue](compatibility.md#current-upstream-limitations).

## Plugin works in one client but not another

**Likely cause:** Generated launch transports differ by host; managed ChatGPT GitHub-imported MCP plugins can be Desktop only, and a supported generated client path does not guarantee every surface.

**Safe next action:** Check the plugin's current workspace/role policy and the matching Claude or Codex transport. A Desktop-only plugin cannot run in ChatGPT web; use a supported surface without modifying the plugin transport contract.

**Details:** [Client decision table](compatibility.md#can-i-use-this-plugin), [managed workspace import](installation.md#chatgpt--managed-codex-workspace-import), and [OpenAI plugin help](https://help.openai.com/en/articles/20001256-plugins-in-chatgpt).

