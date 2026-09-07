# Design: bounded client/platform verification coverage (#18)

## Goal

Close the remaining trustworthy portion of #18 without building an exhaustive client × plugin × operating-system live-test matrix.

The implementation must add:

1. explicit platform identity to the existing verification-check graph;
2. cross-OS packaged startup evidence for Agora-owned local MCP runtimes (`context-fabric`, `sedra`);
3. the strongest reproducible generated-Claude transport-path checks available without pretending to execute Claude Code itself;
4. one documented compatibility/evidence matrix that links claims to stable checks and scopes unsupported combinations honestly.

## Evidence taxonomy

Keep the existing verification status vocabulary (`community`, `verified`) and check kinds (`deterministic`, `live`). Do not create a competing support-status enum.

The compatibility guide describes **evidence mode**, not a new status:

- **live client path** — the named client/transport path itself is exercised with a representative operation;
- **generated transport path** — the generated client configuration is resolved and exercised through Agora's generic MCP harness, but the named client executable is not involved;
- **deterministic only** — schema/manifest/path contract only;
- **not exercised** — no claim beyond generated metadata.

A generated transport-path check can remain `community` evidence even if it performs a real upstream lookup; it must never be presented as equivalent to executing Claude Code.

## Canonical platform identity

Extend `registry/schema/verification-checks.schema.json` with optional structured platform metadata on a check:

```yaml
platform:
  os: linux | macos | windows
  arch: x86_64 | arm64
```

Both fields are required when `platform` is present. Keep this environment identity on the check, not in prose or the check ID.

### Structural workflow binding

Do **not** infer OS/architecture from GitHub runner labels and do not parse shell snippets in registry validation.

Platform workflow jobs must use explicit `strategy.matrix.include` cells carrying the semantic identity that the runtime assertion consumes, for example:

```yaml
include:
  - plugin: context-fabric
    runner: ubuntu-latest
    platform_os: linux
    platform_arch: x86_64
```

The job runs on `${{ matrix.runner }}` and its preflight assertion receives `matrix.platform_os` / `matrix.platform_arch` as the expected values.

Extend `scripts/validate_verification_checks.py` so GitHub Actions executor selectors can match either:

- the existing simple list-valued matrix form; or
- one exact `matrix.include` cell.

For a check with `platform`, validation must require:

1. its executor selector resolves to exactly one executable include cell;
2. the selected cell's `platform_os` equals `check.platform.os`;
3. the selected cell's `platform_arch` equals `check.platform.arch`.

Structural workflow tests—not registry parsing of shell—must ensure the job actually asserts `platform.system()` and `platform.machine()` against those matrix values before MCP launch.

Do not infer platform semantics from IDs such as `*-windows` or `*-macos`.

## Workflow shape

### 1. Existing Ubuntu live Codex checks remain authoritative

Keep the current `live-mcp` Ubuntu matrix for all four v0.1 plugins. These remain the live Codex-path checks with representative operations and `verified` evidence.

### 2. Bounded local-runtime platform startup matrix

Add one job to `external-mcp-smoke.yml`, for example `local-runtime-platform`, with exactly six `matrix.include` cells:

- Context-Fabric × Ubuntu x86_64
- Context-Fabric × Intel macOS x86_64
- Context-Fabric × Windows x86_64
- SEDRA × Ubuntu x86_64
- SEDRA × Intel macOS x86_64
- SEDRA × Windows x86_64

Each include cell carries `plugin`, `runner`, `platform_os`, and `platform_arch` explicitly.

Each cell must:

- use the committed smoke harness environment;
- load the **generated Codex launch metadata**, not duplicate the command in workflow YAML;
- assert actual OS and architecture against `matrix.platform_os` / `matrix.platform_arch` before launch;
- start the server, initialize MCP, and enumerate the expected tool set;
- avoid corpus acquisition and avoid requiring a real SEDRA HTTP lookup;
- upload a separate JSON trace artifact even on failure;
- run with a small bounded timeout.

The current dedicated `context-fabric-intel-macos` job may be folded into this matrix only if the resulting check remains at least as strict and its regression contract is updated atomically. Do not silently reduce existing Intel-mac evidence.

