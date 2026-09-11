#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
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
FILE_BACKED_ENVIRONMENT_KINDS = {"uv-lock", "uv-constraints"}
PERSEUS_ROUTING_KNOWN_ISSUE_ID = "perseus/cts-scaife-inventory-routing"
PERSEUS_ROUTING_TARGET_WORK = "urn:cts:greekLit:tlg0006.tlg020"
EVIDENCE_RANK = {"community": 1, "verified": 2}
MAX_EXCEPTION_DETAIL_DEPTH = 6
MAX_EXCEPTION_GROUP_CHILDREN = 16
MAX_EXCEPTION_MESSAGE_CHARS = 4000


@dataclass(frozen=True)
class LaunchSpec:
    plugin_id: str
    command: str
    args: tuple[str, ...]
    cwd: Path
    env: dict[str, str] | None = None


@dataclass(frozen=True)
class ConnectionSpec:
    plugin_id: str
    client: str
    transport: str
    command: str | None = None
    args: tuple[str, ...] = ()
    cwd: Path | None = None
    env: dict[str, str] | None = None
    url: str | None = None


@dataclass(frozen=True)
class SmokeCase:
    expected_tools: set[str]
    tool_call: tuple[str, dict[str, Any]]
    known_issue_canaries: tuple[str, ...] = ()


class SmokePhaseError(RuntimeError):
    def __init__(self, phase: str, error: Exception) -> None:
        self.phase = phase
        super().__init__(f"{phase}: {type(error).__name__}: {error}")


SMOKE_CASES: dict[str, SmokeCase] = {
    "context-fabric": SmokeCase(
        expected_tools={
            "list_available_corpora",
            "describe_available_corpus",
            "list_collection_members",
            "prepare_corpus",
            "load_corpus",
        },
        tool_call=("list_available_corpora", {"query": "Ugaritic"}),
    ),
    "perseus": SmokeCase(
        expected_tools={"get_passage", "search_perseus", "find_author_names"},
        tool_call=("find_author_names", {"query": "Homer", "limit": 1}),
        known_issue_canaries=(PERSEUS_ROUTING_KNOWN_ISSUE_ID,),
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validated_stdio_connection(
    plugin_id: str,
    client: str,
    server: Mapping[str, Any],
    *,
    plugin_root: Path,
    root: Path,
    expand_claude_root: bool,
) -> ConnectionSpec:
    command = server.get("command")
    args = server.get("args", [])
    if not isinstance(command, str) or not command:
        raise ValueError(f"plugin {plugin_id!r} has no stdio command for {client}")
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise ValueError(f"plugin {plugin_id!r} has invalid stdio args for {client}")

    if expand_claude_root:
        replacement = str(plugin_root.resolve())
        command = command.replace("${CLAUDE_PLUGIN_ROOT}", replacement)
        args = [item.replace("${CLAUDE_PLUGIN_ROOT}", replacement) for item in args]

    relative_cwd = server.get("cwd", ".")
    if not isinstance(relative_cwd, str):
        raise ValueError(f"plugin {plugin_id!r} has invalid cwd for {client}")
    if expand_claude_root:
        relative_cwd = relative_cwd.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root.resolve()))
        cwd_candidate = Path(relative_cwd)
        cwd = cwd_candidate.resolve() if cwd_candidate.is_absolute() else (plugin_root / cwd_candidate).resolve()
    else:
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
            raise ValueError(f"plugin {plugin_id!r} has invalid env for {client}")
        env = dict(configured_env)
        if expand_claude_root:
            replacement = str(plugin_root.resolve())
            env = {key: value.replace("${CLAUDE_PLUGIN_ROOT}", replacement) for key, value in env.items()}

    return ConnectionSpec(
        plugin_id=plugin_id,
        client=client,
        transport="stdio",
        command=command,
        args=tuple(args),
        cwd=cwd,
        env=env,
    )


