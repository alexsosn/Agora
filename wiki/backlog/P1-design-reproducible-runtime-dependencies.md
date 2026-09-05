# P1 design: reproducible runtime dependency environments

Issue: #14

Research: `wiki/backlog/P1-research-reproducible-runtime-dependencies.md`

## Goal

Make every v0.1 Python launch path that Agora verifies depend on a committed, machine-identifiable dependency snapshot, while retaining the thin-marketplace boundary and existing public plugin semantics.

## Non-goals

- Do not change upstream plugin behavior.
- Do not replace upstream dependency metadata with Agora-maintained forks.
- Do not require containers for normal plugin launch.
- Do not promote Claude paths to live-verified; #18 owns broader client/platform verification.
- Do not make a lock file stale merely because newer packages appear on PyPI. Freshness means that the committed snapshot still satisfies its declared inputs.

## File model

### Agora-owned local runtimes

Add:

- `plugins/context-fabric/uv.lock`
- `plugins/sedra/uv.lock`

The existing `pyproject.toml` files remain the compatibility declarations. Generated Claude/Codex commands add `--locked` to `uv run`.

### Third-party uvx runtimes

Add:

- `plugins/perseus/runtime-requirements.in`
- `plugins/perseus/runtime-constraints.txt`
- `plugins/sefaria/runtime-requirements.in`
- `plugins/sefaria/runtime-constraints.txt`

The `.in` files contain only Agora's intentional direct/compatibility requirements:

Perseus:

```text
perseus-mcp==1.0.2
cryptography<43; platform_system == "Darwin" and platform_machine == "x86_64"
```

Sefaria Codex bridge:

```text
mcp-proxy==0.12.0
mcp>=1.17,<2
```

The generated constraints files are universal, exact transitive snapshots produced by uv. Launch commands add `--constraint` pointing at the shipped plugin-local file. The explicit Sefaria `--with mcp>=1.17,<2` remains in the command and its regression test remains mandatory.

### Live smoke harness

Add:

- `verification/mcp-smoke/pyproject.toml`
- `verification/mcp-smoke/uv.lock`

The project declares the harness compatibility requirements (`mcp>=2,<3`, `PyYAML>=6,<7`). `.github/workflows/external-mcp-smoke.yml` runs the existing `scripts/smoke_mcp_plugin.py` through this project with `uv run --locked --project verification/mcp-smoke`.

## Registry environment identity

Extend `registry/schema/plugins.schema.json` verification inputs with optional/required dependency environment records.

Proposed shape for a file-backed Python environment:

```yaml
environment:
  kind: uv-lock
  path: plugins/context-fabric/uv.lock
  sha256: <64 lowercase hex characters>
```

`kind` values:

- `uv-lock`
- `uv-constraints`
- `hosted`

For local or uvx launch checks, `path` and `sha256` are required. Hosted-only checks may use `kind: hosted` without a file.

Live Codex checks additionally carry `harness_environment` pointing at `verification/mcp-smoke/uv.lock`.

`registry/plugins.yaml` remains the canonical source for these records. Generated client manifests continue to come from runtime launch metadata.

## Validation

Add `scripts/validate_runtime_environments.py` with two responsibilities that do not require network access:

1. parse every file-backed environment reference from `registry/plugins.yaml`;
2. require an existing repository-relative file and verify its SHA-256 against the registry declaration.

It also validates ownership-specific invariants:

- Context-Fabric and SEDRA launches use their declared `uv.lock` via `uv run --locked`;
- Perseus and Sefaria Codex `uvx` launches pass their declared constraint file;
- Sefaria still includes `mcp>=1.17,<2` explicitly;
- every live Python check identifies the smoke harness lock.

`validate_registry.py` should invoke this validator so Foundation catches missing/stale digest references without requiring uv or network access.

## uv freshness workflow

Add a targeted workflow or Foundation-adjacent job that installs uv and checks dependency snapshots.

For local projects:

