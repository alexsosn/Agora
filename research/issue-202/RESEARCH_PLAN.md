# Issue #202 — normalize MCP structured outputs in direct smoke clients

## Research (2026-10-10)

The supported MCP SDK (current tested 1.30.x, `mcp<2`) can represent non-object Python tool results in `CallToolResult.structuredContent` as a synthetic object `{"result": <value>}`. In `scripts/smoke_context_fabric_local_import.py`, the local helper returns this dict unchanged; the final `list_available_corpora` call expects an iterable of resource dictionaries and therefore incorrectly iterates the string key `"result"`. The full Coptic composed acceptance `tests/live_issue214_full_coptic.py` already implements a narrow `set(content)=={"result"}` unwrap, so the two callers currently disagree. The Context-Fabric resource/feature-module/cold-load smoke scripts do not use direct `ClientSession.call_tool` or `structuredContent`; leave them unchanged.

## Scope and plan

1. Introduce one pure decoder for a completed successful `CallToolResult`. It prefers `structuredContent` when supplied; unwraps **only the exact one-key `{"result": value}`** wrapper for lists, scalars and nested values; ordinary dictionary results with other keys are preserved. Without structured data, parse text content as JSON (legacy SDK/tool shape). A server tool error raises a useful exception; absent payload raises a useful error.
2. RED unit tests use mock SDK-shaped results for wrapped list/scalar, ordinary dict, result+metadata dict, legacy text JSON, malformed text/empty content and tool error.
3. GREEN extraction in `scripts/context_fabric_mcp_result.py`; both direct stdio clients invoke it. Preserve their independent timeouts and tool-name diagnostics.
4. Run Foundation and full registered Coptic exact-head CI (the latter is triggered by changing `tests/live_issue214_full_coptic.py`); the Coptic path verifies actual MCP `list_available_corpora` on 2.4m slots, so do not count only static unit tests as live acceptance.
5. Independent skeptical review against real source and live SDK responses; do not change runtime server return values, tool schemas, pins, protocol version or corpus contracts in this ticket.

## Limitations

A genuine domain dictionary containing exactly the one key `result` is indistinguishable from the MCP synthetic wrapper without tool schema metadata. This behavior retains the already working Coptic client's contract; a typed per-tool schema normalization would be a future extension if needed. Do not swallow errors or silently turn an invalid MCP response into an empty list.
