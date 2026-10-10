"""Normalize successful MCP CallToolResult payloads for Agora stdio smoke clients.

MCP Python SDK 1.x wraps non-object tool results such as list[str] in
structuredContent={"result": list}. Preserve all regular object tool responses.
"""
from __future__ import annotations

import json
from typing import Any


def decode_mcp_result(result: Any, *, tool_name: str) -> Any:
    """Decode structured MCP results or legacy JSON text without losing errors."""
    if result.isError:
        raise RuntimeError(f"{tool_name}: {result.content}")
    structured = result.structuredContent
    if structured is not None:
        if isinstance(structured, dict) and set(structured) == {"result"}:
            return structured["result"]
        return structured
    if not result.content:
        raise ValueError(f"{tool_name}: MCP response has no structured or text payload")
    text = getattr(result.content[0], "text", None)
    if not isinstance(text, str):
        raise ValueError(f"{tool_name}: MCP response text payload is missing")
    return json.loads(text)
