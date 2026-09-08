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
- `verification-checks.yaml` — stable executable check IDs and their unittest or GitHub Actions executors; checks may be client-scoped or directly bound to an exact resource/member subject.
- `providers.yaml` — scholarly/runtime backend metadata and operational-health evidence.
- `resources.yaml` — corpus and collection resources exposed through providers.
- `materializers.yaml` — immutable third-party materializer-plugin source/install records; currently includes `alexsosn/Pseudepigrapha-TF`.
- `vocabularies.yaml` — controlled vocabulary shared by the registries.
- `v0.1.yaml` — machine-readable fixed release scope and plugin ordering.
- `schema/` — JSON Schemas for canonical registry documents and the upstream materializer contract.
- `collections/` — member indexes for collection resources.

Collection indexes are complete, commit-bound discovery snapshots. Each index records an immutable `source_revision`; indexed members are discovered from that snapshot and acquired lazily only when selected. Member `verification.known_issues` entries are compact references to structured issue definitions on the parent resource, so snapshot-specific integration limitations can be surfaced before acquisition without rewriting upstream data.

## Corpus licensing evidence

`resources.yaml` records the licence or terms governing the **corpus data Agora actually exposes**, not merely the licence of the repository, converter, or other software around it. A root MIT/Unlicense file must not be copied into `licenses.data` unless upstream evidence explicitly applies it to the dataset. Public availability, open-access wording, or an ancient/public-domain source author likewise does not establish rights in a modern edition, transcription, translation, annotation layer, or database arrangement.

Every canonical `corpus` and `collection` therefore carries a reproducible `licenses.evidence` block:

```yaml
licenses:
  data: CC-BY-NC-4.0
  redistribution: restricted
  notes: Attribution and non-commercial conditions apply.
  evidence:
    status: resolved
    checked_at: "2026-09-06"
    sources:
      - https://github.com/ETCBC/bhsa/blob/master/README.md
```

The evidence status describes the state of the licensing research:

- `resolved` — upstream evidence supports a defensible top-level data licence/terms and redistribution conclusion;
- `component-specific` — materially different embedded components have different terms, so callers must read `licenses.notes` and the cited evidence;
- `member-specific` — a collection delegates rights information to individual members/files rather than one collection-wide licence;
- `unresolved` — authoritative sources were checked but no defensible top-level data licence or redistribution conclusion could be established.

`licenses.redistribution` remains deliberately small: `permitted` means redistribution is allowed by the recorded terms (possibly with attribution); `restricted` means a material restriction such as non-commercial or no-derivatives/source-specific conditions applies; `unknown` means research did not establish a safe conclusion or a heterogeneous resource cannot be summarized truthfully.

An `unknown` value is therefore a **researched unresolved state**, not a placeholder for work that has not been done. `unresolved`, `component-specific`, and `member-specific` records require explanatory notes plus dated evidence URLs. `member-specific` is valid only for collections. Feature modules are intentionally not required to carry separate evidence in this migration; a module whose terms materially differ from, or cannot safely inherit from, its parent corpus needs a later focused audit rather than an invented inheritance rule.

A materializer registry entry pins an immutable repository commit, expected upstream plugin identity/version, manifest path, package type/path, install-time trust class, and the exact materializer IDs expected in that manifest. `scripts/validate_registry.py` validates `materializers.yaml` alongside the other canonical files, including duplicate IDs and shared discipline/verification controlled vocabularies.

Registration supports passive source discovery. It does not mean Agora may automatically execute packaging code: Python materializer installation is an explicit trust action because PEP 517/build backends are executable third-party code. Resource → materializer → consumer composition remains a separate architecture step and must preserve that approval boundary.

## Executable verification evidence

Plugin/client and direct resource/member verification claims reference stable check IDs rather than prose test names. The check definition and a particular execution of that check are separate records:

