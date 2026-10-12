# CAL-MCP (Agora candidate)

The upstream [CAL-MCP v0.1.0](https://github.com/alexsosn/CAL-MCP/releases/tag/v0.1.0) is a local Python stdio server; it retrieves CAL content on demand from `https://cal.huc.edu/`. Agora supplies launch and discovery, **not** a CAL-specific parser or database. The pinned software is `cal-mcp==0.1.0` and requires Python >=3.11 (client launcher: `uvx`). See the [upstream integration contract](https://github.com/alexsosn/CAL-MCP/blob/main/docs/integrations/agora.md).

Data/service terms are **upstream-dependent**: upstream CAL and underlying editions may have rights distinct from the MIT software license. The generated Claude and Codex manifests are local stdio launchers, not hosted CAL endpoints.

## First successful use

Install uv/uvx, enable CAL in the Agora plugin marketplace and allow the generated local `cal-mcp` child to initialize. List the advertised **36 v0.1.0** tools without contacting CAL. Confirm its executable identity before the first remote call.

For one CAL provider reachability smoke, call the published tool with one fixed lookup; perform **one CAL** logical operation, not repeated retries:

```json
{"tool": "cal_lexicon_lookup", "arguments": {"query": "br", "lemma_key": "br N"}}
```

A successful `found` result uses **two** bounded CAL transport starts (one lexicon browse plus one selected-entry GET) in upstream 0.1.0. The dedicated downstream smoke forces upstream `max_retries=0` with a 25-start hard cap; the current stdio subprocess launcher does **not** reliably flush its shutdown-only attempt report, so an exact live start count is not claimed. A response with `found` and CAL provenance establishes only that this installed integration could reach CAL for one explicit lookup; it does not assess every lexeme or other research tool. HTTP 429 and upstream/network faults are not reasons to crawl, retry aggressively or blame generated manifests. Normal CAL-MCP pacing, attempt limits and cooldown apply; do not claim safe batch throughput or run the complete upstream smoke matrix.

Client-specific verification is initially marked **community** until a genuine installed generated-client smoke is recorded. Do not advertise unsupported ChatGPT web/mobile hosting.
