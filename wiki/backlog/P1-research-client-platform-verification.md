# Research: client and platform verification coverage (#18)

## Question

Which parts of #18 remain true on current `main`, which have already been implemented, and what is the smallest evidence model/CI expansion that makes Agora's client/platform support claims honest without creating an exhaustive and expensive matrix?

Audited against `main` at `88611d430693695993ff30c4597e1344299aec0a`.

## Current state

### Already implemented since #18 was filed

The issue's original statement that Agora has no Windows/macOS integration coverage is no longer accurate.

- Foundation now runs Context-Fabric cache lifecycle regressions on `ubuntu-latest`, `macos-latest`, and `windows-latest`.
- Foundation also runs materializer installation-lock and migration regressions on all three operating systems.
- `external-mcp-smoke.yml` still runs the four real plugin lookups on Ubuntu, but it also has a dedicated `macos-15-intel` packaged Context-Fabric MCP smoke with a locked environment and uploaded artifact.
- Tests explicitly protect that Intel-macOS lane and its dependency-trigger coverage.
- README verification wording is already conservative: aggregate plugin status remains `community`; current live `verified` evidence is scoped to Codex paths; Claude paths remain deterministic/community.

These changes materially satisfy the filesystem-lock/path/subprocess part of #18 for Context-Fabric and materializer installation. The ticket should not reimplement them.

### Remaining gaps

1. **No explicit compatibility/evidence matrix.** Installation docs say Agora targets Claude Code and ChatGPT/Codex but do not give a compact client × transport × OS × evidence table. A reader cannot tell which combinations have live client evidence, generated-transport evidence, deterministic manifest coverage, or no exercised path.
2. **Local runtime startup coverage is asymmetric.** Context-Fabric has an Intel-macOS packaged smoke, but SEDRA has no Windows/macOS packaged startup lane. The all-OS Foundation jobs exercise cache/install locking, not the actual Agora-owned MCP server startup path.
3. **Windows packaged MCP startup is absent.** No current workflow starts an Agora-owned MCP runtime through generated launch metadata on Windows.
4. **Claude is not exercised as a client.** The repository can deterministically validate generated Claude metadata, but CI has no authenticated Claude Code runtime. Claiming live Claude-client verification would therefore be unjustified.
5. **The strongest reproducible generated-Claude transport paths are not exercised.** Three current Claude configurations (`context-fabric`, `perseus`, `sedra`) are generated stdio launch commands, while Sefaria is a generated direct `type: sse` URL. A generic MCP harness can exercise those generated transports directly—resolving `${CLAUDE_PLUGIN_ROOT}` for stdio and connecting to the generated Sefaria SSE URL—without pretending Claude Code itself was tested.
6. **Platform evidence is not represented canonically.** `registry/verification-checks.yaml` records plugin/client/transport/check executors, but the existing Intel-macOS job is not a referenced verification check and platform is only implicit in workflow YAML. A platform-specific failure can therefore exist outside the traceable evidence graph.

## Existing primitives to reuse

- `scripts/smoke_mcp_plugin.py` already starts generated Codex configurations with the committed locked smoke harness and records trace evidence.
- Generated Claude artifacts are concrete `plugins/<id>/.claude-plugin/mcp.json` files. They are not all stdio: Sefaria's current file is direct SSE, so the harness extension must be transport-aware rather than command-only.
- `registry/verification-checks.yaml` already provides stable check IDs and executable workflow bindings; platform work should extend/reuse that model rather than create a second verification registry.
- `registry/plugins.yaml` already separates aggregate and per-client status. New platform checks must not promote aggregate status or Claude status automatically.
- `tests/test_live_smoke_runtime_environment.py` already asserts workflow/runtime-environment guarantees.
- Foundation's three-OS jobs prove the repository can sustain bounded Linux/macOS/Windows matrices.

## Recommended scope

### A. Compatibility/evidence matrix