- `registry/verification-checks.yaml` defines what can be executed and the maximum evidence level it can support;
- client checks bind a plugin, client, and transport, while direct checks bind a plugin/provider contract to an exact subject (`resource` or `collection-member`) and explicit claims;
- `registry/plugins.yaml` references client check IDs and records the configured source/runtime/dependency inputs the client claim is about;
- resource and collection-member `verification.evidence` entries reference direct check IDs; those references must resolve back to the same exact subject and plugin/provider contract;
- deterministic check IDs point to exact unittest targets;
- live check IDs point to a GitHub Actions workflow, job, matrix selector, and uploaded artifact.

Foundation validates that every referenced ID exists, is bound to the correct contract, points to an executable unittest or workflow job/matrix entry, and is strong enough for the status being claimed. A `verified` client therefore cannot be justified by a missing check or deterministic `community` evidence alone. Direct resource/member promotion is likewise fail-closed: ordinary corpora and collection members require live `verified` evidence for `materialization`, `load`, and `representative-content`; collection-level `verified` status requires its own live `verified` `discovery` evidence. A known-issue canary is negative health evidence and cannot substitute for those positive claims.

Known issues are scoped explicitly. `blocking` issues with `impact: resource` block promotion of that resource; `blocking` issues with `impact: member` block only members that reference the issue. `advisory` issues remain visible but do not automatically invalidate otherwise sufficient evidence. This keeps a known-bad collection member from downgrading unrelated healthy members or the whole collection while still failing closed for that exact subject.

A live check definition is not proof that its latest run succeeded. `scripts/smoke_mcp_plugin.py` embeds the stable check ID, UTC timestamp, exact Agora revision, GitHub run ID/attempt/URL when present, Python/platform/MCP SDK details, generated launch command, and the canonical verification inputs in each JSON smoke artifact. Resource/member load smoke artifacts likewise report the stable check ID, exact resource/member subject, immutable upstream source revision, selected TF path, and representative semantic assertions. GitHub Actions history and those artifacts provide the mutable run observations without hand-editing a `last_successful_run` value into the registry after every schedule.

Provider health may reference the same stable live check IDs as operational observations, but the check must explicitly name the exact provider it traverses and provider health does not inherit the check's client evidence level. A successful Codex-path check can therefore show that one provider/runtime was observed working on that run without asserting that Claude has equivalent evidence, another provider under the same plugin was tested, or the provider's resources are scholarly-quality.

The current live client workflow verifies generated Codex paths and targeted Claude/platform paths according to their canonical check definitions. Resource/member load evidence is produced separately by the Context-Fabric representative-load workflow so client transport evidence and corpus loadability remain distinct claims.

## Reproducible runtime dependency environments

Verification evidence is bound to the dependency environment it actually describes. File-backed environments in `registry/plugins.yaml` record both a repository-relative path and the SHA-256 digest of that exact lock or constraint snapshot. Live Codex checks additionally record the `verification/mcp-smoke/uv.lock` harness environment, so the evidence-producing process is identified separately from the plugin environment being tested. Sefaria's direct hosted Claude path uses `environment.kind: hosted` because Agora does not resolve a local Python environment for that transport.

Agora uses two dependency strategies according to ownership:

- Agora-owned local Python runtimes (`context-fabric` and `sedra`) commit universal `uv.lock` files next to their `pyproject.toml` files and launch with `uv run --locked`. A changed project declaration with an unchanged lock therefore fails closed instead of silently re-resolving at user launch.
- Third-party `uvx` integrations (`perseus` and the Sefaria Codex proxy) keep the advertised top-level package pins while shipping full universal transitive snapshots in `runtime-constraints.txt`, generated from the corresponding `runtime-requirements.in`. Their generated launch commands pass those snapshots with `uvx --constraint`. Sefaria's source declaration still explicitly requires `mcp>=1.17,<2`, and the resolved snapshot keeps the proxy on MCP SDK 1.x.
- The live smoke harness is its own small uv project under `verification/mcp-smoke/`. GitHub Actions runs it with `uv run --project verification/mcp-smoke --locked` rather than dynamically injecting `mcp` or PyYAML at verification time.

