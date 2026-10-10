# Context-Fabric

Load, inspect, and query Text-Fabric-format corpora through Context-Fabric MCP.

## Use this plugin for

- **Corpus discovery** (`corpus-discovery`)
- **Corpus acquisition** (`corpus-acquisition`)
- **Corpus loading** (`corpus-loading`)
- **Structured search** (`structured-search`)
- **Feature inspection** (`feature-inspection`)

## Access and resources

Browse the [generated scholarly resource catalog](../resources.md) for registered corpora and collections. Resources are selected lazily; installing the plugin does not download the full catalog. Use `install_local_corpus` for [user-supplied native TF corpora and feature modules](../context-fabric-local-import.md).

## What connects or runs

Agora bundles resource discovery and lazy acquisition around cfabric-mcp 0.1.7; corpora remain external and are materialized only when selected.

## Local and remote behavior

Runtime mode: `local`.
Data mode: `local`.
Runtime type: `python`.

## Prerequisites

Use the [installation guide](../installation.md) for current host prerequisites and supported installation paths. Keep client/platform support decisions separate from the plugin's scholarly capabilities; consult the [compatibility guide](../compatibility.md).

## Install

Install `context-fabric@agora` through a supported Agora host. Follow the [short installation path](../installation.md) rather than copying host UI steps from this page.

## First success

> Using BHSA, inspect the available word features, then find a small set of occurrences of the lexeme MLK and report the exact features used.

This is a bounded starting request, not a full tutorial. The first-success tutorial workstream can expand it without changing this page's capability contract.

## Typical research tasks

Before constructing a corpus query, inspect the selected schema and annotation. Agent-side workflow guidance lives in the [generic Context-Fabric research skill](../../../plugins/context-fabric/skills/context-fabric-research/SKILL.md); resource-specific BHSA, Ugaritic, Hittite, and Greek-collection skills remain alongside it.

Canonical capabilities:

- **Corpus discovery** (`corpus-discovery`)
- **Corpus acquisition** (`corpus-acquisition`)
- **Corpus loading** (`corpus-loading`)
- **Structured search** (`structured-search`)
- **Feature inspection** (`feature-inspection`)

## Registered BHSA cantillation module

The optional `bhsa-cantillation-trees` feature module attaches verse-level cantillation annotations to the **existing BHSA 2021** parent. It is not a separate corpus and does not require another BHSA download. Inspect `describe_available_corpus(resource_id="bhsa")`, then use the same parent and module selection for both preparation and load:

```text
prepare_corpus(resource_id="bhsa", version="2021", modules=["bhsa-cantillation-trees"])
load_corpus(resource_id="bhsa", version="2021", modules=["bhsa-cantillation-trees"], features=["g_cons", "cantillation_system", "cantillation_depth", "cantillation_alignment"])
```

Inspect the loaded schema and actual feature values before interpreting them. The live 10 October 2026 acceptance verified BHSA Genesis 1:1 words and cantillation `system=prose`, `depth=2`, and `alignment=exact` on BHSA verse node `1414389`; these are representative checks, **not** an audit of all verse alignments. The module's `sources.json` records the BHSA source commit `4db00e2157915495e1a4d3d57e41223df24775da`; the tested module source revision is `445413fa5267b5c1c637d523f07f8a4cf0b3dded`. Registry acquisition currently follows upstream refs, so review the resolved `source_revision` fields on each load; the version label alone does not establish node identity when upstream changes.

The BHSA parent corpus is listed under **CC BY-NC 4.0** in Agora, while the cantillation feature files declare **CC BY 4.0** and cite MorphHB provenance. Preserve attribution, source revisions, and the rights of *each* layer; loading the module does not relax the BHSA noncommercial restriction. The acceptance workflow downloads source data into runner-local caches and does not distribute converted corpora.

## Important limitations

A plugin-level verification result does not promote every corpus or annotation layer. Use the resource catalog and compatibility evidence for the specific resource/path.

Registered plugin-level advisories:

- `context-fabric/search-count-cache-cap` — cfabric-mcp 0.1.7 truncates cached search results at 10,000 before deriving return_type=count, so a reported count of 10,000 is only a lower bound for larger result sets.
- `context-fabric/cuc-text-format-discovery` — cfabric-mcp 0.1.7 discovers text representations from paired fmt metadata and can report none for CUC even though its sign and usign features expose Latin and Ugaritic forms.

## Disk, memory, and network

The canonical runtime and data mode are local; disk and memory use depend on the selected corpus and cache state. Historical load observations live in the resource catalog. First acquisition normally needs network access to the registered upstream Git source unless the exact required snapshots are already resident for offline use. For an unfamiliar resource, use `describe_available_corpus` → `prepare_corpus` → `load_corpus`, and inspect the [cache and cold-load guide](../context-fabric-cache.md) before an expensive load.

## Provenance and licensing

The plugin registry records:

- `software`: `upstream`
- `data`: `resource-specific`

These fields describe the plugin/software/service boundary. Corpus, edition, annotation, or hosted-data rights can remain resource- or upstream-specific.

## Troubleshooting

Start from the observed symptom in [installation troubleshooting](../installation.md#troubleshooting). For current client/platform evidence and structured advisories, use [compatibility and known limitations](../compatibility.md#current-upstream-limitations).

## Upstream

- Repository: https://github.com/Context-Fabric/context-fabric
- Homepage/docs: https://context-fabric.ai/
