# Registry

This directory contains Agora's canonical machine-readable marketplace metadata and schemas.

Phase 1 is implemented around the fixed v0.1 scope:

- four MCP plugin families: `context-fabric`, `perseus`, `sefaria`, and `sedra`;
- four provider records;
- 35 resources from the Context-Fabric corpus catalog snapshot;
- `alexsosn/TLHdig-TF` as the 36th Context-Fabric resource;
- `ETCBC/targum` as the 37th Context-Fabric resource;
- explicit collection handling for `pthu/bible`, `pthu/patristics`, and `pthu/greek_literature`.

Experimental materializer plugins are registered separately from the frozen v0.1 MCP marketplace scope. This keeps third-party converter installation metadata distinct from MCP plugin/provider metadata and does not imply that a materialized corpus is already wired into a consumer.

## Canonical files

- `marketplace.yaml` — platform-neutral Agora marketplace/publisher metadata used by Phase 2 generators.
- `plugins.yaml` — installable MCP plugin/integration metadata and client-scoped verification references.
- `verification-checks.yaml` — stable executable check IDs and their unittest or GitHub Actions executors; live checks may also name the provider they actually observe.
- `providers.yaml` — scholarly/runtime backend metadata and operational-health evidence.
- `resources.yaml` — corpus and collection resources exposed through providers.
- `materializers.yaml` — immutable third-party materializer-plugin source/install records; currently includes `alexsosn/Pseudepigrapha-TF`.
- `vocabularies.yaml` — controlled vocabulary shared by the registries.
- `v0.1.yaml` — machine-readable fixed release scope and plugin ordering.
- `schema/` — JSON Schemas for canonical registry documents and the upstream materializer contract.
- `collections/` — member indexes for collection resources.

The collection indexes are intentionally dynamic: their schema and references are stable, while current members are discovered lazily from upstream Git tree metadata.

A materializer registry entry pins an immutable repository commit, expected upstream plugin identity/version, manifest path, package type/path, install-time trust class, and the exact materializer IDs expected in that manifest. `scripts/validate_registry.py` validates `materializers.yaml` alongside the other canonical files, including duplicate IDs and shared discipline/verification controlled vocabularies.

Registration supports passive source discovery. It does not mean Agora may automatically execute packaging code: Python materializer installation is an explicit trust action because PEP 517/build backends are executable third-party code. Resource → materializer → consumer composition remains a separate architecture step and must preserve that approval boundary.

## Executable verification evidence

Plugin/client verification claims reference stable check IDs rather than prose test names. The check definition and a particular execution of that check are separate records:

- `registry/verification-checks.yaml` defines what can be executed, which plugin/client/transport it verifies, and the maximum evidence level it can support;
- `registry/plugins.yaml` references those IDs and records the configured source/runtime/dependency inputs the claim is about;
- deterministic check IDs point to exact unittest targets;
- live check IDs point to a GitHub Actions workflow, job, matrix selector, and uploaded artifact.

Foundation validates that every referenced ID exists, matches the plugin/client/transport evidence contract, points to an executable unittest or workflow job/matrix entry, and is strong enough for the client status being claimed. A `verified` client therefore cannot be justified by a missing check or by deterministic `community` evidence alone. The plugin aggregate status remains the weakest client status.

A live check definition is not proof that its latest run succeeded. `scripts/smoke_mcp_plugin.py` embeds the stable check ID, UTC timestamp, exact Agora revision, GitHub run ID/attempt/URL when present, Python/platform/MCP SDK details, generated launch command, and the canonical verification inputs in each JSON smoke artifact. GitHub Actions history and those artifacts provide the mutable run observations without hand-editing a `last_successful_run` value into the registry after every schedule.

Provider health may reference the same stable live check IDs as operational observations, but the check must explicitly name the exact provider it traverses and provider health does not inherit the check's client evidence level. A successful Codex-path check can therefore show that one provider/runtime was observed working on that run without asserting that Claude has equivalent evidence, another provider under the same plugin was tested, or the provider's resources are scholarly-quality.

The current live workflow verifies the generated Codex path. Claude launch/configuration checks are deterministic and remain `community`; broader client/platform coverage belongs to the compatibility work tracked separately. Fully resolved dependency locking is also separate work—the evidence records capture the configured resolution inputs and the observed runtime, while lockfiles/constraints are handled by the reproducibility workstream.

## Three independent status dimensions

**Provider/service health** records an operational observation about the provider/runtime path. `observed-operational` means at least one live executable check explicitly scoped to that provider supplies traceable run evidence. It is not a real-time uptime guarantee and does not rank scholarly quality.

**Plugin/client integration evidence** records how strongly a particular Claude or Codex transport path has been tested. The `experimental` / `community` / `verified` ladder belongs here, and the plugin aggregate remains the weakest client status.

**Resource/data status** remains resource-specific. Loadability, provenance, licensing, known issues, annotations, and scholarly suitability are not inferred from provider health or client integration evidence. Resource/member executable evidence is a separate trust-layer workstream.

These dimensions are intentionally not synchronized. A provider can have `observed-operational` health while the aggregate plugin remains `community`, and neither statement promotes the resources behind that provider.

## Validation

Run:

```bash
python -m pip install -r requirements-dev.txt
python scripts/validate_registry.py
python scripts/agora_install_materializer.py list
python scripts/generate_marketplaces.py --check
python -m unittest discover -s tests -v
```

Validation checks schema conformance, duplicate IDs, cross-file references, executable verification-check references, exact-provider health evidence, controlled-vocabulary values, collection/index consistency, the exact four-plugin / 37-resource v0.1 contract, materializer registry constraints, and freshness of committed Claude/Codex marketplace artifacts.

CI also performs a live Pseudepigrapha-TF integration smoke in two phases: passive immutable source fetch/manifest validation, then a separately explicit Python installation that records runtime and dependency identity. Materializer registration and verification do not assess upstream scholarly suitability or converter semantics.

The human-readable release baseline is documented under [`../wiki/releases/`](../wiki/releases/).
