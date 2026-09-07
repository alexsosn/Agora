# Design: bounded client/platform verification coverage (#18)

## Goal

Close the remaining trustworthy portion of #18 without building an exhaustive client × plugin × operating-system matrix.

The implementation must add:

1. explicit platform identity to the existing verification-check graph;
2. cross-OS packaged startup evidence for Agora-owned local MCP runtimes (`context-fabric`, `sedra`);
3. transport-aware live verification of the generated Claude configurations using the same evidence standard already used for generated Codex configurations;
4. one compatibility/evidence guide that states exactly what those checks do and do not prove.

## One client-path verification standard

Current `verified` Codex evidence does **not** launch a Codex executable. `scripts/smoke_mcp_plugin.py` loads the generated `.codex-plugin/mcp.json`, drives that generated transport through Agora's generic MCP harness, initializes MCP, enumerates expected tools, and performs one representative operation.

#18 must not silently impose a stricter standard on Claude. For this release, a **verified generated client path** means:

- load that client's generated MCP configuration;
- exercise the exact generated transport without substituting another client's transport;
- initialize MCP and enumerate the expected tools;
- perform the bounded representative operation used by the smoke contract;
- record the exact generated launch/endpoint, runtime environment, revision, and check identity in the artifact.

This verifies Agora's generated **client configuration/transport path**, not the Claude Code or Codex application binary. The compatibility guide must say so for **both** clients.

Keep the existing verification vocabulary:

- `kind: deterministic` — deterministic unittest evidence;
- `kind: live` — GitHub Actions runtime observation;
- `evidence_level: community|verified` — maximum claim strength supported by that check.

A successful generated-Claude smoke satisfying the same representative-operation contract as the existing generated-Codex smoke may therefore be `kind: live`, `evidence_level: verified`, and may promote that Claude client status to `verified`. Aggregate plugin status continues to be derived by the existing weakest-client rule; if both client paths become verified, the aggregate may become verified through canonical generation rather than prose edits.

Platform startup-only checks are different: they initialize/list tools but intentionally do not perform the representative provider operation, so they are `kind: live`, `evidence_level: community`.

## Canonical platform identity

Extend `registry/schema/verification-checks.schema.json` with optional structured platform metadata:

```yaml
platform:
  os: linux | macos | windows
  arch: x86_64 | arm64
```

Both fields are required when `platform` is present. Platform semantics live in data, not check IDs or runner-name heuristics.

### Structural workflow binding

Platform jobs must use explicit `strategy.matrix.include` cells, for example:

```yaml
include:
  - plugin: context-fabric
    runner: ubuntu-latest
    platform_os: linux
    platform_arch: x86_64
```

The job runs on `${{ matrix.runner }}` and runtime preflight compares normalized `platform.system()` / `platform.machine()` values with `matrix.platform_os` / `matrix.platform_arch` before MCP launch.

Extend `scripts/validate_verification_checks.py` so Actions selectors can resolve either the existing simple list-valued matrix or one exact `matrix.include` cell. For a check carrying `platform`, validation requires exactly one selected cell and exact equality between the check's OS/arch and that cell's `platform_os`/`platform_arch`.

Structural workflow tests—not registry parsing of shell—must ensure the job consumes those matrix values in the runtime assertion.

## Workflow shape

### 1. Existing generated-Codex live smoke remains authoritative

Keep the current Ubuntu `live-mcp` matrix for all four v0.1 plugins. It is the existing verified generated-Codex-path evidence and representative-operation baseline.

### 2. Bounded local-runtime platform startup matrix

Add exactly six `matrix.include` cells:

- Context-Fabric × Ubuntu x86_64
- Context-Fabric × Intel macOS x86_64
- Context-Fabric × Windows x86_64
- SEDRA × Ubuntu x86_64
- SEDRA × Intel macOS x86_64
- SEDRA × Windows x86_64

Every cell carries `plugin`, `runner`, `platform_os`, and `platform_arch` and must:

