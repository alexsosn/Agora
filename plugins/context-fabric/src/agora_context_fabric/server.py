from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Any

from .catalog import Catalog
from .gitstore import GitStore
from .mcp_tools import register_tools
from .resolver import ContextFabricResolver
from .service import ContextFabricService

LOGGER = logging.getLogger("agora_context_fabric")
DEFAULT_PLUGIN_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = Path(
    os.environ.get("AGORA_CORPUS_CACHE", "~/.cache/agora/context-fabric")
).expanduser()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Agora Context-Fabric MCP server",
    )
    parser.add_argument(
        "--plugin-root",
        type=Path,
        default=DEFAULT_PLUGIN_ROOT,
        help="Installed Context-Fabric plugin root containing resources/catalog.yaml",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="Corpus metadata/data cache directory",
    )
    transport = parser.add_mutually_exclusive_group()
    transport.add_argument(
        "--sse",
        type=int,
        metavar="PORT",
        help="Run with SSE transport on the given port",
    )
    transport.add_argument(
        "--http",
        type=int,
        metavar="PORT",
        help="Run with Streamable HTTP transport on the given port",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind for SSE/HTTP transports",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )
    return parser


def select_transport(args: argparse.Namespace) -> tuple[str, int | None]:
    if args.sse is not None:
        return "sse", args.sse
    if args.http is not None:
        return "http", args.http
    return "stdio", None


def build_runtime(
    cache_dir: Path = DEFAULT_CACHE_DIR,
    *,
    plugin_root: Path = DEFAULT_PLUGIN_ROOT,
) -> tuple[Any, ContextFabricService, Any]:
    """Build the Agora-enhanced upstream Context-Fabric MCP runtime.

    The upstream dependency is imported lazily so catalog/resolver tests do not
    require Context-Fabric itself to be installed.
    """
    try:
        from cfabric_mcp import corpus_manager, mcp
    except ImportError as exc:  # pragma: no cover - exercised in installed runtime
        raise RuntimeError(
            "cfabric-mcp is required to run the Context-Fabric plugin; install the plugin runtime dependencies"
        ) from exc

    catalog = Catalog.from_plugin_root(Path(plugin_root))
    store = GitStore(Path(cache_dir))
    resolver = ContextFabricResolver(catalog, store)
    service = ContextFabricService(catalog, resolver, corpus_manager)
    register_tools(mcp, service)
    return mcp, service, corpus_manager


def main() -> None:
    args = build_parser().parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
        LOGGER.setLevel(logging.DEBUG)

    transport, port = select_transport(args)
    mcp, _service, _corpus_manager = build_runtime(
        args.cache_dir,
        plugin_root=args.plugin_root,
    )

    try:
        from cfabric_mcp import tools as upstream_tools
    except ImportError as exc:  # pragma: no cover - exercised in installed runtime
        raise RuntimeError("cfabric-mcp is required to run this plugin") from exc
    upstream_tools.set_transport(transport)

    LOGGER.info(
        "Starting Agora Context-Fabric MCP with zero preloaded corpora (transport=%s)",
        transport,
    )
    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "sse":
        mcp.settings.host = args.host
        mcp.settings.port = port
        mcp.run(transport="sse")
    else:
        mcp.settings.host = args.host
        mcp.settings.port = port
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
