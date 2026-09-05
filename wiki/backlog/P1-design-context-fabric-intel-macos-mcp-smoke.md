# Design: Context-Fabric Intel macOS packaged MCP verification

Issue: #20
Research: `P1-research-context-fabric-intel-macos-mcp-smoke.md`

## Goal

Add one bounded CI lane that continuously proves the packaged Context-Fabric Codex stdio launch works on Intel macOS, the architecture that originally reproduced #20.

## Acceptance contract

A pull request that changes the relevant Context-Fabric launch/runtime/harness inputs must run a job which:

1. uses an explicit GitHub-hosted Intel macOS runner label (`macos-15-intel`);
2. proves at runtime that `platform.machine()` is `x86_64` (accepting the conventional `AMD64` spelling if GitHub ever reports it that way is unnecessary for macOS today; fail closed instead);
3. installs the repository-pinned uv version `0.12.10`;
4. invokes the existing locked verification environment;
5. calls `scripts/smoke_mcp_plugin.py context-fabric --timeout 180`;
6. therefore reads `plugins/context-fabric/.codex-plugin/mcp.json`, starts its exact command, initializes MCP, verifies the expected tools, and executes the representative live call;
7. uploads its evidence artifact even on failure.

The existing Ubuntu four-plugin live matrix remains unchanged.

## Why a separate job

The existing matrix models plugin identity, not platform identity. Expanding it to a plugin × platform product would run remote Sefaria and unrelated local integrations on Intel macOS without improving #20 evidence.

A separate `context-fabric-intel-macos` job keeps the regression lane narrow and makes its purpose legible in GitHub checks.

## Workflow shape

Add to `.github/workflows/external-mcp-smoke.yml`:

```yaml
context-fabric-intel-macos:
  name: Live MCP — context-fabric (Intel macOS)
  runs-on: macos-15-intel
  timeout-minutes: 10
```

Steps:

1. checkout Agora;
2. setup Python 3.13;
3. setup uv 0.12.10;
4. assert `platform.system() == "Darwin"` and `platform.machine() == "x86_64"`;
5. execute:

```bash
uv run --project verification/mcp-smoke --locked \
  python scripts/smoke_mcp_plugin.py context-fabric --timeout 180 \
  | tee mcp-smoke-context-fabric-intel-macos.json
```

6. upload `mcp-smoke-context-fabric-intel-macos.json` with `if: always()`.

No new smoke implementation is introduced.

## Trigger contract

The existing workflow path filters already include the important inputs:

- `plugins/context-fabric/.codex-plugin/mcp.json`
- `plugins/context-fabric/pyproject.toml`
- `plugins/context-fabric/uv.lock`
- `plugins/context-fabric/src/**`
- `verification/mcp-smoke/pyproject.toml`
- `verification/mcp-smoke/uv.lock`
- `scripts/generate_marketplaces.py`
- `scripts/smoke_mcp_plugin.py`
- relevant smoke/evidence tests
- `.github/workflows/external-mcp-smoke.yml`

The TDD regression will freeze the critical subset so future path-filter edits cannot silently detach the Intel lane from the files that define its launch environment.

## RED

Extend `tests/test_live_smoke_runtime_environment.py` with a focused workflow-contract test requiring:

- the named Intel-macOS job;
- `runs-on: macos-15-intel`;
- a fail-closed x86_64 architecture assertion;
- the locked verification harness command;
- `smoke_mcp_plugin.py context-fabric --timeout 180`;
- an always-uploaded Intel-specific artifact;
- the relevant Context-Fabric packaged-command, lock, and harness trigger paths.

On the current workflow this test must fail only because the Intel job is absent.

## GREEN

Add the smallest workflow-only implementation satisfying the RED. Do not alter Python runtime dependencies, the packaged MCP command, or the smoke harness unless the RED exposes a real incompatibility when GitHub runs the new lane.

If the Intel job fails because the existing locked environment still cannot start, that is new evidence and must enter a new RED → implementation cycle rather than weakening the job.

## Verification

Before review:

- focused workflow-contract test passes;
- full Foundation suite passes;
- Ubuntu live MCP matrix remains green;
- new Intel Context-Fabric live job is green on the exact head;
- dependency snapshot freshness remains green;
- generated marketplace/catalog checks remain fresh.

## Independent review questions

The reviewer should verify independently that:

- the job really uses an Intel runner rather than `macos-latest`;
- the architecture assertion cannot silently pass on ARM;
- the job exercises the packaged `.codex-plugin/mcp.json` through the existing harness;
- no upstream behavior has been patched or copied into Agora;
- the path filters are sufficient to retrigger the evidence when the launch/runtime contract changes;
- #20 can be closed without incorrectly claiming the broader #18 support matrix is complete.