Add `wiki/guides/compatibility.md` with one concise table covering current v0.1 clients/transports and the three major OS families. Each cell must distinguish at least:

- **live client path** — actual client/transport path exercised;
- **generated transport path** — generated client configuration exercised through the generic MCP harness, but not the named client executable;
- **deterministic only** — manifest/schema/path contract only;
- **not exercised / not claimed**.

The matrix should link stable verification check IDs or workflow evidence rather than make unsupported prose claims. README and installation docs should link it.

### B. Cross-platform packaged startup for Agora-owned local runtimes

Add a bounded GitHub Actions matrix for `context-fabric` and `sedra` on Linux, macOS, and Windows that:

- uses generated plugin launch metadata rather than a hand-written replacement command;
- starts the MCP server and completes MCP initialization/tool enumeration;
- does not require a real corpus download or broad network sweep;
- keeps the existing Ubuntu real-operation live smoke as the stronger client-path evidence;
- records per-plugin/per-OS artifacts so a platform failure is attributable.

Running two local runtimes across three OSes is six small startup checks, not a four-plugin × two-client × three-OS Cartesian product.

### C. Strongest reproducible Claude-path substitute

Extend the smoke harness to load generated Claude MCP metadata as well as Codex metadata. On Ubuntu, exercise all four v0.1 generated Claude transport paths through the generic MCP client/harness:

- stdio for Context-Fabric, Perseus, and SEDRA;
- direct SSE for Sefaria, using the URL present in the generated Claude configuration rather than the Codex stdio proxy path.

This must remain `community` evidence because it does **not** execute Claude Code itself. The compatibility guide must say exactly that.

If a future authenticated/noninteractive Claude CI mechanism becomes available, it can replace or supplement this substitute without changing the evidence taxonomy.

### D. Trace platform evidence through the existing verification-check model

Do not infer platform support from check-ID names. Extend the canonical verification-check schema minimally so a check can carry explicit structured platform/environment identity with OS and architecture kept separate.

Then register the packaged-startup checks and reference the relevant stable IDs from client evidence where appropriate. A platform check may strengthen confidence without changing the client's canonical status.

The validator must reject a platform check whose declared workflow/job/matrix selector cannot execute the declared platform, and the workflow must assert the actual runtime OS/architecture before launching the server.

## Non-goals

- Do not claim every plugin/client combination is supported on every OS.
- Do not turn third-party Perseus or hosted Sefaria behavior into Agora-owned cross-platform obligations.
- Do not promote Claude to `verified` without an actual Claude-client execution mechanism.
- Do not silently translate Sefaria's Claude direct-SSE path into the Codex stdio proxy path.
- Do not run real network lookups in every OS cell; startup/initialization is sufficient for path/subprocess/packaging differences.
- Do not duplicate the existing Context-Fabric cache and materializer lock matrices.
- Do not create a separate status vocabulary for the compatibility guide.

## Risks to test adversarially

- A generic Claude-path harness is mislabeled as actual Claude-client verification.
- Sefaria's Claude SSE configuration is accidentally replaced by the Codex proxy path during testing.
- Platform support is inferred from a workflow runner but not bound to stable evidence.
- Windows command/path quoting works in unit tests but generated launch execution is never attempted.
- The matrix quietly explodes into expensive live-network jobs.
- One successful platform check promotes aggregate plugin/client status.
- Compatibility prose becomes stale when checks move or disappear.
- A platform declaration names an OS/architecture different from the workflow executor that actually runs the check.

## Research conclusion

#18 remains actionable but is substantially narrower than filed. Agora already has meaningful cross-platform lock/cache coverage and one Intel-macOS packaged Context-Fabric smoke. The remaining trustworthy increment is a bounded compatibility/evidence matrix, six cross-OS packaged-startup checks for the two Agora-owned local MCP runtimes, transport-aware generic-harness evidence for all four generated Claude configurations that remains explicitly non-Claude-client evidence, and explicit platform identity in the existing verification-check graph.