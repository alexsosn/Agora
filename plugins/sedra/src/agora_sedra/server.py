from __future__ import annotations

from typing import Any

from .client import SedraClient
from .mcp_tools import register_tools


def build_server(client: SedraClient | None = None) -> Any:
    try:
        from fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - installed runtime path
        raise RuntimeError(
            "fastmcp is required to run the Agora SEDRA plugin; run it through the plugin's uv project"
        ) from exc

    mcp = FastMCP("sedra")
    register_tools(mcp, client or SedraClient())
    return mcp


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
