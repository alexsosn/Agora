# Research: provider/service status versus client integration status

Issue: #12

## Question

Agora currently forces `provider.verification.status` to equal the aggregate plugin verification status. That makes one value answer three different questions:

1. did a provider/service respond operationally;
2. does a particular Agora client/transport integration have strong executable evidence;
3. are the resources/data behind that provider suitable or reliable for scholarship.

Those dimensions are independent and should not share one status ladder.

## Current state

- `registry/plugins.yaml` uses `experimental` / `community` / `verified` as an **integration-evidence strength** ladder.
- Plugin aggregate status is deliberately the weakest client status; current Codex paths have live `verified` evidence while Claude paths have deterministic `community` evidence.
- `registry/providers.yaml` repeats `community` for all four providers.
- `scripts/validate_registry.py` requires provider status to equal plugin aggregate status.
- `registry/resources.yaml` already carries resource-level verification/known-issue metadata separately.
- PR #54 / issue #11 introduced stable executable check IDs and traceable live smoke artifacts. Those live checks can also prove that a provider/runtime was observed operational during a specific run, without changing what the plugin/client status means.

## Ownership

This is Agora-owned registry and verification metadata. It does not alter upstream scholarly behavior or repair third-party services. Provider health checks and integration smoke evidence are explicitly within the thin-marketplace boundary.

## Model considered

### Reusing `experimental/community/verified` for providers

Rejected. Those terms already mean evidence strength at the plugin/client layer. Reusing them for service health invites false implications such as:

- a `verified` provider means Claude works;
- a `verified` provider means its corpora are high quality;
- a `community` provider is operationally weaker merely because one client path lacks live automation.

### A separate provider-health vocabulary

Preferred. Provider state should describe an operational observation, not an evidence prestige level:

- `unknown` — no current operational observation is claimed;
- `observed-operational` — at least one executable live check has successfully traversed the provider/runtime in recorded CI evidence;
- `degraded` — provider/service is known to be reachable but an Agora-owned operational path is materially impaired;
- `unavailable` — provider/service is known unavailable for the advertised operational path.

`degraded` and `unavailable` are operational states only. Upstream semantic/search/data defects must remain upstream issues and must not be converted into provider-health judgements unless they make the advertised service path operationally unusable.

## Evidence shape

Provider health should carry explicit evidence references. For v0.1 providers, the existing live Codex smoke checks are sufficient evidence for `observed-operational` because each actually traverses the provider/runtime:

- Context-Fabric: initializes the Agora/Context-Fabric runtime and calls a registered tool;
- Perseus: performs a real upstream discovery operation;
- Sefaria: traverses the stdio/SSE bridge to the hosted service and retrieves a real text;
- SEDRA: performs a real SEDRA lookup.

A provider-health evidence record should therefore reference a stable `check_id` from `registry/verification-checks.yaml`. The provider layer does **not** inherit the check's client evidence level. The reference only says that this live check supplies an operational observation.

For `observed-operational`, validation should require at least one referenced executable check whose `kind` is `live` and whose `plugin` matches the provider's plugin. This preserves traceability without coupling provider status to a particular client status.

The mutable successful-run observation remains in GitHub Actions history/artifacts, as established by #11; `providers.yaml` should not hand-maintain a `last_successful_run` field.

## Cross-layer invariants

Validation should continue to enforce:

- provider → plugin reference exists;
- resource → provider reference exists;
- resource plugin matches provider plugin;
- provider health status is in a provider-specific vocabulary;
- provider operational evidence IDs exist and are live executable checks for the same plugin.

Validation should no longer enforce:

- provider health equals plugin aggregate verification status;
- resource verification status follows provider health;
- provider health follows the strongest or weakest client integration status.

## User-facing semantics

Documentation should describe three independent dimensions:

1. **Provider/service health** — whether an operational provider/runtime path has been observed working, with traceable live evidence.
2. **Plugin/client integration evidence** — whether a specific Claude/Codex transport path has deterministic or live executable evidence; aggregate plugin status remains the weakest client path.
3. **Resource/data status** — resource-specific loadability, provenance, licensing, known issues, and other resource-level claims; no provider or client status establishes scholarly suitability.

The README should keep its current warning that Agora verification does not assess scholarly suitability and add this dimensional distinction rather than another badge table.

## Scope boundaries

This ticket should not:

- add resource/member executable evidence (#19);
- lock dependency environments (#14);
- add broader platform/client matrices (#18);
- implement real-time service monitoring;
- classify known upstream semantic defects as provider health problems.

## Recommended implementation

1. Add `provider_health_statuses` to controlled vocabularies.
2. Replace provider `verification` with a provider-specific `health` object containing `status`, `evidence`, and optional notes.
3. Reference existing live check IDs as operational evidence for the four v0.1 providers.
4. Update provider schema and validator to validate health independently and remove equality with plugin aggregate status.
5. Add regressions for legitimate provider/plugin divergence, missing/mismatched/non-live provider evidence, and preserved reference integrity.
6. Document the three dimensions in `registry/README.md` and the user-facing verification section.