### 3. Generated Claude transport-path substitute

Extend `scripts/smoke_mcp_plugin.py` (or reusable config loaders it calls) with an explicit `--client codex|claude` selection and transport-aware generated configuration handling.

For `--client claude`:

- load the generated Claude MCP configuration for the selected plugin;
- for stdio configurations (`context-fabric`, `perseus`, `sedra`), resolve `${CLAUDE_PLUGIN_ROOT}` to that plugin's checkout root exactly and launch without shell interpolation;
- for Sefaria's generated `type: sse` configuration, connect directly to the generated URL through the generic MCP SSE client rather than inventing a stdio proxy path;
- initialize MCP, enumerate expected tools, and perform the same single bounded representative operation where practical;
- record `client_requested: claude`, the generated transport, and an explicit trace field such as `client_execution: generic-harness`, so artifacts cannot be mistaken for Claude Code execution.

Add an Ubuntu scheduled/push matrix for all four v0.1 plugins using this mode. Register those checks as `community`, not `verified`.

The existing deterministic Claude manifest checks remain useful and may stay referenced alongside the stronger generated-transport checks.

Unsupported or malformed generated transport shapes must fail clearly. They must never fall back to another client's configuration or silently translate SSE into stdio.

## Verification registry changes

Add stable verification check records for:

- six local-runtime platform startup cells; and
- four generated-Claude transport-path cells.

For the platform startup checks, use `kind: deterministic` and `evidence_level: community` unless the implementation genuinely performs a provider operation. For generated-Claude generic-harness checks, use `kind: live` only if a real upstream operation is performed, but keep `evidence_level: community` and clearly document that this is not Claude-client execution.

Reference the new checks from the relevant `registry/plugins.yaml` client evidence without changing current statuses solely because more checks exist.

The validator must continue enforcing plugin/client/transport binding, support exact `matrix.include` selector binding, and add explicit platform-to-cell consistency validation.

## Compatibility guide

Add `wiki/guides/compatibility.md`.

It should contain:

1. a concise client/evidence table for Claude and Codex;
2. a local-runtime platform table for Context-Fabric and SEDRA;
3. exact meaning of live-client vs generated-transport vs deterministic evidence;
4. stable check IDs backing each exercised cell;
5. an explicit statement that third-party Perseus and hosted Sefaria are not being claimed as fully cross-platform Agora-owned runtimes merely because Ubuntu path checks succeed;
6. an explicit statement that macOS evidence is currently Intel x86_64 if that is the runner used;
7. an explicit statement that the Claude Sefaria substitute exercises the generated direct-SSE configuration, not the Codex stdio proxy configuration;
8. a link to current workflow artifacts/check definitions rather than a claim that all historical runs are green.

README and `wiki/guides/installation.md` should link this guide and avoid broader support language than the matrix supports.

## TDD gates

### RED 1 — platform evidence schema/validator

Commit failing tests before schema/validator implementation:

1. verification-check schema accepts explicit `platform.os` + `platform.arch` only from controlled values;
2. partial/unknown platform metadata is rejected;
3. platform metadata is not inferred from check ID;
4. the existing simple-list Actions selector behavior remains valid;
5. a GitHub Actions executor selector can bind one exact `matrix.include` cell;
6. missing, non-unique, or partially matching include selectors fail closed;
7. a platform check whose declared OS/arch disagrees with the selected cell's `platform_os`/`platform_arch` is rejected;
8. current registry remains valid only after canonical checks are updated coherently.

### RED 2 — harness client/transport selection

Before implementation, add tests proving:

1. `--client claude` is accepted and chooses generated Claude metadata rather than Codex metadata;
2. `${CLAUDE_PLUGIN_ROOT}` resolves to the exact plugin root without shell interpolation for Claude stdio configurations;
3. Sefaria's Claude `type: sse` configuration selects the generated direct SSE URL and does not invoke the Codex proxy configuration;
4. trace output distinguishes `client_requested`, generated transport, and `client_execution`;
5. default/current Codex behavior is unchanged;
6. malformed or unsupported generated transport shapes fail clearly rather than falling back to another client's command.

