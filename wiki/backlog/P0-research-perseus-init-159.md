# Research: Perseus generated stdio initialization failure (#159)

## Release impact

#159 blocks the #150 Agora 1.0 clean-install matrix. In workflow run `34619305547`, both generated Perseus stdio paths failed while Context-Fabric, Sefaria, and SEDRA passed in the same generic MCP harness. The failure therefore cannot be treated as a general runner or harness outage.

## Preserved observations

- Codex failing job: `103328993859`; Claude failed in the same run.
- Runner: Ubuntu 24.04, Python 3.13.15, uv 0.12.10.
- Generated launch resolves `perseus-mcp==1.0.2` through `plugins/perseus/runtime-constraints.txt`.
- The constraint file pins the relevant environment, including `fastmcp==4.0.3`, `mcp==2.1.1`, `httpx==0.28.1`, and `perseus-mcp==1.0.2`; the live check verifies the file hash before launch.
- FastMCP reaches `Starting MCP server 'perseus' with transport 'stdio'` before the harness exits.
- The original error report recorded only `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`, discarding the nested exception that distinguishes server termination, protocol/handshake failure, transport failure, and client-side cancellation.
- `scripts/smoke_mcp_plugin.py` performs `stdio_client` → `ClientSession` → `session.initialize()` → `list_tools()` → representative tool call → optional known-issue canaries.
- Upstream `perseus-mcp` v1.0.2 declares Python >=3.11 (including a Python 3.13 classifier), depends on `fastmcp>=2.12.0`, `httpx>=0.27.0`, and `defusedxml>=0.7.1`, and its entry point is simply `FastMCP("perseus").run()`.

## Diagnostic rerun result — 2026-09-11

The diagnostic GREEN was copied unchanged into the #150 release branch solely to expose the live nested cause. Exact run `34628176807` at Agora revision `203e683227f0ea270991527c81269cf4381e7919` changes the diagnosis materially:

- both generated Perseus paths start FastMCP successfully;
- MCP initialization succeeds;
- tool enumeration succeeds;
- the representative Perseus operation succeeds;
- failures occur only in the **advisory known-issue retirement canary** after the representative operation.

The two clients observed different canary outcomes against the same pinned environment:

- Claude: merged `find_author_names` discovery no longer advertised the canary target `urn:cts:greekLit:tlg0006.tlg020`, so the old canary signature could not be reproduced.
- Codex: discovery and the CTS-oriented step progressed, but `get_scaife_library_metadata` failed with an upstream/provider `httpx.ReadError` surfaced by FastMCP as an MCP tool error.

This falsifies the earlier runtime/handshake hypothesis. There is no evidence justifying a FastMCP, MCP SDK, Python, or `perseus-mcp` pin change. The release failure is caused by Agora coupling a volatile advisory-retirement probe to the same pass/fail result as the supported-client first-success smoke.

Upstream current documentation still describes `find_author_names` as merged CTS/Scaife discovery and the CTS-oriented resource helpers separately, so the documented semantic boundary remains relevant. The live evidence only says the single old canary specimen is not currently a stable mandatory success condition.

## Ownership boundary

The first Agora-owned defect was diagnostic: the release smoke dropped the actionable nested error and could not state which phase failed. The diagnostic slice fixes that without patching Perseus semantics.

The second Agora-owned defect is verification coupling. A known-issue **retirement canary** should fail closed only when it positively demonstrates that the documented issue has been fixed and therefore the advisory must be reviewed. Provider/read failures or a changed specimen signature are insufficient evidence either that the plugin path is broken or that the advisory is obsolete.

Retries and local rewrites of Perseus behavior remain out of scope.

## Decision

1. Keep the diagnostic surface.
2. Make the Perseus advisory canary conservative:
   - positive evidence that CTS now resolves the previously mismatched target still raises and forces advisory review;
   - provider-operation failures or changed canary signatures return structured `inconclusive` evidence instead of failing the client path;
   - tools required by the documented workaround remain part of tool-discovery expectations, so removal of the capability itself still fails verification.
3. Re-run both exact generated client paths. They must complete the representative smoke while preserving any `inconclusive` canary evidence in the report.
4. Do not change runtime pins unless later evidence independently requires it.