The canonical snapshot producer/checker tool version is uv `0.12.10`. Foundation runs `scripts/check_runtime_environment_freshness.py`: project locks are checked with `uv lock --check`, while each `runtime-constraints.txt` is recompiled from its source declaration **under the committed snapshot as a constraint** and byte-compared with the committed result. This distinction is deliberate. A newly published transitive package version on PyPI does not make a frozen, still-valid environment stale; changing the declared dependency contract so that the committed snapshot no longer satisfies or completely represents it does.

`scripts/validate_runtime_environments.py`, invoked by the canonical registry validator, independently verifies that every referenced file exists and that its current SHA-256 matches the registry claim. Together, semantic freshness and digest identity prevent both stale declarations and unrecorded snapshot edits.

The live smoke workflow watches every relevant local `pyproject.toml`/`uv.lock`, every uvx `runtime-requirements.in`/`runtime-constraints.txt`, and the harness project/lock. Changing any of those inputs therefore produces a new live observation instead of silently retaining an unrelated verified run. The JSON smoke artifact records the pinned uv version, generated user launch, plugin dependency snapshot identity, and harness snapshot identity used for that run.

## Three independent status dimensions

**Provider/service health** is a recorded operational observation about a specific provider/runtime path. The controlled values are:

- `unknown` — Agora makes no operational claim; live evidence is not required;
- `observed-operational` — a provider-scoped live check has observed the advertised path working;
- `degraded` — provider-scoped live evidence records that the advertised operational path is materially impaired but not wholly unavailable;
- `unavailable` — provider-scoped live evidence records that the advertised operational path could not be used.

Every non-`unknown` provider-health claim requires at least one exact-provider live evidence reference. These labels summarize recorded observations and are not automatic real-time monitoring or an uptime guarantee; later workflow runs and their artifacts are the mutable observations that maintainers should consult when current state matters.

**Plugin/client integration evidence** records how strongly a particular Claude or Codex transport path has been tested. The `experimental` / `community` / `verified` ladder belongs here, and the plugin aggregate remains the weakest client status.

**Resource/member verification evidence** records loadability and representative-content evidence for one exact resource or collection member, independently from provider health and client integration. Resource/member `verification.evidence` must reference direct checks for the exact subject. A verified member does not promote its parent collection, a verified resource does not promote its provider or plugin, and a verified client path does not promote resources behind that plugin. Provenance, licensing, annotation richness, and broader scholarly suitability also remain separate metadata and are not inferred from load verification.

These dimensions are intentionally not synchronized. A provider can have `observed-operational` health while the aggregate plugin remains `community`; a resource or member can have stronger or weaker direct evidence than either of those layers. Trust is promoted only where the canonical evidence is explicitly bound.

## Validation

Run:

```bash
python -m pip install -r requirements-dev.txt
python scripts/validate_registry.py
python scripts/agora_install_materializer.py list
python scripts/generate_marketplaces.py --check
python -m unittest discover -s tests -v
```

For the networked dependency-snapshot freshness gate, install uv `0.12.10` and run:

```bash
python scripts/check_runtime_environment_freshness.py
```

Validation checks schema conformance, duplicate IDs, cross-file references, executable verification-check references, exact resource/member evidence binding and promotion gates, runtime-environment file/digest identity, exact-provider evidence for every asserted provider-health state, controlled-vocabulary values, collection/index consistency, the exact four-plugin / 37-resource v0.1 contract, materializer registry constraints, corpus licensing evidence invariants, and freshness of committed Claude/Codex marketplace artifacts. Foundation additionally verifies the semantic freshness of all committed runtime dependency snapshots.

CI also performs a live Pseudepigrapha-TF integration smoke in two phases: passive immutable source fetch/manifest validation, then a separately explicit Python installation that records runtime and dependency identity. Materializer registration and verification do not assess upstream scholarly suitability or converter semantics.

The human-readable release baseline is documented under [`../wiki/releases/`](../wiki/releases/).
