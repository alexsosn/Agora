# Design: bounded client/platform verification coverage (#18)

## Goal

Close the remaining trustworthy portion of #18 without building an exhaustive client × plugin × operating-system live-test matrix.

The implementation must add:

1. explicit platform identity to the existing verification-check graph;
2. cross-OS packaged startup evidence for Agora-owned local MCP runtimes (`context-fabric`, `sedra`);
3. the strongest reproducible generated-Claude launch-path check available without pretending to execute Claude Code itself;
4. one documented compatibility/evidence matrix that links claims to stable checks and scopes unsupported combinations honestly.

## Evidence taxonomy

Keep the existing verification status vocabulary (`community`, `verified`) and check kinds (`deterministic`, `live`). Do not create a competing support-status enum.

The compatibility guide describes **evidence mode**, not a new status:

- **live client path** — the named client/transport path itself is exercised with a representative operation;
- **packaged launch** — the generated launch command is resolved and the MCP server is initialized through Agora's generic harness, but the named client executable is not involved;
- **deterministic only** — schema/manifest/path contract only;
- **not exercised** — no claim beyond generated metadata.

A packaged launch check can remain `community` evidence even if it performs a real upstream lookup; it must never be presented as equivalent to executing Claude Code.

## Canonical platform identity

Extend `registry/schema/verification-checks.schema.json` with optional structured platform metadata on a check:

```yaml
platform:
  os: linux | macos | windows
  arch: x86_64 | arm64
```

Both fields are required when `platform` is present. Keep this environment identity on the check, not in prose or the check ID.

For GitHub Actions platform checks:

- the executor still names the workflow/job/matrix selector;
- the selected job must assert `platform.system()` and `platform.machine()` before exercising the MCP path;
- registry validation must reject a platform check whose workflow/job/matrix binding cannot be found;
- tests must reject a mismatch between declared platform metadata and the runner selector/runtime assertion contract.

Do not infer platform semantics from IDs such as `*-windows` or `*-macos`.

## Workflow shape

### 1. Existing Ubuntu live Codex checks remain authoritative

Keep the current `live-mcp` Ubuntu matrix for all four v0.1 plugins. These remain the live Codex-path checks with representative operations and `verified` evidence.

### 2. Bounded local-runtime platform startup matrix

Add one job to `external-mcp-smoke.yml`, for example `local-runtime-platform`, with a six-cell include matrix:

- Context-Fabric × Ubuntu x86_64
- Context-Fabric × Intel macOS x86_64
- Context-Fabric × Windows x86_64
- SEDRA × Ubuntu x86_64
- SEDRA × Intel macOS x86_64
- SEDRA × Windows x86_64

Each cell must:

- use the committed smoke harness environment;
- load the **generated Codex launch metadata**, not duplicate the command in workflow YAML;
- assert actual OS and architecture before launch;
- start the server, initialize MCP, and enumerate the expected tool set;
- avoid corpus acquisition and avoid requiring a real SEDRA HTTP lookup;
- upload a separate JSON trace artifact even on failure;
- run with a small bounded timeout.

The current dedicated `context-fabric-intel-macos` job may be folded into this matrix only if the resulting check remains at least as strict and its regression contract is updated atomically. Do not silently reduce existing Intel-mac evidence.

### 3. Generated Claude launch-path substitute

Extend `scripts/smoke_mcp_plugin.py` (or a small reusable config loader it calls) with an explicit `--client codex|claude` selection.

For `--client claude`:

- load the generated Claude MCP configuration for the selected plugin;
- resolve `${CLAUDE_PLUGIN_ROOT}` to that plugin's checkout root exactly as Claude would need for the generated command;
- start/connect through the generic MCP harness;
- initialize MCP, enumerate expected tools, and perform the same single bounded representative operation where practical;
- record `client_requested: claude` and an explicit trace field such as `client_execution: generic-harness`, so artifacts cannot be mistaken for Claude Code execution.

Add an Ubuntu scheduled/push matrix for all four v0.1 plugins using this mode. Register those checks as `community`, not `verified`.

The existing deterministic Claude manifest checks remain useful and may stay referenced alongside the stronger packaged-launch checks.

## Verification registry changes

Add stable verification check records for:

- six local-runtime platform startup cells; and
- four generated-Claude packaged-launch cells.

For the platform startup checks, use `kind: deterministic` and `evidence_level: community` unless the implementation genuinely exercises the named client path. For generated-Claude generic-harness checks, use `kind: live` only if a real upstream operation is performed, but still `evidence_level: community` and clearly document that this is not Claude-client execution.

Reference the new checks from the relevant `registry/plugins.yaml` client evidence without changing current statuses solely because more checks exist.

