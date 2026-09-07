# Research: client and platform verification coverage (#18)

## Question

Which parts of #18 remain true on current `main`, which have already been implemented, and what is the smallest evidence/CI expansion that makes Agora's client/platform claims honest without an exhaustive matrix?

Audited against `main` at `88611d430693695993ff30c4597e1344299aec0a`.

## Current state

### Already implemented since #18 was filed

The original issue is materially stale in several places:

- Context-Fabric cache lifecycle regressions already run on Linux, macOS, and Windows.
- Materializer installation-lock/migration regressions already run on all three OS families.
- The external live-smoke workflow exercises all four generated Codex MCP configurations on Ubuntu and performs one representative operation per plugin.
- Context-Fabric also has a dedicated Intel-macOS packaged smoke using the locked harness.
- README already scopes current evidence conservatively: Codex paths are live-verified while Claude remains deterministic/community.

The ticket should not reimplement these existing cross-platform lock/cache guarantees.

### Remaining gaps

1. **No explicit compatibility/evidence matrix.** Installation docs do not show which client/configuration/OS combinations have verified representative-operation evidence, startup-only evidence, deterministic evidence, or no exercised path.
2. **Local runtime startup coverage is asymmetric.** SEDRA has no Windows/macOS packaged startup lane; Windows has no packaged startup lane for either Agora-owned local MCP runtime.
3. **Generated Claude configurations are not live-exercised.** Context-Fabric, Perseus, and SEDRA generate stdio Claude configurations; Sefaria generates direct SSE. Those exact configurations are only deterministically tested today.
4. **Platform evidence is not canonical.** The Intel-macOS job is workflow evidence but not a stable verification check with explicit OS/architecture identity.

## Critical verification-semantics finding

Current `verified` Codex evidence is already produced by `scripts/smoke_mcp_plugin.py`, a generic MCP harness. It loads `.codex-plugin/mcp.json`, initializes MCP, enumerates tools, and performs the representative operation; it does **not** launch the Codex application binary.

Therefore #18 should not require a Claude application binary merely because Claude is a different client. The fair current standard is **generated client configuration/transport path verification**:

- exercise that client's exact generated MCP configuration;
- do not substitute another client's transport;
- perform the same bounded initialization/tool/representative-operation contract;
- trace the exact launch/endpoint and environment.

The compatibility documentation must disclose that this verifies generated client configuration paths, not the Claude Code or Codex executables themselves.

Under that existing standard, a transport-aware generated-Claude smoke can legitimately support `verified` evidence if it passes the same representative-operation contract on the exact implementation head. If it cannot, Claude must remain `community`.

## Existing primitives to reuse

- `scripts/smoke_mcp_plugin.py` already provides the generated-Codex representative-operation harness and trace envelope.
- Generated Claude configs are concrete `plugins/<id>/.claude-plugin/mcp.json` artifacts.
- Sefaria Claude is direct `type: sse`; testing it via the Codex stdio proxy would be invalid evidence.
- `registry/verification-checks.yaml` already provides stable executable evidence IDs; platform identity should extend this graph rather than create another registry.
- `registry/plugins.yaml` already enforces client status from strongest evidence and aggregate status from the weakest client.
- `scripts/validate_verification_checks.py` currently validates simple list-valued Actions matrices but not `matrix.include` cells.

## Recommended scope

### A. Compatibility/evidence guide

Add `wiki/guides/compatibility.md` that distinguishes:

- verified generated client configuration + representative operation;
- community platform startup-only observation;
- deterministic-only configuration evidence;
- not exercised/not claimed.

It must say explicitly that neither current Codex verification nor proposed Claude verification launches the client executable itself. README and installation docs should link it.

### B. Bounded cross-platform startup for Agora-owned local runtimes

Run only Context-Fabric and SEDRA on Linux, Intel macOS x86_64, and Windows x86_64: six startup cells total.

Each cell should use generated launch metadata, assert its actual OS/architecture, initialize MCP, enumerate tools, avoid corpus acquisition/network lookup, and upload attributable evidence. This tests Agora-owned path/subprocess/packaging behavior without making third-party Perseus or hosted Sefaria an Agora cross-platform runtime obligation.

### C. Equivalent generated-Claude live verification

Extend the existing harness with `--client claude` and transport-aware loading:

- stdio for Context-Fabric, Perseus, SEDRA, resolving `${CLAUDE_PLUGIN_ROOT}` exactly without shell interpolation;
- direct SSE for Sefaria from the generated Claude URL, never the Codex proxy.

Run the same representative operation used by the Codex smoke. Successful exact-head runs may support Claude `verified` evidence under the same existing standard.

### D. Canonical platform identity

Add structured `platform.os` and `platform.arch` to verification checks. Platform workflow jobs should use explicit `matrix.include` cells with `runner`, `platform_os`, and `platform_arch`; registry validation should bind each check to exactly one cell and compare declared platform metadata with the selected semantic fields. Runtime workflow tests should separately enforce the actual `platform.system()`/`platform.machine()` assertion.

Do not infer platform from check IDs or runner labels.

## Non-goals

- Do not claim every plugin/client combination works on every OS.
- Do not run real network lookups in every platform cell.
- Do not turn Perseus or hosted Sefaria into Agora-owned cross-platform runtime obligations.
- Do not treat startup-only platform checks as verified client evidence.
- Do not silently translate Sefaria Claude SSE to the Codex stdio proxy.
- Do not claim the Claude Code or Codex application binary was exercised when only generated configuration was driven by the generic harness.
- Do not duplicate existing cache/materializer lock matrices.

## Risks to test adversarially

- Claude and Codex are judged by different verification standards.
- Documentation implies client executables were run when they were not.
- Sefaria Claude evidence accidentally uses the Codex proxy.
- Platform identity is inferred from labels rather than explicit data and runtime assertions.
- `matrix.include` selectors match zero or multiple cells because the validator only understands simple matrices.
- Windows path/argument failures remain hidden behind unit tests.
- Startup-only community evidence accidentally promotes client status.
- Cross-platform jobs expand into expensive network fan-out.

## Research conclusion

#18 remains actionable but is substantially narrower than filed. Agora already has meaningful three-OS lock/cache coverage and one Intel-macOS Context-Fabric smoke. The remaining trustworthy increment is: one explicit compatibility/evidence guide; six cross-OS startup checks for the two Agora-owned local runtimes; equivalent transport-aware generated-Claude representative-operation verification under the same standard already used for generated Codex paths; and explicit platform identity bound through the canonical verification-check graph.