# First success: CAL lexicon with provenance

## Start after installation

Install the **CAL** plugin through Agora's Claude/Codex marketplace. It starts the pinned `cal-mcp==0.1.0` package locally over stdio and reaches remote [CAL](https://cal.huc.edu/) only when a CAL-backed tool is used. Check that the client lists `cal_lexicon_lookup` among the 36 released tools. Merely listing tools does not contact CAL.

## Try this

Ask the agent: “Use CAL to look up `br`, select `br N`, and report the original lexicon entry and provenance without guessing any inflected-text senses.”

1. Make one explicit MCP call: `cal_lexicon_lookup(query="br", lemma_key="br N")`.
2. On a fresh uncached lookup, a successful `found` result normally takes two upstream GET requests: a bounded browse and a selected lexical entry. A warm process-local cache can avoid repeated requests. Record CAL provenance (source URL and retrieval time) and preserve any supplied ambiguity.
3. If the tool reports no match, truncation, an upstream/network failure or HTTP 429, keep that outcome explicit. Do not automatically crawl other lemmas or retry a 429.
4. Report only the supported CAL citation/entry details; avoid guessing period, language, corpus frequency or attested contexts from a single dictionary entry.

## What success looks like

The installed generated-client stdio transport initializes, advertises the expected tools, and returns a structured `found` lexicon entry with source provenance. One such response is a representative reachability test, **not** proof of comprehensive lexicon coverage or production request throughput.

## Interpretation limits

The software is MIT; CAL's underlying lexical, text and bibliography data and service terms are **upstream-dependent**. A lexicon entry is a dictionary resource, not itself the attestation in a particular manuscript. The provider is remote; CAL-MCP applies pacing, rolling request caps and cooldown after upstream 429. The generated **Codex** stdio path completed a bounded, provenance-bearing `br N` lookup in [live check 38234918961](https://github.com/alexsosn/Agora/actions/runs/38234918961), so the Codex integration path is **verified** in the canonical registry. The generated **Claude** path has not passed an equivalent live check and remains **community**, as does the aggregate CAL plugin status. These generated-path checks do not execute the actual-client application or certify CAL's scholarly coverage.

## Next steps

Read the [CAL plugin page](../plugins/cal.md), the [upstream CAL-MCP integration handoff](https://github.com/alexsosn/CAL-MCP/blob/v0.1.0/docs/integrations/standalone-mcp.md), and the [troubleshooting by symptom](../troubleshooting.md#remote-lookup-fails) guide. Use a separate explicit CAL tool call to investigate a manuscript or lexical context.
