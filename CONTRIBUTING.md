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

When an upstream plugin is buggy, prefer to report/link the upstream issue, record the limitation in Agora metadata/documentation, constrain or pin a known-good upstream version when one exists, and remove or downgrade verification claims that the bug invalidates.

Thin adaptation is allowed when it is necessary for Agora-owned integration concerns such as installation, process launch, transport bridging, client configuration, resource discovery, or mapping canonical registry metadata into a plugin's supported public interface. Such adapters must preserve upstream semantics and responses rather than silently redefining them.

## Skill ownership

Skills that implement or teach the substantive capabilities of a third-party plugin belong with that plugin upstream whenever practical.

Agora may contain skills only when they are one of these:

1. **generic marketplace skills** that work across plugins, such as discovery, selection, installation, or orchestration guidance;
2. **plugin-facilitation skills** packaged with an Agora plugin integration that help an agent use capabilities the upstream plugin already exposes, such as identifier discovery, tool-selection guidance, configuration, limitations, or reproducibility conventions;
3. **repository-maintenance skills** under `.agents/skills/`, which guide contributors and coding agents working on Agora itself and are not scholarly capabilities shipped by a third-party plugin.

An Agora skill must not compensate for a missing upstream tool, repair an upstream result, synthesize a new domain capability, or turn an unsupported workflow into an apparently supported one.

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
