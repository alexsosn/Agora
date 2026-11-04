#!/usr/bin/env python3
"""Bounded startup smoke for the nabu plugin's user-local launch.

Runs ONLY on a machine that has a Nabu checkout (a user-local environment —
Agora's CI has none, and the generic live harness refuses user-local kinds by
design). It proves exactly what the generated manifests claim and nothing
more:

1. `${NABU_HOME}` expansion — the launch is read from the GENERATED
   plugins/nabu/.claude-plugin/mcp.json and every `${VAR}` in its args/env is
   expanded from the operator's environment, the same substitution the
   clients perform;
2. Bundler from a foreign working directory — the server is spawned from a
   temporary directory, so only the expanded BUNDLE_GEMFILE makes the gem
   environment resolve;
3. MCP startup — initialize, the initialized notification, tools/list, and
   ONE bounded tools/call of `nabu_status`, each under a hard timeout;
4. the error path — run with NABU_HOME unset, it refuses immediately with an
   explanation instead of launching anything.

Exit 0 and a transcript summary on success; exit 1 with the failing step
otherwise. The tool call is read-only against the operator's own library.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "plugins/nabu/.claude-plugin/mcp.json"
PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
STARTUP_TIMEOUT = 90.0
CALL_TIMEOUT = 30.0


def _expand(value: str, environment: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in environment:
            raise KeyError(name)
        return environment[name]

    return PLACEHOLDER.sub(replace, value)


class Server:
    def __init__(self, process: subprocess.Popen) -> None:
        self.process = process
        self.next_id = 0

    def request(self, method: str, params: dict | None, *, timeout: float) -> dict:
        self.next_id += 1
        message: dict = {"jsonrpc": "2.0", "id": self.next_id, "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"{method}: no response within {timeout:.0f}s")
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError(f"{method}: server closed stdout (exit {self.process.poll()})")
            try:
                received = json.loads(line)
            except json.JSONDecodeError:
                continue  # not a JSON-RPC line (a stray log line); keep reading
            if received.get("id") == self.next_id:
                if "error" in received:
                    raise RuntimeError(f"{method}: server error {received['error']}")
                return received["result"]

    def notify(self, method: str) -> None:
        self._send({"jsonrpc": "2.0", "method": method})

    def _send(self, message: dict) -> None:
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()


def main() -> int:
    if not os.environ.get("NABU_HOME"):
        print(
            "smoke refused before launching anything: NABU_HOME is not set. "
            "The nabu plugin is a user-local runtime — point NABU_HOME at your "
            "own Nabu checkout (see plugins/nabu/README.md) and re-run.",
            file=sys.stderr,
        )
        return 1

    with MANIFEST.open("r", encoding="utf-8") as fh:
        launch = json.load(fh)["nabu"]

    environment = dict(os.environ)
    try:
        command = [_expand(launch["command"], environment)]
        command += [_expand(argument, environment) for argument in launch.get("args", [])]
        env = dict(environment)
        for key, value in (launch.get("env") or {}).items():
            env[key] = _expand(value, environment)
    except KeyError as missing:
        print(f"smoke failed: launch references unset variable ${{{missing.args[0]}}}", file=sys.stderr)
        return 1

    steps: list[str] = [f"launch: {' '.join(command)}"]
    with tempfile.TemporaryDirectory() as foreign_cwd:
        steps.append(f"cwd: {foreign_cwd} (foreign — not the checkout)")
        process = subprocess.Popen(
            command,
            cwd=foreign_cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        server = Server(process)
        try:
            result = server.request(
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "agora-user-local-smoke", "version": "0"},
                },
                timeout=STARTUP_TIMEOUT,
            )
            info = result.get("serverInfo", {})
            steps.append(
                f"initialize: ok — server {info.get('name')!r} {info.get('version')!r}, "
                f"protocol {result.get('protocolVersion')!r}"
            )
            server.notify("notifications/initialized")

            tools = server.request("tools/list", {}, timeout=CALL_TIMEOUT)
            names = sorted(tool["name"] for tool in tools.get("tools", []))
            if "nabu_status" not in names:
                raise RuntimeError(f"tools/list: nabu_status missing from {names}")
            steps.append(f"tools/list: {len(names)} tools ({', '.join(names[:6])}, …)")

            called = server.request(
                "tools/call",
                {"name": "nabu_status", "arguments": {}},
                timeout=CALL_TIMEOUT,
            )
            content = called.get("content") or []
            if not content:
                raise RuntimeError("tools/call nabu_status: empty content")
            first = content[0].get("text", "")[:160].replace("\n", " ")
            steps.append(f"nabu_status: ok — {first!r}")
        except Exception as failure:  # noqa: BLE001 — one bounded report path
            print(f"smoke failed: {failure}", file=sys.stderr)
            stderr_tail = ""
            if process.poll() is not None and process.stderr is not None:
                stderr_tail = process.stderr.read()[-800:]
            if stderr_tail:
                print(f"server stderr tail:\n{stderr_tail}", file=sys.stderr)
            process.kill()
            return 1
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()

    print("nabu user-local startup smoke passed:")
    for step in steps:
        print(f"- {step}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
