# Research: Context-Fabric Intel macOS MCP discovery regression

Issue: #20

## Problem statement

Issue #20 reported that the Context-Fabric plugin loaded its skills in Codex on Intel macOS but exposed no MCP tools. The original failure occurred before MCP discovery: the packaged `uv run ... agora-context-fabric-mcp` launch attempted to resolve/build `cryptography==50.0.1`, for which no compatible Intel macOS wheel was selected, and the Rust source build did not complete inside the discovery window.

This research re-evaluates that report against current `main` rather than assuming the August 2026 diagnosis is still current.

## What has already been fixed

### PR #35: Intel macOS dependency compatibility

Merged PR #35 added an Agora-owned environment marker to local Python plugins:

```toml
'cryptography<43; platform_system == "Darwin" and platform_machine == "x86_64"'
```

The PR manually verified that the exact Context-Fabric launch command started successfully on Intel macOS without a Rust source build. This addresses the concrete dependency-resolution failure reported in #20.

### PR #59: reproducible runtime resolution

Merged PR #59 added committed `uv.lock` files for Agora-owned local runtimes and changed the packaged Context-Fabric launch to:

```text
uv run --locked --project . agora-context-fabric-mcp --plugin-root .
```

The dependency environment is now fail-closed against lock drift, and the live MCP harness binds verification evidence to the committed dependency snapshots.

### Current packaged command

`plugins/context-fabric/.codex-plugin/mcp.json` on current `main` contains exactly one stdio server and launches with `uv run --locked`. `scripts/smoke_mcp_plugin.py` reads that packaged file, starts the declared command, performs MCP initialization, enumerates tools, asserts the expected Context-Fabric tool subset, and runs `list_available_corpora`.

Therefore the remaining risk is not missing tool registration or use of a synthetic launch command.

## Remaining verification gap

`.github/workflows/external-mcp-smoke.yml` currently runs all four live MCP checks only on `ubuntu-24.04` / Python 3.13.

That means the exact packaged Context-Fabric launch is continuously exercised, but not on the architecture that produced #20.

GitHub's current hosted-runner documentation distinguishes these standard macOS labels:

- Intel: `macos-15-intel`, `macos-26-intel`
- ARM64: `macos-latest`, `macos-14`, `macos-15`, `macos-26`

Sources:

- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job

A job on `macos-latest` would therefore not reproduce the original x86_64 dependency/wheel-selection risk.

## Scope boundary

Agora owns the launch metadata, its locked dependency environment, and integration verification. It should verify that the packaged command can start and expose tools on a supported runner.

This ticket should not:

- fork or patch `cfabric-mcp`, MCP SDK, PyJWT, or `cryptography` behavior;
- add fallback tool implementations inside Agora;
- broaden into every client/platform combination covered by #18;
- duplicate the dependency-locking machinery already merged in #59.

## Proposed remaining contract for #20

The current issue can be considered fixed when CI proves, from a clean GitHub-hosted Intel macOS runner, that the exact packaged Codex Context-Fabric command:

1. resolves only the committed locked environment;
2. starts within the existing bounded live-smoke timeout;
3. completes MCP initialization;
4. exposes the expected Context-Fabric tool set;
5. executes the representative `list_available_corpora` call;
6. records the runner OS/architecture and the same dependency identity evidence already emitted on Linux.

The Linux live check should remain because it covers the ordinary deployment path; Intel macOS is an additional regression lane for Context-Fabric, not a replacement.

## CI design considerations

Running all remote integrations on Intel macOS would add cost while not addressing #20 directly. Sefaria is hosted, and #20 is specifically a local Context-Fabric cold-start failure. A focused Context-Fabric Intel-macOS job is therefore preferable to multiplying the whole `plugin: [context-fabric, perseus, sefaria, sedra]` matrix.

The job should invoke the same `scripts/smoke_mcp_plugin.py context-fabric` harness and the same locked verification project as the existing Linux live smoke. A separate implementation of MCP probing would weaken the evidence by creating two subtly different launch paths.

The workflow must also assert the runner architecture (`platform.machine()` / `uname -m`) is x86_64 so a future runner-label change cannot silently turn this into ARM-only evidence.

## TDD target

Before changing the workflow, add a workflow-contract regression that fails on current `main` because there is no Intel-macOS Context-Fabric live job. The regression should require:

- `macos-15-intel` or another explicit GitHub-documented Intel label;
- Context-Fabric-only scope;
- the locked verification harness;
- invocation of `scripts/smoke_mcp_plugin.py context-fabric`;
- an explicit x86_64 architecture assertion;
- triggers covering Context-Fabric packaged launch metadata, lock/project files, harness files, and the workflow itself.

Only after that RED is recorded should the workflow be changed.

## Relationship to #18

Issue #18 asks for a broader client/platform verification matrix. Closing #20 should provide one concrete Intel-macOS Codex lane and can be cited by #18, but should not close #18: Claude live verification, Windows integration coverage, ARM macOS coverage, and the broader support matrix remain separate work.
