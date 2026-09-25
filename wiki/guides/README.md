# Agora researcher user guide

Use this page to choose the shortest path for a research task. You can start here without learning Agora's internal implementation vocabulary.

| I want to… | Start here |
|---|---|
| **Get started** | [Install the plugin you need](installation.md) |
| **Browse plugins** | [Choose a plugin by research task](../../README.md#choosing-a-plugin) |
| **Browse resources** | [Browse the resource catalog](resources.md) |
| **Research tutorials / recipes** | [Start from the current example prompts](../../README.md#example-prompts) |
| **Compatibility** | [Check client, platform, and known limitations](compatibility.md) |
| **Troubleshooting** | [Start from the symptom you see](#troubleshooting) |

## How Agora fits together

```text
Agora marketplace
├─ Context-Fabric plugin → scholarly resources/corpora (for example BHSA)
├─ Perseus plugin → Perseus/Scaife service
├─ Sefaria plugin → Sefaria service
└─ SEDRA plugin → SEDRA IV service
```

- **Marketplace** — the place from which you discover and install Agora plugins.
- **Plugin** — an installable integration that gives the agent access to a scholarly tool or service.
- **Resource/corpus** — a scholarly dataset selected through a plugin when that plugin offers multiple datasets.
- **Skill** — research guidance used by the agent to apply existing plugin/resource capabilities and conventions correctly.

For BHSA, **install Context-Fabric**. BHSA is a corpus/resource, **not a plugin**. Perseus, Sefaria, and SEDRA usually work by installing their plugin and using the corresponding remote service directly.

## Get started

If you already know which plugin you need, follow the [installation guide](installation.md). It covers Claude Code, managed ChatGPT/Codex workspace import, local Codex testing, prerequisites, updates, and removal.

If you are not sure which plugin fits the question, use [Choose a plugin](../../README.md#choosing-a-plugin) first. After installation, the current [example prompts](../../README.md#example-prompts) give small starting requests for Context-Fabric, Perseus, Sefaria, and SEDRA.

## Browse plugins

The current [plugin chooser](../../README.md#choosing-a-plugin) maps common research tasks to the four plugin families without requiring internal marketplace terminology. For a pre-install decision, open the matching detail page:

- [Context-Fabric](plugins/context-fabric.md)
- [Perseus](plugins/perseus.md)
- [Sefaria](plugins/sefaria.md)
- [SEDRA](plugins/sedra.md)

Each page uses the same structure for capabilities, local/remote behavior, installation, first success, limitations, costs, licensing, troubleshooting, and upstream links.

## Browse resources

Use the [generated scholarly resource catalog](resources.md) to browse the current Context-Fabric corpora and collections by recognizable name, language, discipline, period, rights, integration status, and recorded load cost where available.

Installing Context-Fabric does not download every corpus. Collection members are discovered after installation rather than copied wholesale into the static catalog. For an unfamiliar or potentially large corpus, use the [safe first-load workflow](context-fabric-cache.md#recommended-first-load-workflow) before loading it.

Perseus, Sefaria, and SEDRA primarily expose remote scholarly services rather than the same local corpus-selection model, so resource selection differs by plugin.

## Research tutorials / recipes

The current [example prompts](../../README.md#example-prompts) are starting points, not full step-by-step tutorials. They show the intended level of research request while preserving source-specific caveats such as schema inspection and ambiguity handling.

For Context-Fabric, the [cache and cold-load guide](context-fabric-cache.md) also documents the recommended `describe → prepare → load` workflow for unfamiliar or expensive corpora. More complete first-success walkthroughs can be added without changing the installation or compatibility contracts.

## Compatibility

Use [Client and platform compatibility evidence](compatibility.md) when you need to know whether a plugin/client/platform path is currently supported or which upstream limitations affect interpretation.

Compatibility evidence describes integration/runtime observations. It does not certify the scholarly quality or suitability of an upstream corpus, edition, annotation layer, or service.

## Troubleshooting

Start with the observable symptom rather than the internal component name:

- plugin is missing, will not launch, `uv`/Python cannot be resolved, a remote lookup fails, or a ChatGPT surface does not expose the plugin → [installation troubleshooting](installation.md#troubleshooting);
- Context-Fabric acquisition or compilation is slow, disk use is high, a load is already active, or you need to cancel/clean cache objects → [Context-Fabric cache and cold-load safety](context-fabric-cache.md);
- a plugin or remote service has a known limitation, or you need the exact tested client/platform boundary → [compatibility and known limitations](compatibility.md#current-upstream-limitations).

A remote-service outage or upstream defect is not repaired by reinstalling Agora. Preserve the original error and follow the upstream/service guidance linked from the relevant page.

## Returning users

For updates and removal, use the host-owned flows in [Updating](installation.md#updating) and [Removing](installation.md#removing). Removing the Context-Fabric plugin does not automatically delete corpus cache data; use the cache tools described in the [cache guide](context-fabric-cache.md) when you actually want to reclaim it.

For reproducible corpus work, record the selected resource/version or source revision, the relevant feature names, and the counted unit or query definition rather than relying on an informal result description.

## Project and contributor documentation

Researcher workflows above are the primary documentation path. Repository architecture, release planning, backlog, and historical reviews remain available through the [project wiki index](../README.md). Contributors should start with [CONTRIBUTING.md](../../CONTRIBUTING.md).
