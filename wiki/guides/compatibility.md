# Client and platform compatibility evidence

Agora records compatibility as executable evidence, not as a blanket claim that every plugin works through every client on every operating system. The canonical check definitions are in `registry/verification-checks.yaml`; current workflow runs and their JSON artifacts are the mutable observations.

## What the evidence means

There are three materially different levels of evidence in this repository:

- **Representative-operation path evidence** drives the exact generated client MCP configuration through Agora's generic MCP harness, initializes MCP, enumerates the expected tools, and executes one bounded representative operation. The current harness does **not** launch the Claude Code or Codex application executable itself; it verifies the generated client configuration and transport path that those clients consume.
- **Startup-only platform evidence** drives an Agora-owned local runtime through generated launch metadata, initializes MCP, and enumerates tools, but deliberately skips corpus acquisition and remote scholarly-service calls. These checks are live runtime observations at `community` evidence strength, not substitutes for representative-operation evidence.
- **Deterministic evidence** validates generated manifest/configuration shape without starting the runtime. A deterministic check alone cannot justify `verified` client status.

A check with `kind: live` means GitHub Actions observed runtime behavior. It does not by itself mean the named client application binary ran, and it does not automatically imply `evidence_level: verified`.

## Generated client paths

| Plugin | Claude generated path | Codex generated path | Current canonical evidence |
|---|---|---|---|
| Context-Fabric | stdio | stdio | Claude `manifest/context-fabric-claude` + `mcp-live/context-fabric-claude`; Codex `mcp-live/context-fabric-codex` |
| Perseus | stdio | stdio | Claude `manifest/perseus-claude` + `mcp-live/perseus-claude`; Codex `mcp-live/perseus-codex` |
| Sefaria | **direct SSE** | **stdio-via-SSE-proxy** | Claude `manifest/sefaria-claude` + `mcp-live/sefaria-claude`; Codex `mcp-live/sefaria-codex` |
| SEDRA | stdio | stdio | Claude `manifest/sedra-claude` + `mcp-live/sedra-claude`; Codex `mcp-live/sedra-codex` |

The Claude Sefaria check connects to the generated direct SSE endpoint. It does not silently substitute the Codex `stdio-via-sse-proxy` bridge. Conversely, the Codex check exercises its generated proxy path.

The four newly added Claude live checks initially remain `community` evidence until their exact implementation-head workflow observations succeed. Canonical status is promoted only after that evidence exists; the check definition itself is not proof of a successful run.

## Agora-owned local runtime platform startup

Cross-platform startup evidence is intentionally bounded to the two local runtimes whose process/packaging behavior Agora owns directly. It does not turn third-party Perseus or hosted Sefaria into Agora-owned cross-platform runtime obligations.

| Runtime | Linux x86_64 | macOS Intel x86_64 | Windows x86_64 |
|---|---|---|---|
| Context-Fabric | `platform-startup/context-fabric-linux-x86-64` | `platform-startup/context-fabric-macos-x86-64` | `platform-startup/context-fabric-windows-x86-64` |
| SEDRA | `platform-startup/sedra-linux-x86-64` | `platform-startup/sedra-macos-x86-64` | `platform-startup/sedra-windows-x86-64` |

Each platform check carries canonical `platform.os` and `platform.arch` metadata, binds to one exact workflow matrix cell, and the workflow separately asserts `platform.system()` and `platform.machine()` before launch. The macOS evidence is specifically **Intel x86_64**; this table does not claim Apple Silicon coverage.

These platform checks use generated Codex stdio launch metadata only as the packaging/startup vehicle. They are not additional claims that the Codex application itself was executed on those operating systems.

## Reading the matrix safely

A green historical workflow run is evidence about that exact Agora revision and dependency snapshot, not a permanent uptime or compatibility guarantee. A provider may later be unavailable, an upstream service may change, or a platform dependency may stop resolving. Consult the current check definition and the latest relevant workflow artifact when current state matters.

Plugin/client integration evidence also remains separate from provider/service health and from resource/data quality. Successful launch or representative lookup does not certify scholarly suitability of a corpus, edition, annotation layer, or remote dataset.