def load_plugin_connection(
    plugin_id: str,
    *,
    client: str = "codex",
    root: Path = ROOT,
) -> ConnectionSpec:
    if plugin_id not in SMOKE_CASES:
        raise KeyError(f"no live smoke case is defined for plugin {plugin_id!r}")
    if client not in {"codex", "claude"}:
        raise ValueError(f"unsupported generated client configuration: {client!r}")

    root = Path(root).resolve()
    plugin_root = root / "plugins" / plugin_id
    if client == "codex":
        path = plugin_root / ".codex-plugin" / "mcp.json"
        with path.open("r", encoding="utf-8") as fh:
            document = json.load(fh)
        servers = document.get("mcpServers")
        if not isinstance(servers, dict) or set(servers) != {plugin_id}:
            raise ValueError(
                f"{path.relative_to(root)} must contain exactly the {plugin_id!r} MCP server"
            )
        server = servers[plugin_id]
        if not isinstance(server, Mapping) or server.get("type") != "stdio":
            raise ValueError(f"unsupported generated Codex transport for {plugin_id!r}: expected stdio")
        return _validated_stdio_connection(
            plugin_id,
            client,
            server,
            plugin_root=plugin_root,
            root=root,
            expand_claude_root=False,
        )

    path = plugin_root / ".claude-plugin" / "mcp.json"
    with path.open("r", encoding="utf-8") as fh:
        document = json.load(fh)
    if not isinstance(document, dict) or set(document) != {plugin_id}:
        raise ValueError(
            f"{path.relative_to(root)} must contain exactly the {plugin_id!r} MCP server"
        )
    server = document[plugin_id]
    if not isinstance(server, Mapping):
        raise ValueError(f"plugin {plugin_id!r} has malformed generated Claude configuration")

    transport_type = server.get("type")
    if transport_type in {None, "stdio"} and server.get("command"):
        return _validated_stdio_connection(
            plugin_id,
            client,
            server,
            plugin_root=plugin_root,
            root=root,
            expand_claude_root=True,
        )
    if transport_type == "sse":
        url = server.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise ValueError(f"plugin {plugin_id!r} has invalid generated Claude SSE URL")
        return ConnectionSpec(
            plugin_id=plugin_id,
            client=client,
            transport="sse",
            cwd=plugin_root.resolve(),
            url=url,
        )
    raise ValueError(
        f"unsupported generated Claude transport for {plugin_id!r}: {transport_type!r}"
    )


def load_plugin_launch(plugin_id: str, root: Path = ROOT) -> LaunchSpec:
    """Backward-compatible loader for the generated Codex stdio launch."""
    connection = load_plugin_connection(plugin_id, client="codex", root=root)
    assert connection.command is not None and connection.cwd is not None
    return LaunchSpec(
        plugin_id=plugin_id,
        command=connection.command,
        args=connection.args,
        cwd=connection.cwd,
        env=connection.env,
    )