The validator must continue enforcing plugin/client/transport binding and add platform binding validation.

## Compatibility guide

Add `wiki/guides/compatibility.md`.

It should contain:

1. a concise client/evidence table for Claude and Codex;
2. a local-runtime platform table for Context-Fabric and SEDRA;
3. exact meaning of live-client vs packaged-launch vs deterministic evidence;
4. stable check IDs backing each exercised cell;
5. an explicit statement that third-party Perseus and hosted Sefaria are not being claimed as fully cross-platform Agora-owned runtimes merely because Ubuntu live smoke succeeds;
6. an explicit statement that macOS evidence is currently Intel x86_64 if that is the runner used;
7. a link to current workflow artifacts/check definitions rather than a claim that all historical runs are green.

README and `wiki/guides/installation.md` should link this guide and avoid broader support language than the matrix supports.

## TDD gates

### RED 1 — platform evidence schema/validator

Commit failing tests before schema/validator implementation:

1. verification-check schema accepts explicit `platform.os` + `platform.arch` only from controlled values;
2. partial/unknown platform metadata is rejected;
3. platform metadata is not inferred from check ID;
4. a referenced GitHub Actions platform check must bind to an executable workflow/job/matrix selector;
5. a declared platform inconsistent with the selected runner/assertion contract is rejected;
6. current registry remains valid only after canonical checks are updated coherently.

### RED 2 — harness client selection

Before implementation, add tests proving:

1. `--client claude` is accepted and chooses generated Claude metadata rather than Codex metadata;
2. `${CLAUDE_PLUGIN_ROOT}` resolves to the exact plugin root without shell interpolation;
3. trace output distinguishes `client_requested` from `client_execution`;
4. default/current Codex behavior is unchanged;
5. malformed/non-stdio generated configs fail clearly rather than falling back to another client's command.

### RED 3 — platform workflow contract

Add structural tests that fail until the workflow exists:

1. exactly the intended six local-runtime cells are present;
2. Ubuntu, Intel macOS, and Windows are all represented for both Agora-owned local runtimes;
3. each cell asserts OS/architecture at runtime;
4. each cell invokes the smoke harness against generated launch metadata and does not hand-code plugin server commands;
5. artifacts are unique and uploaded with `if: always()`;
6. timeouts are bounded;
7. dependency/launch/harness changes retrigger the matrix;
8. removing any OS/plugin cell fails the contract.

### RED 4 — Claude packaged-launch workflow contract

Add tests that fail until:

1. all four v0.1 plugins are exercised with `--client claude` on Ubuntu;
2. the check artifacts are uniquely attributable;
3. no generated-Claude check is promoted to `verified` merely because the generic harness succeeds;
4. the workflow/documentation identifies the execution as generic-harness rather than actual Claude Code.

### RED 5 — compatibility documentation

Add tests that fail until:

1. `wiki/guides/compatibility.md` exists;
2. README and installation guide link it;
3. the guide distinguishes live client path / packaged launch / deterministic only / not exercised;
4. the guide explicitly says generated-Claude packaged checks do not execute Claude Code;
5. the guide identifies Intel x86_64 macOS if that is the tested macOS platform;
6. every check ID named in the guide resolves in `registry/verification-checks.yaml`.

## GREEN implementation order

1. schema + validator platform support;
2. harness client-selection/config-loader changes;
3. workflow platform matrix and Claude packaged-launch matrix;
4. canonical check/plugin evidence updates;
5. compatibility guide and links;
6. run canonical generators/freshness updates if registry inputs change generated artifacts.

Keep commits narrow enough that review can distinguish evidence-model changes from workflow/harness changes.

## Test gate

On the frozen implementation head require:

- Foundation green on all existing jobs plus new deterministic contracts;
- external MCP workflow triggered by all relevant launch/runtime/harness changes;
- successful six-cell local-runtime startup evidence on the implementation head, unless GitHub lacks a requested runner—in that case do not merge a claim for that platform;
- successful four-plugin generated-Claude packaged-launch evidence on the implementation head;
- existing Ubuntu live Codex checks remain green;
- no current `community`/`verified` status is promoted without evidence satisfying the pre-existing status validator.

## Independent adversarial review checklist

Before finalizing, review the frozen head independently for:

- accidental conflation of generic-harness Claude launch with actual Claude-client verification;
- platform labels that are not runtime-asserted;
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

#18 can close when the compatibility guide accurately scopes client/platform support, both Agora-owned local runtimes have bounded packaged-startup evidence on Linux/Intel-macOS/Windows, all four generated Claude launch paths have a reproducible generic-harness check that remains explicitly non-Claude-client evidence, platform identity is traceable through canonical verification checks, and the frozen implementation head passes independent adversarial review.