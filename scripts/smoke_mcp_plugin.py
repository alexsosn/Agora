#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
import os
import platform
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

import yaml

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
    "context-fabric": SmokeCase(
        expected_tools={
            "list_available_corpora",
            "describe_available_corpus",
            "list_collection_members",
            "prepare_corpus",
            "load_corpus",
        },
        # This validates the shipped runtime/catalog without downloading a corpus.
        tool_call=("list_available_corpora", {"query": "Ugaritic"}),
    ),
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


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


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


def _load_live_verification_reference(
    plugin_id: str,
    root: Path = ROOT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    plugins_doc = _load_yaml(Path(root) / "registry/plugins.yaml")
    checks_doc = _load_yaml(Path(root) / "registry/verification-checks.yaml")
    plugins = {item["id"]: item for item in plugins_doc["plugins"]}
    checks = {item["id"]: item for item in checks_doc["checks"]}

    plugin = plugins.get(plugin_id)
    if plugin is None:
        raise KeyError(f"plugin {plugin_id!r} is not present in registry/plugins.yaml")
    evidence = plugin["verification"]["clients"]["codex"]
    live_references: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for reference in evidence["checks"]:
        check = checks.get(reference["check_id"])
        if check is not None and check.get("kind") == "live":
            live_references.append((check, reference))
    if len(live_references) != 1:
        raise ValueError(
            f"plugin {plugin_id!r} must have exactly one Codex live verification check; "
            f"found {len(live_references)}"
        )
    return live_references[0]


def _local_revision(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    revision = result.stdout.strip()
    return revision if result.returncode == 0 and revision else "unknown"


def _distribution_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _command_version(command: str) -> str | None:
    try:
        result = subprocess.run(
            [command, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = (result.stdout or result.stderr).strip()
    return output if result.returncode == 0 and output else None


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc).replace(microsecond=0)
    return value.isoformat().replace("+00:00", "Z")


def build_trace_metadata(
    plugin_id: str,
    *,
    launch: LaunchSpec | None = None,
    env: Mapping[str, str] | None = None,
    checked_at: datetime | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    root = Path(root).resolve()
    check, reference = _load_live_verification_reference(plugin_id, root)
    environment = dict(os.environ if env is None else env)
    when = checked_at or datetime.now(timezone.utc)

    repository = environment.get("GITHUB_REPOSITORY")
    run_id = environment.get("GITHUB_RUN_ID")
    server_url = environment.get("GITHUB_SERVER_URL")
    run_url = (
        f"{server_url.rstrip('/')}/{repository}/actions/runs/{run_id}"
        if server_url and repository and run_id
        else None
    )
    revision = environment.get("GITHUB_SHA") or _local_revision(root)

    if launch is None:
        launch_data: dict[str, Any] | None = None
    else:
        try:
            relative_cwd = launch.cwd.resolve().relative_to(root)
            cwd = relative_cwd.as_posix()
        except ValueError:
            cwd = str(launch.cwd)
        launch_data = {
            "command": launch.command,
            "args": list(launch.args),
            "cwd": cwd,
            "env": launch.env,
        }

    return {
        "check_id": check["id"],
        "checked_at": _iso_utc(when),
        "plugin": plugin_id,
        "client": check["client"],
        "transport": check["transport"],
        "agora_revision": revision,
        "github": {
            "repository": repository,
            "workflow": environment.get("GITHUB_WORKFLOW"),
            "job": environment.get("GITHUB_JOB"),
            "run_id": run_id,
            "run_attempt": environment.get("GITHUB_RUN_ATTEMPT"),
            "run_url": run_url,
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "mcp_sdk": _distribution_version("mcp"),
            "uv": _command_version("uv"),
        },
        "launch": launch_data,
        "verification_inputs": reference["inputs"],
    }


def build_error_report(
    plugin_id: str,
    error: Exception,
    *,
    launch: LaunchSpec | None = None,
    env: Mapping[str, str] | None = None,
    checked_at: datetime | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    try:
        trace = build_trace_metadata(
            plugin_id,
            launch=launch,
            env=env,
            checked_at=checked_at,
            root=root,
        )
    except Exception as trace_exc:
        trace = {
            "plugin": plugin_id,
            "trace_error": f"{type(trace_exc).__name__}: {trace_exc}",
        }
    return {
        **trace,
        "status": "error",
        "error": f"{type(error).__name__}: {error}",
    }


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


async def smoke_plugin(
    plugin_id: str,
    *,
    timeout: float = 180.0,
    launch: LaunchSpec | None = None,
) -> dict[str, Any]:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as exc:
        raise RuntimeError(
            "the live smoke harness requires MCP Python SDK v2; install mcp>=2,<3"
        ) from exc

    launch = launch or load_plugin_launch(plugin_id)
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
        **build_trace_metadata(plugin_id, launch=launch),
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

    launch: LaunchSpec | None = None
    try:
        launch = load_plugin_launch(args.plugin)
        report = asyncio.run(smoke_plugin(args.plugin, timeout=args.timeout, launch=launch))
    except Exception as exc:
        report = build_error_report(args.plugin, exc, launch=launch)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 1

    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