def _load_live_verification_reference(
    plugin_id: str,
    root: Path = ROOT,
    *,
    client: str = "codex",
    check_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    plugins_doc = _load_yaml(Path(root) / "registry/plugins.yaml")
    checks_doc = _load_yaml(Path(root) / "registry/verification-checks.yaml")
    plugins = {item["id"]: item for item in plugins_doc["plugins"]}
    checks = {item["id"]: item for item in checks_doc["checks"]}

    plugin = plugins.get(plugin_id)
    if plugin is None:
        raise KeyError(f"plugin {plugin_id!r} is not present in registry/plugins.yaml")
    evidence = plugin["verification"]["clients"].get(client)
    if not isinstance(evidence, Mapping):
        raise ValueError(f"plugin {plugin_id!r} has no verification evidence for client {client!r}")

    live_references: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for reference in evidence.get("checks", []):
        check = checks.get(reference.get("check_id")) if isinstance(reference, Mapping) else None
        if check is not None and check.get("kind") == "live":
            live_references.append((check, dict(reference)))

    if check_id is not None:
        matches = [item for item in live_references if item[0].get("id") == check_id]
        if len(matches) != 1:
            raise ValueError(
                f"plugin {plugin_id!r} client {client!r} does not reference live check {check_id!r}"
            )
        return matches[0]

    if not live_references:
        raise ValueError(f"plugin {plugin_id!r} client {client!r} has no live verification check")
    strongest_rank = max(EVIDENCE_RANK.get(item[0].get("evidence_level"), -1) for item in live_references)
    strongest = [
        item
        for item in live_references
        if EVIDENCE_RANK.get(item[0].get("evidence_level"), -1) == strongest_rank
    ]
    if len(strongest) != 1:
        raise ValueError(
            f"plugin {plugin_id!r} client {client!r} has {len(strongest)} equally strong live checks; "
            "select one with check_id"
        )
    return strongest[0]


def _load_declared_known_issue(
    plugin_id: str,
    issue_id: str,
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    plugins_doc = _load_yaml(Path(root) / "registry/plugins.yaml")
    plugins = {item["id"]: item for item in plugins_doc["plugins"]}
    plugin = plugins.get(plugin_id)
    if plugin is None:
        raise KeyError(f"plugin {plugin_id!r} is not present in registry/plugins.yaml")
    known_issues = plugin.get("verification", {}).get("known_issues", [])
    for issue in known_issues:
        if issue.get("id") == issue_id:
            return issue
    raise ValueError(f"known issue {issue_id!r} is not declared for plugin {plugin_id!r}")


def _bind_environment_identity(
    identity: Mapping[str, Any] | None,
    *,
    label: str,
    root: Path,
) -> dict[str, Any]:
    if not isinstance(identity, Mapping):
        raise ValueError(f"{label}: missing dependency environment identity")
    bound = dict(identity)
    kind = bound.get("kind")
    if kind == "hosted":
        return bound
    if kind not in FILE_BACKED_ENVIRONMENT_KINDS:
        raise ValueError(f"{label}: unsupported dependency environment kind {kind!r}")
    relative = bound.get("path")
    expected = bound.get("sha256")
    if not isinstance(relative, str) or not relative:
        raise ValueError(f"{label}: file-backed environment requires path")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError(f"{label}: file-backed environment requires a 64-character sha256")
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"{label}: environment path must be repository-relative: {relative!r}")
    target = root / candidate
    if not target.is_file():
        raise ValueError(f"{label}: dependency environment file does not exist: {relative}")
    actual = _sha256(target)
    if actual != expected:
        raise ValueError(
            f"{label}: sha256 mismatch for {relative}: declared {expected}, actual {actual}"
        )
    bound["actual_sha256"] = actual
    return bound


def bind_live_verification_inputs(
    plugin_id: str,
    *,
    root: Path = ROOT,
    client: str = "codex",
    check_id: str | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    _check, reference = _load_live_verification_reference(
        plugin_id,
        root,
        client=client,
        check_id=check_id,
    )
    inputs = copy.deepcopy(reference["inputs"])
    inputs["environment"] = _bind_environment_identity(
        inputs.get("environment"), label=f"plugin[{plugin_id}].environment", root=root
    )
    inputs["harness_environment"] = _bind_environment_identity(
        inputs.get("harness_environment"),
        label=f"plugin[{plugin_id}].harness_environment",
        root=root,
    )
    return inputs


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


def _launch_from_connection(connection: ConnectionSpec | None) -> LaunchSpec | None:
    if connection is None or connection.transport != "stdio":
        return None
    assert connection.command is not None and connection.cwd is not None
    return LaunchSpec(
        plugin_id=connection.plugin_id,
        command=connection.command,
        args=connection.args,
        cwd=connection.cwd,
        env=connection.env,
    )


def build_trace_metadata(
    plugin_id: str,
    *,
    launch: LaunchSpec | None = None,
    connection: ConnectionSpec | None = None,
    client: str = "codex",
    check_id: str | None = None,
    env: Mapping[str, str] | None = None,
    checked_at: datetime | None = None,
    root: Path = ROOT,
    verification_inputs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    check, _reference = _load_live_verification_reference(
        plugin_id, root, client=client, check_id=check_id
    )
    bound_inputs = (
        copy.deepcopy(dict(verification_inputs))
        if verification_inputs is not None
        else bind_live_verification_inputs(plugin_id, root=root, client=client, check_id=check_id)
    )
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

    if connection is None and launch is not None:
        connection = ConnectionSpec(
            plugin_id=plugin_id,
            client=client,
            transport="stdio",
            command=launch.command,
            args=launch.args,
            cwd=launch.cwd,
            env=launch.env,
        )
    if launch is None:
        launch = _launch_from_connection(connection)

    launch_data: dict[str, Any] | None = None
    if launch is not None:
        try:
            cwd = launch.cwd.resolve().relative_to(root).as_posix()
        except ValueError:
            cwd = str(launch.cwd)
        launch_data = {
            "command": launch.command,
            "args": list(launch.args),
            "cwd": cwd,
            "env": launch.env,
        }

    generated_transport = connection.transport if connection is not None else "stdio"
    endpoint = connection.url if connection is not None and connection.transport == "sse" else None
    return {
        "check_id": check["id"],
        "checked_at": _iso_utc(when),
        "plugin": plugin_id,
        "client": check["client"],
        "client_requested": client,
        "client_execution": "generic-harness",
        "transport": check["transport"],
        "generated_transport": generated_transport,
        "endpoint": endpoint,
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
        "verification_inputs": bound_inputs,
    }


def _bounded_exception_message(error: BaseException) -> str:
    message = str(error)
    if len(message) <= MAX_EXCEPTION_MESSAGE_CHARS:
        return message
    return message[:MAX_EXCEPTION_MESSAGE_CHARS] + "…"


def _exception_detail(error: BaseException, *, depth: int = 0) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "type": type(error).__name__,
        "message": _bounded_exception_message(error),
    }
    if isinstance(error, SmokePhaseError):
        detail["phase"] = error.phase
    if depth >= MAX_EXCEPTION_DETAIL_DEPTH:
        detail["truncated"] = True
        return detail

    if isinstance(error, BaseExceptionGroup):
        children = list(error.exceptions)
        detail["exceptions"] = [
            _exception_detail(child, depth=depth + 1)
            for child in children[:MAX_EXCEPTION_GROUP_CHILDREN]
        ]
        if len(children) > MAX_EXCEPTION_GROUP_CHILDREN:
            detail["exceptions_truncated"] = len(children) - MAX_EXCEPTION_GROUP_CHILDREN

    if error.__cause__ is not None:
        detail["cause"] = _exception_detail(error.__cause__, depth=depth + 1)
    return detail


def build_error_report(
    plugin_id: str,
    error: Exception,
    *,
    launch: LaunchSpec | None = None,
    connection: ConnectionSpec | None = None,
    client: str = "codex",
    check_id: str | None = None,
    env: Mapping[str, str] | None = None,
    checked_at: datetime | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    try:
        trace = build_trace_metadata(
            plugin_id,
            launch=launch,
            connection=connection,
            client=client,
            check_id=check_id,
            env=env,
            checked_at=checked_at,
            root=root,
        )
    except Exception as trace_exc:
        trace = {"plugin": plugin_id, "trace_error": f"{type(trace_exc).__name__}: {trace_exc}"}
    return {
        **trace,
        "status": "error",
        "error": f"{type(error).__name__}: {error}",
        "error_detail": _exception_detail(error),
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
    return bool(getattr(result, "is_error", False) or getattr(result, "isError", False))


def _tool_has_payload(result: Any) -> bool:
    if getattr(result, "content", None):
        return True
    if getattr(result, "structured_content", None) is not None:
        return True
    if getattr(result, "structuredContent", None) is not None:
        return True
    return False


def _parse_json_object_text(text: str, *, plugin_id: str, tool_name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{plugin_id} live tool {tool_name!r} did not return a valid JSON object") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{plugin_id} live tool {tool_name!r} did not return a valid JSON object")
    return parsed


def _json_object_from_tool_result(result: Any, *, plugin_id: str, tool_name: str) -> dict[str, Any]:
    if _tool_failed(result):
        raise RuntimeError(f"{plugin_id} live tool {tool_name!r} returned an MCP error: {result}")
    structured = getattr(result, "structured_content", None)
    if structured is None:
        structured = getattr(result, "structuredContent", None)
    if isinstance(structured, Mapping):
        if set(structured) == {"result"}:
            wrapped = structured["result"]
            if isinstance(wrapped, Mapping):
                return dict(wrapped)
            if isinstance(wrapped, str):
                return _parse_json_object_text(wrapped, plugin_id=plugin_id, tool_name=tool_name)
            raise RuntimeError(f"{plugin_id} live tool {tool_name!r} did not return a valid JSON object")
        return dict(structured)
    text_parts = [
        item.text
        for item in getattr(result, "content", None) or []
        if isinstance(getattr(item, "text", None), str) and item.text.strip()
    ]
    if len(text_parts) != 1:
        raise RuntimeError(f"{plugin_id} live tool {tool_name!r} did not return one valid JSON object")
    return _parse_json_object_text(text_parts[0], plugin_id=plugin_id, tool_name=tool_name)


def _json_contains_exact_string(value: Any, expected: str) -> bool:
    if isinstance(value, str):
        return value == expected
    if isinstance(value, Mapping):
        return any(_json_contains_exact_string(item, expected) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_json_contains_exact_string(item, expected) for item in value)
    return False


async def run_known_issue_canary(
    session: Any,
    plugin_id: str,
    issue_id: str,
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    _load_declared_known_issue(plugin_id, issue_id, root=root)
    if plugin_id != "perseus" or issue_id != PERSEUS_ROUTING_KNOWN_ISSUE_ID:
        raise ValueError(f"no live known-issue canary is implemented for {plugin_id!r} / {issue_id!r}")

    discovery = _json_object_from_tool_result(
        await session.call_tool(
            "find_author_names",
            arguments={"query": "Euripides", "language": "greek", "limit": 20},
        ),
        plugin_id=plugin_id,
        tool_name="find_author_names",
    )
    if not _json_contains_exact_string(discovery, PERSEUS_ROUTING_TARGET_WORK):
        raise RuntimeError(
            f"{issue_id} signature changed: merged discovery no longer advertises "
            f"{PERSEUS_ROUTING_TARGET_WORK}; revise or retire the canonical known issue"
        )

    cts_resources = _json_object_from_tool_result(
        await session.call_tool(
            "get_work_resources",
            arguments={"urn_or_title": PERSEUS_ROUTING_TARGET_WORK, "language": "greek"},
        ),
        plugin_id=plugin_id,
        tool_name="get_work_resources",
    )
    scaife_metadata = _json_object_from_tool_result(
        await session.call_tool(
            "get_scaife_library_metadata",
            arguments={"urn": PERSEUS_ROUTING_TARGET_WORK},
        ),
        plugin_id=plugin_id,
        tool_name="get_scaife_library_metadata",
    )
    match_count = cts_resources.get("match_count")
    if type(match_count) is not int or match_count < 0:
        raise RuntimeError(
            f"{issue_id} signature changed: CTS get_work_resources returned invalid match_count={match_count!r}"
        )
    if not _json_contains_exact_string(scaife_metadata, PERSEUS_ROUTING_TARGET_WORK):
        raise RuntimeError(
            f"{issue_id} signature changed: Scaife metadata no longer resolves "
            f"{PERSEUS_ROUTING_TARGET_WORK}; revise the canonical known issue"
        )
    if match_count != 0:
        raise RuntimeError(
            f"{issue_id} may have been fixed: CTS get_work_resources now resolves "
            f"{PERSEUS_ROUTING_TARGET_WORK} with match_count={match_count}; "
            "retire or revise the canonical known issue and skill workaround"
        )
    return {
        "id": issue_id,
        "status": "observed",
        "target_urn": PERSEUS_ROUTING_TARGET_WORK,
        "cts_match_count": match_count,
    }


async def _exercise_session(
    session: Any,
    plugin_id: str,
    case: SmokeCase,
    *,
    startup_only: bool,
    root: Path,
) -> tuple[Any, set[str], str | None, list[dict[str, Any]]]:
    try:
        initialize_result = await session.initialize()
    except Exception as exc:
        raise SmokePhaseError("initialize", exc) from exc

    try:
        listed = await session.list_tools()
        tool_names = {tool.name for tool in listed.tools}
        missing = case.expected_tools - tool_names
        if missing:
            raise RuntimeError(
                f"{plugin_id} is missing expected MCP tools: {sorted(missing)}; available={sorted(tool_names)}"
            )
    except Exception as exc:
        raise SmokePhaseError("list_tools", exc) from exc

    if startup_only:
        return initialize_result, tool_names, None, []

    tool_name, arguments = case.tool_call
    try:
        result = await session.call_tool(tool_name, arguments=arguments)
        if _tool_failed(result):
            raise RuntimeError(f"{plugin_id} live tool {tool_name!r} returned an MCP error: {result}")
        if not _tool_has_payload(result):
            raise RuntimeError(f"{plugin_id} live tool {tool_name!r} returned no payload")
    except Exception as exc:
        raise SmokePhaseError("call_tool", exc) from exc

    known_issue_evidence: list[dict[str, Any]] = []
    for issue_id in case.known_issue_canaries:
        try:
            known_issue_evidence.append(
                await run_known_issue_canary(session, plugin_id, issue_id, root=root)
            )
        except Exception as exc:
            raise SmokePhaseError("known_issue_canary", exc) from exc
    return initialize_result, tool_names, tool_name, known_issue_evidence


async def smoke_plugin(
    plugin_id: str,
    *,
    timeout: float = 180.0,
    launch: LaunchSpec | None = None,
    connection: ConnectionSpec | None = None,
    client: str = "codex",
    check_id: str | None = None,
    startup_only: bool = False,
    root: Path = ROOT,
) -> dict[str, Any]:
    bound_inputs = bind_live_verification_inputs(
        plugin_id, root=root, client=client, check_id=check_id
    )
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as exc:
        raise RuntimeError("the live smoke harness requires MCP Python SDK v2; install mcp>=2,<3") from exc

    if connection is None:
        if launch is not None:
            connection = ConnectionSpec(
                plugin_id=plugin_id,
                client=client,
                transport="stdio",
                command=launch.command,
                args=launch.args,
                cwd=launch.cwd,
                env=launch.env,
            )
        else:
            connection = load_plugin_connection(plugin_id, client=client, root=root)
    case = SMOKE_CASES[plugin_id]

    async with asyncio.timeout(timeout):
        if connection.transport == "stdio":
            if connection.command is None or connection.cwd is None:
                raise ValueError(f"plugin {plugin_id!r} has incomplete stdio connection metadata")
            server_params = StdioServerParameters(
                command=connection.command,
                args=list(connection.args),
                env=connection.env,
            )
            with _working_directory(connection.cwd):
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        initialize_result, tool_names, tool_name, known_issue_evidence = await _exercise_session(
                            session,
                            plugin_id,
                            case,
                            startup_only=startup_only,
                            root=Path(root),
                        )
        elif connection.transport == "sse":
            if not connection.url:
                raise ValueError(f"plugin {plugin_id!r} has incomplete SSE connection metadata")
            try:
                from mcp.client.sse import sse_client
            except ImportError as exc:
                raise RuntimeError("the live smoke harness requires MCP SDK legacy SSE client support") from exc
            async with sse_client(connection.url) as (read, write):
                async with ClientSession(read, write) as session:
                    initialize_result, tool_names, tool_name, known_issue_evidence = await _exercise_session(
                        session,
                        plugin_id,
                        case,
                        startup_only=startup_only,
                        root=Path(root),
                    )
        else:
            raise ValueError(f"unsupported smoke transport: {connection.transport!r}")

    return {
        **build_trace_metadata(
            plugin_id,
            connection=connection,
            client=client,
            check_id=check_id,
            root=root,
            verification_inputs=bound_inputs,
        ),
        "server_name": getattr(initialize_result, "serverInfo", None)
        or getattr(initialize_result, "server_info", None),
        "tool_count": len(tool_names),
        "expected_tools": sorted(case.expected_tools),
        "called_tool": tool_name,
        "startup_only": startup_only,
        "known_issue_canaries": known_issue_evidence,
        "status": "ok",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Exercise one Agora plugin through generated Claude or Codex MCP configuration, "
            "using the generic MCP harness."
        )
    )
    parser.add_argument("plugin", choices=sorted(SMOKE_CASES))
    parser.add_argument("--client", choices=("codex", "claude"), default="codex")
    parser.add_argument("--check-id", help="Exact canonical live verification check to bind")
    parser.add_argument(
        "--startup-only",
        action="store_true",
        help="Initialize MCP and enumerate tools without executing the representative provider operation",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Maximum seconds for startup, MCP handshake, and requested smoke operations",
    )
    args = parser.parse_args()

    connection: ConnectionSpec | None = None
    try:
        connection = load_plugin_connection(args.plugin, client=args.client)
        report = asyncio.run(
            smoke_plugin(
                args.plugin,
                timeout=args.timeout,
                connection=connection,
                client=args.client,
                check_id=args.check_id,
                startup_only=args.startup_only,
            )
        )
    except Exception as exc:
        report = build_error_report(
            args.plugin,
            exc,
            connection=connection,
            client=args.client,
            check_id=args.check_id,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 1

    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())