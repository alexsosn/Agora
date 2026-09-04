# Plan: provider/service status separation

Issue: #12

Research: `wiki/backlog/P1-research-provider-service-status.md`

## Goal

Make provider/service operational health independent from plugin/client verification evidence while preserving strict registry references and keeping resource/data status separate.

## Scope

### In scope

- provider-specific health vocabulary and schema;
- provider health evidence references to executable live checks;
- independent provider validation;
- removal of provider == plugin aggregate status coupling;
- tests for divergence and invalid provider evidence;
- README/registry documentation of the three independent dimensions.

### Out of scope

- resource/member executable evidence (#19);
- dependency lockfiles/resolved environment recording (#14);
- new platform/client coverage (#18);
- real-time availability monitoring;
- upstream semantic fixes or data-quality scoring.

## TDD gates

### RED 1 — provider health is a distinct registry contract

Add tests that require:

1. providers use `health`, not plugin-style `verification`;
2. `health.status` accepts only provider-health vocabulary values;
3. a provider may be `observed-operational` while its linked plugin aggregate remains `community`;
4. removing/mangling the provider→plugin reference is still rejected.

Expected current failure: providers still expose `verification.status: community`, the schema has no `health`, and validator enforces equality.

### GREEN 1 — schema/vocabulary/registry migration

- add `provider_health_statuses` to `registry/vocabularies.yaml`;
- update `providers.schema.json` to require `health`;
- migrate all four providers to `health.status: observed-operational` with live evidence references;
- remove provider/plugin equality validation;
- validate provider-health vocabulary independently.

### RED 2 — health evidence must be executable and layer-appropriate

Add mutation tests proving validation rejects:

- missing provider evidence check ID;
- deterministic-only check used to justify `observed-operational`;
- live check belonging to a different plugin;
- `observed-operational` with no evidence.

Expected current failure after GREEN 1 unless evidence validation is implemented.

### GREEN 2 — provider evidence validation

Load the canonical check catalog and require each `observed-operational` evidence reference to:

- exist;
- be `kind: live`;
- match the provider's plugin.

Do not compare or inherit client/evidence-level status.

For `unknown`, evidence may be absent. `degraded`/`unavailable` remain allowed operational states with notes/evidence but are not used for current v0.1 providers in this ticket.

### RED 3 — documentation must preserve dimensional separation

Add a focused documentation regression asserting the canonical registry documentation names and distinguishes:

- provider/service health;
- plugin/client integration evidence;
- resource/data status.

Also assert user-facing verification prose does not claim provider health implies resource quality or all-client verification.

### GREEN 3 — documentation

Update:

- `registry/README.md` with provider-health semantics/evidence;
- `README.md` verification scope with the three-layer distinction.

No broad release-plan cleanup; #16 owns unrelated documentation drift.

## Full test gate

Before review:

- `python scripts/validate_registry.py`;
- `python scripts/generate_marketplaces.py --check`;
- `python -m unittest discover -s tests -v`;
- Foundation CI on the PR head.

If provider registry changes trigger live smoke CI, require the live checks to pass on the final head as supporting provider-health evidence.

## Independent review gate

After all tests are green, review the exact PR head independently using:

- `AGENTS.md`;
- `CONTRIBUTING.md`;
- `.agents/skills/agora-pr-review/SKILL.md`;
- `.agents/skills/agora-plugin-review/SKILL.md` because provider/plugin metadata is touched;
- `wiki/architecture/ref-plugin-boundary.md`;
- issue #12 acceptance criteria.

Review specifically for:

- accidental re-coupling of provider health to a client status/evidence level;
- using provider health as scholarly/resource quality;
- accepting non-live or cross-plugin evidence;
- overclaiming current real-time availability from historical observations;
- scope creep into #14/#18/#19.

If review finds a blocker, add a regression first when applicable, fix it, rerun the full gate, and repeat independent review on the new exact head. Merge only a reviewed green SHA.
