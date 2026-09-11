# Research: Perseus generated stdio initialization failure (#159)

## Release impact

#159 blocks the #150 Agora 1.0 clean-install matrix. In workflow run `34619305547`, both generated Perseus stdio paths failed while Context-Fabric, Sefaria, and SEDRA passed in the same generic MCP harness. The failure therefore cannot be treated as a general runner or harness outage.

## Preserved observations

- Codex failing job: `103328993859`; Claude failed in the same run.
- Runner: Ubuntu 24.04, Python 3.13.15, uv 0.12.10.
- Generated launch resolves `perseus-mcp==1.0.2` through `plugins/perseus/runtime-constraints.txt`.
- The constraint file pins the relevant environment, including `fastmcp==4.0.3`, `mcp==2.1.1`, `httpx==0.28.1`, and `perseus-mcp==1.0.2`; the live check verifies the file hash before launch.
- FastMCP reaches `Starting MCP server 'perseus' with transport 'stdio'` before the harness exits.
- The current error report records only `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`, discarding the nested exception that distinguishes server termination, protocol/handshake failure, transport failure, and client-side cancellation.
- `scripts/smoke_mcp_plugin.py` performs `stdio_client` → `ClientSession` → `session.initialize()` → `list_tools()`, but does not record the phase that failed.
- Upstream `perseus-mcp` v1.0.2 declares Python >=3.11 (including a Python 3.13 classifier), depends on `fastmcp>=2.12.0`, `httpx>=0.27.0`, and `defusedxml>=0.7.1`, and its entry point is simply `FastMCP("perseus").run()`.

## Current hypothesis ranking

1. **Server/client runtime interaction** between the pinned FastMCP 4.0.3 server and MCP Python client 2.1.1 is plausible because failure happens around stdio session initialization and both generated host configurations reproduce it.
2. **Perseus server startup/background-task failure** is also plausible; the lost nested exception prevents distinguishing it from client-side protocol failure.
3. **Mutable dependency drift** is weaker than initially suspected because Agora pins the resolved Perseus runtime dependency set and verifies the constraint hash.
4. **Generated Claude-vs-Codex configuration error** is weak because both generated paths fail with the same package/runtime and other generated stdio plugins pass.
5. Provider HTTP/CTS/Scaife semantics are not implicated yet: failure occurs before representative tool execution.

## Ownership boundary

The first Agora-owned defect is diagnostic: the release smoke drops the only actionable nested error and cannot state whether `initialize`, `list_tools`, or a later operation failed. Improving this evidence does not patch Perseus semantics or mask instability.

A runtime/package pin may be changed only after the improved evidence identifies a specific incompatible component. Retries are not an acceptable diagnosis or release fix.

## Decision

Implement one diagnostic slice first: preserve nested exception structure in the smoke report and identify the MCP phase that fails. Re-run both generated Perseus paths with the exact pinned environment. Only then choose among an Agora launch/runtime fix, an upstream/runtime compatibility disposition, or a truthful support downgrade.
