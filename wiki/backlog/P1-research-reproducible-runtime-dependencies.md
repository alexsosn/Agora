# P1 research: reproducible runtime dependency environments

Issue: #14

## Question

How should Agora make the dependency environments behind shipped plugin launch paths and live verification reproducible without turning Agora into an upstream dependency-maintenance fork?

## Current state on `main`

The four v0.1 plugins currently have three distinct dependency models.

### Agora-owned local runtimes

`plugins/context-fabric/pyproject.toml` pins `cfabric-mcp==0.1.7` but leaves `PyYAML` as a range and relies on transitive resolution at `uv run` time. `plugins/sedra/pyproject.toml` allows `fastmcp>=2.12.0,<3`, so both the direct FastMCP version and all transitive packages can move without an Agora commit.

The generated Claude/Codex launch commands use `uv run --project ...` without `--locked`. With uv's project interface, `uv run` automatically creates or updates `uv.lock`; an uncommitted or stale lock therefore does not fail closed.

### Third-party `uvx` runtimes

Perseus launches `perseus-mcp==1.0.2` through `uvx`, with only the Intel-macOS `cryptography<43` compatibility constraint. Sefaria's Codex bridge launches `mcp-proxy==0.12.0` with `mcp>=1.17,<2`. These top-level constraints protect important compatibility boundaries, but the remaining transitive graph is resolved afresh when the disposable uv tool environment is recreated.

Sefaria's MCP SDK 1.x bound is already regression-tested in generated launch metadata and must remain explicit even after adding a full resolved constraints file.

### Verification harness

`.github/workflows/external-mcp-smoke.yml` installs the smoke harness with:

```text
uv run --with "mcp>=2,<3" --with "PyYAML>=6,<7" python scripts/smoke_mcp_plugin.py ...
```

The report records Python, uv and the installed MCP SDK version, but the harness itself is not resolved from a committed lock. A later live run can therefore produce new evidence under a different harness without any repository change.

Plugin verification inputs in `registry/plugins.yaml` list human-readable resolution ranges, but they do not identify a stable lock/constraints artifact.

## uv capabilities relevant to the design

Official uv documentation states that:

- `uv.lock` is a universal, cross-platform project lockfile containing exact resolved versions and is intended to be checked into version control;
- `uv run --locked` requires an existing up-to-date lockfile and exits instead of updating it;
- `uv lock --check` verifies that a project lockfile remains current;
- `uvx` is `uv tool run` and accepts `--constraint`/`-c` requirements-style constraint files;
- `uv pip compile --universal` can produce one cross-platform requirements/constraints resolution with environment markers.

References:

- https://docs.astral.sh/uv/concepts/projects/layout/
- https://docs.astral.sh/uv/concepts/projects/sync/
- https://docs.astral.sh/uv/reference/cli/#uv-tool-run
- https://docs.astral.sh/uv/concepts/resolution/
- https://docs.astral.sh/uv/pip/compile/

## Ownership boundary

Dependency reproducibility of Agora's launch and verification paths is Agora-owned integration work. It does not justify modifying upstream package behavior or carrying substitute implementations.

For upstream `uvx` servers, Agora should constrain only the environment used by Agora's advertised launch path. Upstream projects remain responsible for their own dependency metadata and semantic behavior.

## Options considered

### 1. Exact-pin every dependency in each `pyproject.toml`

Rejected. Published project metadata should describe compatibility, not encode one deployment snapshot as a long hand-maintained list. It would also duplicate transitive dependency declarations owned upstream.

### 2. Per-platform requirements files

Rejected for the default design. Agora already claims multiple desktop platforms, and uv provides universal resolution for both project lockfiles and `uv pip compile`. Per-platform files would multiply maintenance and make verification evidence harder to identify consistently.

### 3. Containerize every runtime

Rejected. It is much heavier than Agora's thin marketplace model and would change client installation/launch ergonomics substantially.

### 4. Universal project locks + universal uvx constraints

Selected.

For Agora-owned local runtimes:

- commit `plugins/context-fabric/uv.lock` and `plugins/sedra/uv.lock`;
- retain compatibility ranges in `pyproject.toml`;
- add `--locked` to both Claude and Codex `uv run` launch paths;
- CI runs `uv lock --check` for both projects.

For third-party uvx integrations:

- commit a small source requirements file and a generated universal full constraints file under each affected plugin;
- keep the existing exact top-level package pins and special compatibility bounds visible in launch metadata;
- add `--constraint <plugin-root>/runtime-constraints.txt` to the uvx launch path;
- preserve the explicit Sefaria `mcp>=1.17,<2` argument as a defense-in-depth compatibility contract and regression target;
- CI verifies that the committed constraints still resolve the declared inputs and the real live smoke launches through those same generated client commands.

For the live smoke harness:

- create a dedicated minimal uv project under `verification/mcp-smoke/` with `mcp>=2,<3` and `PyYAML>=6,<7`;
- commit its `uv.lock`;
- run the smoke script via `uv run --locked --project verification/mcp-smoke ...` rather than ad-hoc `--with` dependencies.

## Stable environment identity

A verification claim needs a machine-checkable pointer to the exact dependency snapshot used by the launch or harness.

Extend verification inputs with an `environment` record containing:

- `kind`: `uv-lock`, `uv-constraints`, or `hosted`;
- repository-relative `path` for file-backed environments;
- SHA-256 digest of the committed lock/constraints file for file-backed environments.

For live stdio checks, also record the smoke-harness lock identity. `scripts/smoke_mcp_plugin.py` should emit the actual file digests in its JSON trace so evidence is self-describing rather than relying only on mutable prose.

Registry validation should recompute declared digests. A dependency file change therefore cannot leave the verification input record silently pointing at the old environment. The live-smoke workflow must trigger on every runtime lock/constraint/input file so the changed environment is exercised again.

Hosted Sefaria/Claude has no local Python dependency graph; its environment remains the hosted endpoint and does not need a synthetic lock file.

## Freshness and update semantics

A dependency update is an explicit repository change:

1. update compatibility input only when intended;
2. regenerate the relevant lock/constraints file;
3. update its registry digest;
4. run deterministic freshness validation;
5. rerun the applicable live smoke on the same generated launch path;
6. only then retain or promote verification claims.

This makes transitive updates reviewable and keeps verification evidence tied to an inspectable dependency snapshot.

## Risks and mitigations

- **Universal resolution may contain platform markers.** This is expected and preferable to separate manually coordinated platform files.
- **uv itself can evolve.** `--locked` removes dependency re-resolution from normal local runtime launches. Constraint files fully pin uvx dependency candidates. The live report continues to record the uv version for traceability.
- **Constraint files can drift from their source inputs.** CI must regenerate/check them or otherwise prove that the exact pins still satisfy the declared source requirements.
- **Installed plugin path differences.** Claude constraints paths must use `${CLAUDE_PLUGIN_ROOT}`; Codex paths can be plugin-relative with `cwd: "."` so both clients consume the shipped file rather than a repository-only absolute path.

## Acceptance-criteria mapping

This design covers #14 by providing deterministic local locks, using the same files in user and CI launch paths, adding stable environment identifiers to evidence, fully constraining practical uvx environments, preserving the Sefaria MCP SDK 1.x guard, triggering live verification on dependency snapshot changes, and adding explicit lock/constraint freshness checks.
