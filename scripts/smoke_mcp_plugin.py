#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class LaunchSpec:
    plugin_id: str
    command: str
    args: tuple[str, ...]
    cwd: Path
    env: dict[str, str] | None = None


@dataclass(frozen=True)
class SmokeCase:
    expected_tools: set[str]
    tool_call: tuple[str, dict[str, Any]]


SMOKE_CASES: dict[str, SmokeCase] = {
    "perseus": SmokeCase(
        expected_tools={"get_passage", "search_perseus", "find_author_names"},
        tool_call=("find_author_names", {"query": "Homer", "limit": 1}),
    ),
    "sefaria": SmokeCase(
        expected_tools={"get_text", "text_search", "get_links_between_texts"},
        tool_call=(
            "get_text",
            {"reference": "Genesis 1:1", "version_language": "english"},
        ),
    ),
    "sedra": SmokeCase(
        expected_tools={"lookup_word", "get_lexeme"},
        tool_call=("lookup_word", {"query": "ܐܒܪܐ"}),
    ),
}


def load_plugin_launch(plugin_id: str, root: Path = ROOT) -> LaunchSpec:
    if plugin_id not in SMOKE_CASES:
        raise KeyError(f"no live smoke case is defined for plugin {plugin_id!r}")

    root = Path(root)
    plugin_root = root / "plugins" / plugin_id
    path = plugin_root / ".codex-plugin" / "mcp.json"
    with path.open("r", encoding="utf-8") as fh:
        document = json.load(fh)

    servers = document.get("mcpServers")
    if not isinstance(servers, dict) or set(servers) != {plugin_id}:
        raise ValueError(
            f"{path.relative_to(root)} must contain exactly the {plugin_id!r} MCP server"
        )
    server = servers[plugin_id]
    if server.get("type") != "stdio":
        raise ValueError(f"live smoke only supports stdio plugin configs: {plugin_id}")

    command = server.get("command")
    args = server.get("args", [])
    if not isinstance(command, str) or not command:
        raise ValueError(f"plugin {plugin_id!r} has no stdio command")
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise ValueError(f"plugin {plugin_id!r} has invalid stdio args")

    relative_cwd = server.get("cwd", ".")
    if not isinstance(relative_cwd, str):
        raise ValueError(f"plugin {plugin_id!r} has invalid cwd")
    cwd = (plugin_root / relative_cwd).resolve()
    try:
        cwd.relative_to(plugin_root.resolve())
    except ValueError as exc:
        raise ValueError(f"plugin {plugin_id!r} cwd escapes the plugin root") from exc

    configured_env = server.get("env")
    env: dict[str, str] | None = None
    if configured_env is not None:
        if not isinstance(configured_env, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in configured_env.items()
        ):
            raise ValueError(f"plugin {plugin_id!r} has invalid env")
        env = dict(configured_env)

    return LaunchSpec(
        plugin_id=plugin_id,
        command=command,
        args=tuple(args),
        cwd=cwd,
        env=env,
    )


@contextmanager
def _working_directory(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _tool_failed(result: Any) -> bool:
    return bool(
        getattr(result, "is_error", False)
        or getattr(result, "isError", False)
    )


def _tool_has_payload(result: Any) -> bool:
    if getattr(result, "content", None):
        return True
    if getattr(result, "structured_content", None) is not None:
        return True
    if getattr(result, "structuredContent", None) is not None:
        return True
    return False


async def smoke_plugin(plugin_id: str, *, timeout: float = 180.0) -> dict[str, Any]:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as exc:
        raise RuntimeError(
            "the live smoke harness requires MCP Python SDK v2; install mcp>=2,<3"
        ) from exc

    launch = load_plugin_launch(plugin_id)
    case = SMOKE_CASES[plugin_id]
    server_params = StdioServerParameters(
        command=launch.command,
        args=list(launch.args),
        env=launch.env,
    )

    async with asyncio.timeout(timeout):
        with _working_directory(launch.cwd):
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    initialize_result = await session.initialize()
                    listed = await session.list_tools()
                    tool_names = {tool.name for tool in listed.tools}
                    missing = case.expected_tools - tool_names
                    if missing:
                        raise RuntimeError(
                            f"{plugin_id} is missing expected MCP tools: {sorted(missing)}; "
                            f"available={sorted(tool_names)}"
                        )

                    tool_name, arguments = case.tool_call
                    result = await session.call_tool(tool_name, arguments=arguments)
                    if _tool_failed(result):
                        raise RuntimeError(
                            f"{plugin_id} live tool {tool_name!r} returned an MCP error: {result}"
                        )
                    if not _tool_has_payload(result):
                        raise RuntimeError(
                            f"{plugin_id} live tool {tool_name!r} returned no payload"
                        )

    return {
        "plugin": plugin_id,
        "server_name": getattr(initialize_result, "serverInfo", None)
        or getattr(initialize_result, "server_info", None),
        "tool_count": len(tool_names),
        "expected_tools": sorted(case.expected_tools),
        "called_tool": tool_name,
        "status": "ok",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Launch one Agora plugin through its generated Codex stdio MCP config, "
            "initialize MCP, verify representative tools, and execute one live lookup."
        )
    )
    parser.add_argument("plugin", choices=sorted(SMOKE_CASES))
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Maximum seconds for package startup, MCP handshake, and one live lookup",
    )
    args = parser.parse_args()

    try:
        report = asyncio.run(smoke_plugin(args.plugin, timeout=args.timeout))
    except Exception as exc:
        print(
            json.dumps(
                {"plugin": args.plugin, "status": "error", "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
