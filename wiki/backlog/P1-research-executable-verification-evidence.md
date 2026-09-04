# Executable verification evidence research

Issue: #11

## Problem statement

Agora currently records plugin/client verification as free-form test names in `registry/plugins.yaml`, for example `scheduled live Homer discovery smoke`. The names describe intent but do not identify an executable check, a workflow/job, a tested revision, or a reproducible runtime. `scripts/validate_registry.py` can validate the status vocabulary and aggregate ranking, but it cannot establish that a claimed check exists or can run.

The repository already has the two execution surfaces needed to replace these strings with machine-traceable evidence:

- deterministic manifest/runtime checks in the unittest suite, especially `tests/test_generation.py`;
- live Codex-path checks in `.github/workflows/external-mcp-smoke.yml`, whose `live-mcp` matrix launches `scripts/smoke_mcp_plugin.py` for `context-fabric`, `perseus`, `sefaria`, and `sedra` and uploads one JSON artifact per plugin.

The missing layer is identity and traceability between those executors and the canonical verification claims.

## Research findings

### 1. Check definitions and check observations have different lifetimes

A stable check definition belongs in source control. A successful GitHub Actions run is an observation of that definition at one commit and time. Storing a mutable `last_successful_run: 123...` inside `registry/plugins.yaml` would require repository churn after every scheduled run and would still be stale between commits.

The canonical registry should therefore reference stable check IDs. Live artifacts should record the run-specific observation: check ID, GitHub run metadata, Agora commit, timestamp, platform/runtime and launch inputs. GitHub Actions history plus the uploaded artifact supplies the current successful observation without hand-editing the registry.

### 2. A check catalog avoids duplicating executor semantics

The same workflow/job information should not be copied into every plugin record. A separate canonical catalog can define each executable check once and let plugin/client evidence reference it.

Proposed file: `registry/verification-checks.yaml`.

Each check needs at least:

- stable `id`;
- `kind`: deterministic or live;
- plugin/client/transport contract it verifies;
- evidence level it is capable of supporting (`community` or `verified`);
- an executable target.

For deterministic checks the target can be an exact unittest target. For live checks the target can identify the workflow file, job ID, matrix selector and artifact name.

Representative IDs:

- `manifest/context-fabric-claude`
- `manifest/perseus-claude`
- `manifest/sefaria-claude`
- `manifest/sedra-claude`
- `mcp-live/context-fabric-codex`
- `mcp-live/perseus-codex`
- `mcp-live/sefaria-codex`
- `mcp-live/sedra-codex`

The ID is an Agora contract and should not depend on the human-readable Actions job label.

### 3. Registry evidence should identify what was tested

A plugin/client evidence record should no longer contain a free-form `name`. It should reference one or more `check_id` values and record stable verification inputs that materially constrain the claim.

For v0.1 the useful reproducibility boundary is the configured launch/runtime input, not a new lockfile system. Examples include `cfabric-mcp==0.1.7`, `perseus-mcp==1.0.2`, `mcp-proxy==0.12.0` plus `mcp>=1.17,<2`, and the bundled SEDRA project revision represented by the Agora commit.

Fully resolving and locking transitive dependency graphs is issue #14 and should not be pulled into #11. #11 should make the evidence traceable to the resolution inputs and observed runtime used by a check.

### 4. Live smoke JSON is the natural run artifact

`smoke_mcp_plugin.py` already emits a JSON report. Its current shape reports plugin, server/tool information, called tool and status, but omits the information needed to reproduce or trace the run.

A live report should also include:

- stable `check_id`;
- `checked_at` UTC timestamp;
- Agora commit (`GITHUB_SHA` when in Actions, otherwise local git revision when available);
- GitHub repository/run ID/run attempt and a run URL when available;
- Python version and platform;
- client and transport;
- exact command/args/cwd from the generated launch manifest;
- configured package/runtime resolution inputs;
- harness dependency/runtime versions that can be determined cheaply (for example MCP SDK version).

The report must remain useful outside GitHub Actions: GitHub-specific fields can be null while revision/runtime/launch fields remain populated.

### 5. Validation must prove executability, not only referential integrity

Checking that an ID exists in `verification-checks.yaml` is insufficient. Foundation should also reject catalog entries that point to nonexistent executors.

For the current executor types this can be validated deterministically:

- unittest target: import/load the named test and require exactly one runnable test;
- GitHub Actions target: require the workflow file to exist, parse its jobs, require the configured job ID, and validate that the declared matrix selector corresponds to a configured matrix value.

The validator should also require the check's plugin/client/transport to match the evidence record that references it.

### 6. Verification status should be bounded by executable evidence

The current aggregate rule—plugin status equals the weakest client status—can remain. The missing client-level rule is that a status cannot exceed the strongest executable evidence referenced by that client.

For v0.1:

- a `community` client can be justified by deterministic manifest/runtime checks;
- a `verified` client must reference at least one check whose declared evidence level is `verified`, currently the live MCP checks.

This keeps Claude at `community` and Codex at `verified` until issue #18 adds stronger Claude-path evidence.

### 7. Adjacent issues remain separate

This issue should not absorb:

- #12 provider/service status semantics;
- #14 deterministic dependency locking;
- #18 broader platform/Claude live coverage;
- #19 resource/member verification evidence.

The check catalog should be extensible enough for those later layers, but this PR should migrate only plugin/client verification.

## Proposed architecture

1. Add `registry/verification-checks.yaml` and a Draft 2020-12 schema.
2. Replace plugin/client free-form `tests` with `checks` references plus explicit tested-input metadata.
3. Extend `validate_registry.py` to validate the check catalog, executor existence, client/check matching and evidence-level/status bounds.
4. Enrich `smoke_mcp_plugin.py` reports with stable check and run/environment metadata.
5. Keep scheduled run observations in uploaded artifacts and Actions history rather than committing changing run IDs.
6. Document how to trace a registry claim from plugin/client → check ID → executor → run artifact.

## Test implications

The RED contract should reject:

- nonexistent check IDs;
- a check referenced by the wrong plugin/client/transport;
- `verified` status backed only by a community/deterministic check;
- catalog entries pointing to nonexistent unittest targets or workflow jobs/matrix entries;
- legacy free-form test records after migration.

It should also assert that a generated live-smoke report contains the stable check ID and reproducibility/run metadata.