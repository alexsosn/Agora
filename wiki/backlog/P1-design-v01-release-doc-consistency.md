# Design: v0.1 release-document consistency (#16)

## Goal

Make `wiki/releases/v0.1-plan-active.md` accurately describe the current v0.1 implementation and prevent its dynamic plugin/client verification summary from drifting beyond canonical registry evidence.

## Inputs

Canonical inputs:

- `registry/v0.1.yaml` — fixed v0.1 plugin IDs;
- `registry/plugins.yaml` — aggregate and per-client verification statuses plus referenced check IDs;
- `registry/verification-checks.yaml` — machine-readable check kind, evidence level, plugin, client, and transport semantics;
- existing required-skill tests — evidence that the current v0.1 scholarly skill set is implemented.

Human-authored release history remains in `wiki/releases/v0.1-plan-active.md`.

## Generated verification block

Add one bounded block to `v0.1-plan-active.md`:

```text
<!-- BEGIN GENERATED V0.1 PLUGIN VERIFICATION -->
...
<!-- END GENERATED V0.1 PLUGIN VERIFICATION -->
```

A new deterministic script, `scripts/generate_release_status.py`, renders only this block.

The generated text must:

1. use the plugin IDs from `registry/v0.1.yaml`, not every registry plugin;
2. report aggregate plugin status by grouping exact canonical values from `registry/plugins.yaml`;
3. report each supported client’s status conservatively and explicitly;
4. identify live-verified client paths only when the client has `status: verified` and at least one referenced check resolves in `registry/verification-checks.yaml` to the same plugin/client with `kind: live` and `evidence_level: verified`;
5. never infer verification semantics from a check-ID naming prefix;
6. never infer that aggregate plugin status equals a client status;
7. render deterministically in v0.1 plugin order and stable client order;
8. fail clearly if a v0.1 plugin is missing from `plugins.yaml`, a referenced check is missing/mismatched, or expected verification/client metadata is absent.

For the current registry the prose should communicate, without hard-coded plugin names in the generator logic, that all four aggregate plugin statuses are `community`, Codex paths are `verified` with live evidence, and Claude paths remain `community` without equivalent live client-path evidence.

## Script interface

`python scripts/generate_release_status.py`

- reads canonical YAML;
- replaces only the bounded generated block;
- leaves all other bytes/content outside the block unchanged except normal final-newline handling;
- exits non-zero on malformed/missing markers or inconsistent canonical inputs.

`python scripts/generate_release_status.py --check`

- computes the expected block in memory;
- exits non-zero when the committed plan block differs;
- performs no write.

## Hand-authored plan reconciliation

Update only stale current-state sections:

- Phase 4: describe integrations as implemented, with verification scoped by the generated canonical summary instead of calling them globally Verified.
- Phase 5: mark the required v0.1 scholarly skill set implemented; describe future work as refinement/extension rather than `NEXT`.
- Phase 6: remove the hand-authored false aggregate `verified` claim and point to the generated block.
- Phase 7: mark installation and existing plugin/skill guidance as implemented; leave the compatibility matrix and other genuinely unfinished docs as pending.
- Current sequence and final “remaining work” summary: reconcile with those statuses.

Do not edit `v0.1-scope-frozen.md` merely to satisfy the old issue text; its TLHdig statement is already correct.

## TDD gates

### RED 1 — generated status contract

Add tests that fail before the script exists/works:

1. generator/checker exists and `--check` accepts current generated output;
2. rendering is derived from the v0.1 plugin set and exact registry aggregate/client statuses;
3. aggregate `community` + client `verified` never renders aggregate “verified”;
4. a verified client whose referenced checks are not canonically `kind: live` + `evidence_level: verified` is not described as live-verified;
5. a missing or plugin/client-mismatched referenced check fails closed;
6. missing v0.1 plugin/client verification metadata fails closed;
7. generation changes only the bounded block.

### RED 2 — stale plan semantics

Add focused document assertions that reject the known stale states:

- Phase 5 may not be labeled `NEXT` while the required-skill contract passes;
- plan may not contain the false current-state sentence that v0.1 aggregate plugin statuses are `verified`;
- Phase 4 may not state unscoped “implemented and Verified”.

These checks should encode semantic invariants, not a growing blacklist of historical prose.

### GREEN

Implement the generator, insert the generated block, reconcile the stale plan sections, and wire `--check` into Foundation.

### Test gate

Require on the implementation PR’s frozen head:

- Foundation green, including the new freshness check and unit regressions;
- any documentation/generator-specific tests green;
- no generated marketplace/catalog changes unless canonical inputs actually changed.

## Independent adversarial review checklist

Before finalization, review the frozen implementation head independently against:

- #16 acceptance criteria as rescoped by current repository state;
- `CONTRIBUTING.md` generated-artifact rules;
- whether the generator is genuinely registry-derived rather than hard-coded to the current four values;
- whether live evidence is joined through `registry/verification-checks.yaml` rather than inferred from IDs;
- whether “verified” can leak from one client into aggregate plugin prose;
- whether missing/unknown evidence fails closed;
- whether generation mutates hand-authored history outside its markers;
- whether stale Phase 5/7 prose remains elsewhere in the current sequence or definition-of-done summary;
- whether the change remains documentation/verification plumbing and does not alter plugin semantics.

## Completion criteria

#16 can close when the plan is current, the generated verification block exactly reflects canonical v0.1 registry evidence, Foundation enforces freshness, tests cover conservative status derivation, and the frozen implementation head passes independent adversarial review.