- use the committed smoke-harness environment;
- load generated Codex launch metadata rather than duplicate the server command in YAML;
- runtime-assert OS/architecture before launch;
- initialize MCP and enumerate expected tools;
- avoid corpus acquisition and real SEDRA HTTP lookup;
- upload a unique JSON trace with `if: always()`;
- use a bounded timeout.

These six records are `kind: live`, `evidence_level: community`. They add platform startup confidence but do not independently establish verified client-path behavior on every OS.

The existing dedicated Intel-macOS Context-Fabric job may be folded into this matrix only if its guarantees are preserved or strengthened atomically.

### 3. Generated-Claude verified path

Extend `scripts/smoke_mcp_plugin.py` (or a reusable loader it calls) with explicit `--client codex|claude` and transport-aware configuration loading.

For Claude:

- load `plugins/<id>/.claude-plugin/mcp.json`;
- for Context-Fabric, Perseus, and SEDRA stdio entries, resolve `${CLAUDE_PLUGIN_ROOT}` to the exact plugin root without shell interpolation;
- for Sefaria `type: sse`, connect directly to the generated `https://mcp.sefaria.org/sse` endpoint; never substitute the Codex stdio proxy;
- initialize MCP, enumerate expected tools, and perform the same bounded representative operation as the existing Codex smoke;
- record `client_requested: claude`, generated transport, and `client_execution: generic-harness` in the trace.

Add an Ubuntu matrix for all four v0.1 plugins. If these exact-head checks succeed, register them as `kind: live`, `evidence_level: verified` and update Claude client statuses accordingly. If any generated Claude path cannot satisfy the same smoke contract, keep that client at `community` and do not merge an overstated compatibility claim.

Existing deterministic Claude manifest checks remain useful alongside live evidence.

Malformed or unsupported generated transport shapes fail clearly; there is no fallback to Codex configuration or transport rewriting.

## Verification registry changes

Add stable check records for:

- six local-runtime platform startup cells (`live` / `community`); and
- four generated-Claude representative-operation cells (`live` / `verified` only after their exact-head workflow succeeds).

Reference new checks from the relevant `registry/plugins.yaml` client evidence. Platform community checks do not lower or raise a stronger client status. Claude status promotion, if earned, follows the pre-existing strongest-evidence validator; aggregate status then follows the pre-existing weakest-client rule.

This ticket must also update any registry-derived release-status block/artifacts made stale by legitimate canonical status changes.

## Compatibility guide

Add `wiki/guides/compatibility.md` with:

1. a client-path evidence table for Claude and Codex;
2. a local-runtime platform table for Context-Fabric and SEDRA;
3. stable check IDs backing every exercised cell;
4. a precise statement that current live client-path verification executes generated client MCP configuration through the generic harness, **not** the Claude Code or Codex executable itself;
5. a distinction between verified representative-operation evidence and community startup-only platform evidence;
6. an explicit statement that macOS platform startup evidence is Intel x86_64 if that is the runner used;
7. an explicit distinction between Sefaria Claude direct SSE and Codex stdio-via-SSE-proxy;
8. no claim that third-party Perseus/Sefaria have full Agora-owned cross-platform runtime coverage merely because their generated client paths work on Ubuntu;
9. links to current check definitions/workflow artifacts rather than a claim that every historical run is green.

README and `wiki/guides/installation.md` should link the guide and use terminology consistent with it.

## TDD gates

### RED 1 — platform schema/selector validation

Commit failing tests before implementation:

1. valid explicit platform OS/arch is accepted; partial/unknown values are rejected;
2. no platform semantics are inferred from check IDs;
3. existing simple-list Actions selectors continue to validate;
4. one exact `matrix.include` cell can be selected;
5. zero, multiple, or partial include matches fail closed;
6. declared check platform must equal selected cell `platform_os`/`platform_arch`;
7. the six new platform Actions checks are `live` / `community`.

