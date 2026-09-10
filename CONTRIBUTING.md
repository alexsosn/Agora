# Contributing to Agora

Agora is a clean-slate, thin plugin marketplace for philology and related disciplines.

## Architectural boundary

Agora owns **discovery, description, installation, launch/integration, compatibility metadata, and marketplace UX** for third-party plugins. It does not own the domain behavior of those plugins.

The normative boundary is documented in [`wiki/architecture/ref-plugin-boundary.md`](wiki/architecture/ref-plugin-boundary.md). Read it before changing anything under `plugins/`, adding plugin-specific tests, or adding skills.

A useful ownership test is:

> If the same bug or missing capability is present when the third-party plugin is run directly without Agora, the fix normally belongs upstream.

Accordingly, do not use Agora to:

- monkey-patch or override third-party tool behavior;
- fix incorrect search, counting, parsing, ranking, morphology, retrieval, or other domain semantics inside an upstream plugin;
- add tools, query modes, data transformations, or research capabilities that the upstream plugin does not provide;
- depend on private upstream internals merely to repair or extend upstream behavior;
- duplicate upstream behavioral test suites in Agora.

When an upstream plugin is buggy, prefer to report/link the upstream issue and direct users to authoritative upstream documentation. Constrain or pin a known-good upstream version when required for integration compatibility, and remove or downgrade Agora integration claims that the bug invalidates. Do not copy mutable upstream suitability or data-quality assessments into Agora metadata or documentation.

Thin adaptation is allowed when it is necessary for Agora-owned integration concerns such as installation, process launch, transport bridging, client configuration, resource discovery, or mapping canonical registry metadata into a plugin's supported public interface. Such adapters must preserve upstream semantics and responses rather than silently redefining them.

## Skill ownership

Skills that implement or teach the substantive capabilities of a third-party plugin belong with that plugin upstream whenever practical.

Agora may contain skills only when they are one of these:

1. **generic marketplace skills** that work across plugins, such as discovery, selection, installation, or orchestration guidance;
2. **plugin-facilitation skills** packaged with an Agora plugin integration that help an agent use capabilities the upstream plugin already exposes, such as identifier discovery, tool-selection guidance, configuration, Agora-owned integration limitations, upstream-documentation discovery, or reproducibility conventions;
3. **repository-maintenance skills** under `.agents/skills/`, which guide contributors and coding agents working on Agora itself and are not scholarly capabilities shipped by a third-party plugin.

An Agora skill must not compensate for a missing upstream tool, repair an upstream result, synthesize a new domain capability, turn an unsupported workflow into an apparently supported one, or restate mutable upstream suitability and data-quality guidance. Link to the authoritative upstream documentation instead.

## Project rule

`mcp-demo` is prior art, not a compatibility target. Code, metadata, tests, and integration knowledge may be reused where their licenses permit, but new Agora components should follow Agora's own plugin and registry architecture. Do not add compatibility shims, legacy paths, or workshop-specific behavior solely to preserve `mcp-demo` interfaces.

## Repository areas

- `registry/` — canonical marketplace, plugin, provider, resource, and release metadata and schemas.
- `plugins/` — thin Agora integration packages, generated native manifests, and permitted plugin-facilitation skills.
- `.agents/skills/` — repo-maintenance workflows for coding agents; not third-party scholarly capabilities.
- `profiles/` — optional curated plugin/resource bundles.
- `scripts/` — repository tooling, generators, and validators.
- `tests/` — tests of Agora-owned registry, packaging, launch, transport, and integration contracts.
- `generated/` — reserved for generated artifacts without client-mandated native paths.
- `wiki/` — design, research, release, backlog, and review notes.

The current architecture references are indexed in [`wiki/README.md`](wiki/README.md).

## Testing boundary

Agora tests should prove Agora claims: registry validity, generated metadata, installation/launch configuration, transport compatibility, tool discovery, resource resolution owned by Agora, and smoke-level evidence that the advertised integration can perform a representative published operation.

A smoke operation is evidence that the integration reaches the upstream service; it is not an invitation to reproduce upstream's semantic test suite. When a test would primarily prove that a third-party algorithm or scholarly operation is correct, that test and its fix belong upstream.

## Development and review gates

Agora uses TDD for behavior changes and logically independent adversarial review for finalized pull requests. The amount of ceremony and CI must be proportional to the risk and scope of the change.

### High-risk changes

Runtime execution, sandbox/trust boundaries, acquisition integrity, cache/data integrity, destructive operations, concurrency, and changes that can cause resource exhaustion should receive the full evidence path appropriate to the risk:

1. reproduce and research the current behavior and the relevant source contracts;
2. write a plan when the change crosses components or requires a material design choice;
3. preserve a focused failing regression before the production fix;
4. implement the smallest change that satisfies the stated user contract;
5. run focused tests plus the directly relevant integration/end-to-end gates and Foundation;
6. independently review the frozen final head.

The research and plan may be concise, but they should make unresolved assumptions explicit.

### Ordinary bug fixes

For a localized Agora-owned bug, reproduce the user-visible failure, add a focused regression, implement the fix, run affected tests and Foundation where applicable, then independently review the final head. A separate research document, design document, or dedicated preserved RED commit is optional unless it provides real evidence or resolves uncertainty.

### Registry, version, and generated-metadata changes

For a bounded metadata or upstream-version change:

- verify the authoritative upstream identity and the fields Agora owns;
- change the canonical registry source rather than generated projections;
- regenerate client-native artifacts;
- run schema/generation checks and a directly relevant launch/install smoke when the executable pin changed;
- independently review the final head for identity drift, accidental scope expansion, and stale generated artifacts.

Do not require a broad architecture study, unrelated platform matrix, or full materialization suite for a metadata-only change unless the changed metadata can affect those paths.

### Documentation-only changes

Verify commands, links, client names, version claims, and limitations against current behavior. Run lightweight documentation or generated-artifact checks where relevant. Runtime RED/GREEN history and unrelated live smokes are unnecessary.

### Review findings and scope control

Review should challenge the PR's stated contract, user impact, regressions, and architectural boundary. A finding should block or expand the current PR only when it affects that contract, safety, correctness, or the active release criteria.

Other useful findings should be recorded as follow-up work without becoming prerequisites for the current PR. During Agora 1.0 release mode, post-release findings must not displace the active release queue in [#148](https://github.com/alexsosn/Agora/issues/148).

## Generated files

Claude Code and ChatGPT/Codex marketplace/plugin metadata is generated from the canonical registry:

```bash
python scripts/generate_marketplaces.py
```

Do not hand-edit:

- `.claude-plugin/marketplace.json`;
- `.agents/plugins/marketplace.json`;
- `plugins/*/.claude-plugin/plugin.json`;
- `plugins/*/.codex-plugin/plugin.json`.

Change the canonical registry or generator and regenerate instead. CI enforces freshness with:

```bash
python scripts/generate_marketplaces.py --check
```

Antigravity artifacts are not part of the current v0.1 generation target.

## Before opening a PR

For plugin-related work, state explicitly which Agora-owned responsibility the change serves. If the motivation is an upstream bug or missing feature, link the upstream report and keep the Agora change to metadata, version constraints, integration glue, or documentation unless the problem is genuinely caused by Agora itself.

During the Agora 1.0 release cycle, state whether the PR serves an item in [#148](https://github.com/alexsosn/Agora/issues/148). If it does not, explain why it should consume pre-release review and CI capacity instead of remaining post-1.0.