### RED 3 — platform workflow contract

Add structural tests that fail until the workflow exists:

1. exactly the intended six `matrix.include` cells are present;
2. Ubuntu, Intel macOS, and Windows are represented for both Agora-owned local runtimes;
3. each cell declares `runner`, `platform_os`, and `platform_arch` explicitly;
4. the job consumes those exact matrix values for `runs-on` and runtime OS/architecture assertions;
5. each cell invokes the smoke harness against generated launch metadata and does not hand-code plugin server commands;
6. artifacts are unique and uploaded with `if: always()`;
7. timeouts are bounded;
8. dependency/launch/harness changes retrigger the matrix;
9. removing or duplicating any OS/plugin cell fails the contract.

### RED 4 — Claude generated-transport workflow contract

Add tests that fail until:

1. all four v0.1 plugins are exercised with `--client claude` on Ubuntu;
2. the check artifacts are uniquely attributable;
3. the Sefaria cell exercises generated SSE while the three local Claude cells exercise generated stdio;
4. no generated-Claude check is promoted to `verified` merely because the generic harness succeeds;
5. workflow/documentation identifies execution as generic-harness rather than actual Claude Code.

### RED 5 — compatibility documentation

Add tests that fail until:

1. `wiki/guides/compatibility.md` exists;
2. README and installation guide link it;
3. the guide distinguishes live client path / generated transport path / deterministic only / not exercised;
4. the guide explicitly says generated-Claude checks do not execute Claude Code;
5. the guide identifies Intel x86_64 macOS if that is the tested macOS platform;
6. the guide distinguishes Sefaria Claude direct SSE from Codex stdio-via-SSE-proxy;
7. every check ID named in the guide resolves in `registry/verification-checks.yaml`.

## GREEN implementation order

1. schema + validator platform/include-selector support;
2. harness client/transport-selection changes;
3. workflow platform matrix and Claude generated-transport matrix;
4. canonical check/plugin evidence updates;
5. compatibility guide and links;
6. run canonical generators/freshness updates if registry inputs change generated artifacts.

Keep commits narrow enough that review can distinguish evidence-model changes from workflow/harness changes.

## Test gate

On the frozen implementation head require:

- Foundation green on all existing jobs plus new deterministic contracts;
- external MCP workflow triggered by all relevant launch/runtime/harness changes;
- successful six-cell local-runtime startup evidence on the implementation head, unless GitHub lacks a requested runner—in that case do not merge a claim for that platform;
- successful four-plugin generated-Claude transport-path evidence on the implementation head;
- existing Ubuntu live Codex checks remain green;
- no current `community`/`verified` status is promoted without evidence satisfying the pre-existing status validator.

## Independent adversarial review checklist

Before finalizing, review the frozen head independently for:

- accidental conflation of generic-harness Claude transport execution with actual Claude-client verification;
- accidental use of the Codex Sefaria proxy while claiming the Claude direct-SSE path;
- platform labels that are not runtime-asserted;
- platform semantics inferred from runner/check names instead of explicit include-cell fields;
- include selectors that match zero or multiple cells;
- Windows path/argument handling through generated metadata;
- any workflow command that bypasses generated manifests;
- status promotion caused merely by adding more checks;
- matrix omissions hidden by aggregate success;
- unbounded live-network fan-out;
- stale compatibility cells/check IDs;
- regressions to the existing Intel-mac Context-Fabric evidence;
- whether third-party plugin behavior has leaked into Agora-owned cross-platform obligations;
- exact-head CI/workflow evidence for every newly claimed cell.

## Completion criteria

#18 can close when the compatibility guide accurately scopes client/platform support, both Agora-owned local runtimes have bounded packaged-startup evidence on Linux/Intel-macOS/Windows, all four generated Claude configurations have reproducible transport-aware generic-harness evidence that remains explicitly non-Claude-client evidence, platform identity is traceable through canonical verification checks with exact workflow-cell binding, and the frozen implementation head passes independent adversarial review.