### RED 2 — client/transport harness selection

Add tests proving:

1. `--client claude` chooses Claude metadata and Codex default behavior is unchanged;
2. `${CLAUDE_PLUGIN_ROOT}` resolves exactly without a shell;
3. Sefaria Claude selects generated direct SSE and never the Codex proxy;
4. trace distinguishes requested client, generated transport, and generic-harness execution;
5. malformed/unsupported transports fail without fallback;
6. representative operation selection remains identical across Claude/Codex for the same plugin.

### RED 3 — platform workflow contract

Add tests requiring:

1. exactly six intended include cells with no duplicates;
2. Context-Fabric and SEDRA each cover Linux, Intel macOS, and Windows x86_64;
3. `runner`, `platform_os`, and `platform_arch` are explicit;
4. `runs-on` and runtime assertions consume those matrix fields;
5. generated launch metadata is used; server commands are not hand-coded;
6. artifacts are unique/always uploaded and timeouts bounded;
7. all launch/runtime/harness changes retrigger the matrix.

### RED 4 — generated-Claude live contract

Add tests requiring:

1. all four v0.1 plugins run with `--client claude` on Ubuntu;
2. artifacts are uniquely attributable;
3. Sefaria uses generated SSE while the other three use generated stdio;
4. check definitions are `kind: live` and can be `evidence_level: verified` only when the full representative-operation path is exercised;
5. compatibility wording states that neither Claude nor Codex client binaries are launched;
6. canonical Claude/aggregate status cannot exceed the strongest/weakest evidence rules already enforced by the registry validator.

### RED 5 — compatibility documentation

Add tests requiring:

1. `wiki/guides/compatibility.md` exists;
2. README and installation guide link it;
3. guide distinguishes verified representative-operation evidence from community platform startup evidence and deterministic-only evidence;
4. guide discloses generic-harness execution for both Claude and Codex;
5. guide identifies Intel x86_64 macOS platform evidence;
6. guide distinguishes Sefaria direct-SSE Claude from stdio-proxy Codex;
7. every named check ID resolves canonically.

## GREEN implementation order

1. schema + validator platform/include support;
2. harness client/transport support;
3. platform and Claude workflow matrices;
4. canonical verification records/statuses only after observed evidence supports them;
5. compatibility guide and links;
6. regenerate/check all canonical-derived artifacts affected by status changes.

## Test gate

On the frozen implementation head require:

- Foundation green;
- existing generated-Codex Ubuntu live checks green;
- all six local-runtime platform startup cells green on the exact head; if a runner is unavailable, do not merge a claim for that cell;
- all four generated-Claude representative-operation checks green before setting their evidence/status to verified;
- generated release/status artifacts fresh against any canonical status promotion;
- no status exceeds the existing evidence validator.

## Independent adversarial review checklist

Review the frozen head independently for:

- asymmetric standards between Claude and Codex;
- wording that implies either client executable was launched when only generated configuration was exercised;
- accidental use of the Codex Sefaria proxy for Claude;
- platform semantics inferred from names instead of explicit include data;
- zero/multiple include-selector matches;
- missing runtime OS/architecture assertions;
- Windows path/argument failures hidden by unit tests;
- hand-coded workflow launch commands bypassing generated manifests;
- status promotion before exact-head live evidence exists;
- community startup checks accidentally treated as verified client evidence;
- unbounded network fan-out;
- regressions to existing Intel-mac Context-Fabric evidence;
- third-party behavior being turned into an Agora-owned cross-platform obligation;
- stale compatibility/check IDs or generated status docs.

## Completion criteria

#18 can close when client-path verification uses one explicit standard for Claude and Codex, both Agora-owned local runtimes have bounded startup evidence on Linux/Intel-macOS/Windows, platform identity is canonically bound to exact workflow cells, the compatibility guide scopes every claim honestly, canonical statuses reflect only exact-head successful evidence, and the final implementation passes independent adversarial review.