```text
uv lock --check --project plugins/context-fabric
uv lock --check --project plugins/sedra
uv lock --check --project verification/mcp-smoke
```

For uvx constraints, add `scripts/check_uvx_constraints.py` or an equivalent shell/Python wrapper that:

1. copies the committed constraints file to a temporary output path;
2. invokes `uv pip compile --universal --no-header --no-annotate <runtime-requirements.in> -o <temporary-copy>`;
3. relies on uv's existing-output preferences so the committed pins are retained when valid;
4. fails if the resulting canonical pin set differs.

The workflow triggers on all local pyprojects/locks, uvx input/constraint files, launch metadata/generator, verification registry/schema, smoke harness files, validation scripts, and itself.

The existing live-smoke workflow also triggers on all runtime lock/constraint files and the harness lock so changing a dependency snapshot reruns the real verified path.

## Evidence trace

Extend `scripts/smoke_mcp_plugin.py` trace output with dependency environment records copied from the canonical verification input plus an independently recomputed `actual_sha256` for each file-backed environment.

The smoke must fail before launch if the registry digest and actual file differ. This prevents an evidence artifact from claiming one dependency snapshot while executing another.

The report continues to include Python, uv and installed MCP SDK versions as runtime observations.

## TDD slices

### RED 1 — canonical dependency environment contract

Add failing tests that require:

- Context-Fabric and SEDRA generated launch commands include `--locked`;
- Perseus and Sefaria Codex launch commands include plugin-local constraint paths;
- the explicit Sefaria MCP SDK `<2` compatibility guard remains present;
- registry verification inputs reference file-backed environments and live checks reference the harness lock;
- the offline digest validator rejects a mutated or stale digest.

Expected failure: no locks/constraints/environment schema exist and launch commands are not locked.

### GREEN 1 — schema, launch metadata, offline validator

Implement the schema and registry fields, launch argument changes, validator, and generated artifacts. Use placeholder environment files only if necessary to advance to the generation gate; do not mark GREEN until actual files and digests are valid.

### RED 2 — lock/constraint semantic freshness

Add tests for the uv freshness command construction and workflow triggers. A fixture should prove that constraint checking preserves a valid committed exact pin set instead of treating newer releases as automatic staleness.

Expected failure: no uv freshness tooling/workflow exists.

### GREEN 2 — generate real snapshots and freshness CI

Generate:

- local plugin `uv.lock` files;
- the smoke-harness `uv.lock`;
- universal exact Perseus/Sefaria constraints.

Add uv semantic freshness CI and include it in relevant path triggers.

### RED 3 — evidence trace is bound to environment snapshot

Add smoke-report tests that mutate a referenced environment file or digest and require failure before MCP launch; assert emitted reports contain declared and actual environment digests.

### GREEN 3 — trace binding and live workflow

Implement trace digest verification and switch the live smoke harness to its locked project. Extend workflow triggers to all dependency snapshot inputs.

## Test gate

Before independent review, require:

1. `python scripts/validate_registry.py`
2. `python scripts/generate_marketplaces.py --check`
3. full unit suite
4. runtime dependency snapshot workflow green
5. live MCP smoke green for Context-Fabric, Perseus, Sefaria and SEDRA on the exact PR head
6. existing materializer/load/source-audit checks unaffected or green when triggered

## Independent review gate

Fresh review must load current target-branch `AGENTS.md`, `CONTRIBUTING.md`, PR template, `agora-pr-review`, and `agora-plugin-review`, then inspect the exact final diff and CI.

Special review questions:

- Are locks/constraints actually consumed by shipped launch commands, or merely committed documentation?
- Can a lock/constraint change retain an old registry digest or avoid the live-smoke trigger?
- Is the Sefaria SDK `<2` compatibility boundary still explicit and tested?
- Did Agora accidentally take ownership of upstream package semantics instead of only its launch environment?
- Are generated client manifests still canonical projections from registry metadata?

Any material finding starts a new RED/fix/test/fresh-review cycle before merge.
