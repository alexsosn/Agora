# Executable verification evidence design

Issue: #11
Depends on research: `P1-research-executable-verification-evidence.md`

## Goal

Replace free-form plugin/client verification test names with stable references to executable checks and make live check artifacts traceable to the exact run, Agora revision, runtime and launch inputs that produced them.

## Scope

This change owns plugin/client integration evidence only. It does not redesign provider status (#12), introduce lockfiles (#14), expand the client/platform matrix (#18), or add resource/member evidence (#19).

## Data model

### Check catalog

Add `registry/verification-checks.yaml` with `schema_version: 1` and `checks`.

Each check record contains:

- `id` — stable slash-delimited check ID;
- `kind` — `deterministic` or `live`;
- `plugin`;
- `client`;
- `transport`;
- `evidence_level` — `community` or `verified`;
- `executor` — exactly one supported executable target.

Executor forms:

- unittest: `type: unittest`, `target: <module.class.method>`;
- GitHub Actions: `type: github-actions`, `workflow`, `job`, optional `matrix`, and `artifact`.

### Plugin/client evidence

Replace `tests` with `checks`:

```yaml
verification:
  clients:
    codex:
      status: verified
      transport: stdio
      checks:
        - check_id: mcp-live/context-fabric-codex
          inputs:
            - cfabric-mcp==0.1.7
            - python==3.13
```

`inputs` are stable configured resolution/runtime inputs used to reproduce the claim. They are not a substitute for #14's future resolved dependency environment.

## Executable validation

Extend `scripts/validate_registry.py` to:

1. schema-validate `verification-checks.yaml`;
2. reject duplicate check IDs;
3. validate each referenced check ID exists;
4. require referenced check plugin/client/transport to match the referencing evidence record;
5. reject a client status stronger than the strongest referenced executable evidence level;
6. preserve the existing aggregate plugin status = weakest client rule;
7. for unittest executors, load the exact target with `unittest.TestLoader` and require one runnable test;
8. for GitHub Actions executors, require the workflow path and configured job; require declared matrix values to be represented by that job's strategy matrix;
9. reject unsupported executor types.

Foundation already invokes `validate_registry.py`, so no second validation entry point is needed.

## Live artifact contract

Extend `scripts/smoke_mcp_plugin.py` with a stable plugin → live check ID mapping and report metadata:

```json
{
  "check_id": "mcp-live/perseus-codex",
  "checked_at": "...Z",
  "plugin": "perseus",
  "client": "codex",
  "transport": "stdio",
  "agora_revision": "...",
  "github": {
    "repository": "alexsosn/Agora",
    "run_id": "...",
    "run_attempt": "...",
    "run_url": "..."
  },
  "runtime": {
    "python": "3.13.x",
    "platform": "...",
    "mcp_sdk": "..."
  },
  "launch": {
    "command": "uvx",
    "args": [...],
    "cwd": "."
  },
  "verification_inputs": [...],
  "status": "ok"
}
```

Failure JSON should carry the same identity/run/runtime envelope where possible, rather than dropping trace metadata on the path most useful for diagnosis.

The workflow continues uploading `mcp-smoke-<plugin>` artifacts. A stable check ID maps a canonical claim to its workflow/job/matrix/artifact; Actions history determines the latest successful run without committing an ephemeral run number.

## Documentation

Update `registry/README.md` to document:

- check IDs and catalog semantics;
- distinction between check definition and run observation;
- how to trace a live claim to Actions history/artifacts;
- status bounds (`community` deterministic, `verified` requires verified-level evidence);
- the boundary with #14/#18/#19.

README verification wording should continue to state aggregate `community` and scoped Codex live verification; it must not imply that adding a check definition proves a successful run by itself.

## TDD sequence

### RED 1 — catalog/reference contract

Add tests that expect:

- a canonical check catalog to exist;
- every client evidence record to use `checks`, not free-form `tests`;
- nonexistent check IDs to fail validation;
- plugin/client/transport mismatch to fail validation;
- a `verified` client backed only by community evidence to fail validation.

These tests must fail before the catalog/schema/validator migration exists.

### GREEN 1

Add the catalog/schema, migrate `plugins.yaml`, and implement referential/status validation.

### RED 2 — executor contract

Add mutation tests for nonexistent unittest targets, missing workflow jobs, and invalid matrix values.

### GREEN 2

Add executor validation.

### RED 3 — traceable live artifact

Add tests around a pure report-metadata builder or patched smoke execution requiring check ID, timestamp, revision, GitHub run metadata, runtime, launch and configured verification inputs in success and error reports.

### GREEN 3

Enrich the smoke harness without changing the scholarly operation performed by each existing live case.

## Acceptance-criterion mapping

- Stable check IDs → check catalog IDs and plugin references.
- Client/transport/check/revision → catalog plugin/client/transport plus registry inputs and artifact revision metadata.
- Last successful run/timestamp → stable workflow/artifact mapping plus run ID/timestamp embedded in each artifact; queryable through GitHub Actions history without registry edits.
- Executable IDs validated → unittest/workflow/job/matrix validator.
- Status derived/validated against evidence → client evidence-level bound + existing weakest-client aggregate rule.
- Reproducible environment → report Python/platform/MCP SDK/launch + configured resolution inputs; dependency locking deferred to #14.
- Stale/missing/nonexistent IDs → mutation/regression tests and Foundation validation.
- User-facing claims → registry README/README wording remains scoped to the executable evidence actually present.

## Finalization gate

A PR can be finalized only after:

1. Foundation is green on the final head;
2. any affected live MCP workflow is green and emits the enriched artifacts;
3. a fresh independent review is performed on that exact head;
4. every review finding is fixed with a regression where applicable and followed by another fresh review.