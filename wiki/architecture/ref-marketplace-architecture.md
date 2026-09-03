# Research: Agora — a Plugin Marketplace for Digital Philology

## 1. Goal

Agora is a new, clean-slate, cross-platform plugin marketplace for philology and related disciplines.

Its purpose is to make scholarly corpora, textual databases, lexica, search services, manuscript resources, and related research tools easy to discover, install, and use from AI agents.

Agora is not a continuation of `alexsosn/mcp-demo` and does not inherit that repository's workshop-oriented architecture, compatibility obligations, setup flow, or historical assumptions. The old repository may be used as a source of tested code, integration knowledge, configuration patterns, corpus metadata, and smoke tests, but Agora should only reuse pieces that fit the new architecture.

Agora must support heterogeneous upstreams, including:

- local MCP servers;
- hosted MCP endpoints;
- APIs wrapped by MCP servers;
- locally cached corpora;
- remote scholarly services;
- plugins that add domain-specific skills around external tools.

## 2. Fixed first implementation

The first implementation is not merely a four-plugin architectural proof of concept. Its resource scope is fixed in [`v0.1-scope-frozen.md`](../releases/v0.1-scope-frozen.md).

It contains four plugin families:

1. **Context-Fabric** — the complete current Context-Fabric corpus catalog plus TLHdig-TF and the ETCBC Targum Corpus;
2. **Perseus** — `tonyjurg/Perseus-mcp`;
3. **Sefaria**;
4. **Beth Mardutho / SEDRA**.

The current Context-Fabric documentation page says it catalogs "40+" known corpora, while the current `CorporaTable.tsx` source contains 35 concrete entries. Agora v0.1 uses the concrete source-table entries as the baseline and records the snapshot provenance. Adding `alexsosn/TLHdig-TF` and `ETCBC/targum` gives **37 Context-Fabric corpus resources**.

The 35 Context-Fabric catalog entries are:

- `bhsa`
- `dss`
- `sp`
- `extrabiblical`
- `lxx`
- `n1904`
- `SBLGNT`
- `nestle1904`
- `Nestle1904GBI`
- `tischendorf_tf`
- `bible`
- `patristics`
- `greek_literature`
- `athenaeus`
- `peshitta`
- `syrnt`
- `syriac`
- `quran`
- `fusus`
- `nena_tf`
- `uruk`
- `oldassyrian`
- `oldbabylonian`
- `ninmed`
- `cuc`
- `dhammapada`
- `translatin-manif`
- `wp6-missieven`
- `wp6-daghregisters`
- `wp6-ferdinandhuyck`
- `mondriaan`
- `descartes-tf`
- `suriano`
- `mobydick`
- `banks`

TLHdig-TF is an explicit additional resource, not part of the current Context-Fabric catalog snapshot. It should be exposed through Context-Fabric MCP.

### Inclusion is not upstream endorsement

Agora verification answers an integration question: does the plugin or resource configuration install, initialize, resolve, and perform representative operations correctly? It does not assess whether an upstream corpus is suitable for a particular research use.

Suitability, data quality, corpus semantics, and upstream limitations remain owned by the original repository or corpus publisher. Agora should identify and resolve the upstream source precisely so users can consult the documentation matching the loaded revision; it should not duplicate mutable upstream assessments.

## 3. Relationship to `mcp-demo`

`mcp-demo` should be treated as prior art and a reusable code source, not as the system being refactored.

Potentially reusable assets include:

- working Context-Fabric launch/configuration code;
- known-good TF corpus identifiers and feature metadata;
- Greek Text-Fabric cataloging work;
- Sefaria transport/proxy knowledge;
- SEDRA integration details;
- client configuration experiments;
- verification/smoke-test logic;
- examples of real research queries.

These assets should be copied, adapted, or reimplemented only when useful. Agora does not need to preserve:

- the old `setup.sh` interface;
- the old environment layout;
- the workshop profile;
- monolithic `ancient-corpora` configuration;
- machine-specific absolute-path generation;
- compatibility with the old repository's file structure;
- any promise that existing `mcp-demo` users can switch to Agora without changes.

## 4. Target abstraction

Agora should distinguish four concepts.

### 4.1 Marketplace

The repository/catalog that advertises installable scholarly plugins.

### 4.2 Plugin

The unit installed by an agent client. A plugin may contain:

- one or more MCP server definitions;
- skills/instructions;
- commands or agent definitions where supported;
- scripts or launchers;
- metadata;
- optional resource/catalog files.

A plugin is not synonymous with an MCP server.

### 4.3 Provider/backend

The mechanism supplying data or functionality. Examples:

- Context-Fabric / Text-Fabric data
- Perseus CTS / Scaife
- Sefaria
- SEDRA
- ORACC
- CDLI
- IIIF
- Wikidata

Several resources may use the same backend, and one plugin may integrate several backends.

### 4.4 Corpus/resource

A scholarly dataset available through a plugin. Corpora should not automatically become top-level marketplace plugins.

This distinction is essential for Agora v0.1 because the Context-Fabric plugin must expose 37 corpus resources while remaining one plugin family. Repositories such as `pthu/greek_literature` can contain many separately loadable works; treating every work as a marketplace plugin would make discovery unusable.

## 5. Marketplace scope

The intended domain is digital philology and adjacent historical-text disciplines rather than a specific data format.

Likely categories include:

- Classics
- Ancient Near East / Assyriology
- Hittitology
- Biblical studies
- Judaica
- Syriac studies
- Semitic linguistics
- Papyrology
- Epigraphy
- Manuscript studies
- Historical linguistics
- Lexicography
- Prosopography
- Bibliography
- Digital editions
- Textual criticism
- Paleography / HTR / OCR
- IIIF and manuscript-image tooling

The scope can include generic infrastructure when it has a clear philological use case.

## 6. v0.1 plugin families

### 6.1 `context-fabric`

Agora should use **Context-Fabric** as the provider/plugin identity, with Text-Fabric describing the corpus data format/ecosystem beneath it.

Responsibilities:

- maintain the canonical registry of v0.1 corpus resources;
- resolve/install/cache a requested TF-format corpus;
- compile/load corpora with Context-Fabric;
- expose them through Context-Fabric MCP;
- list available and installed corpora;
- expose corpus metadata and important features;
- support collection repositories such as `pthu/greek_literature`;
- provide Context-Fabric/TF-specific agent instructions.

The v0.1 provider must cover all 35 current Context-Fabric catalog entries plus TLHdig-TF. Broad coverage is therefore a release requirement rather than a later expansion goal.

The resource registry should record at least:

- stable resource ID;
- title;
- upstream repository;
- TF application/data location;
- language(s);
- discipline/category;
- period;
- data/content license;
- citation/publication information;
- available/preferred TF versions;
- node types;
- important node/edge features;
- morphology/syntax availability;
- collection membership;
- acquisition status;
- plugin/runtime verification status;
- resource integration-verification status;
- Agora-owned integration issues.

The preferred design is to use supported TF-native acquisition/application mechanisms where practical rather than reproducing bespoke clone/path logic from `mcp-demo`.

### 6.2 `perseus`

Integrate `tonyjurg/Perseus-mcp` rather than vendoring it.

The marketplace plugin should add:

- upstream installation/launch metadata;
- client-compatible MCP configuration;
- CTS/URN usage guidance;
- Perseus/Scaife resource distinctions;
- smoke tests;
- upstream version/provenance metadata.

### 6.3 `sefaria`

Create Sefaria as an independent Agora plugin.

The plugin should contain:

- hosted endpoint definition;
- transport compatibility/proxy behavior where clients still need it;
- scholarly instructions for text retrieval, links, dictionaries, commentaries, and related tools;
- health checks.

### 6.4 `sedra`

Create an independent Beth Mardutho / SEDRA plugin.

The Agora plugin should document and test the distinction between word and lexeme lookup and expose relevant Syriac lexicographic workflows.

## 7. Granularity rules

### A plugin should usually be created when:

- it has an independent upstream MCP server or service;
- it has a distinct installation/runtime lifecycle;
- it represents a coherent scholarly service;
- it benefits from its own domain instructions;
- users may reasonably want it without other Agora components.

### A corpus/resource should usually remain inside a provider plugin when:

- many corpora share the same runtime;
- installation differs mainly by corpus identifier/upstream metadata;
- the upstream repository contains many similar corpus units;
- making each corpus a plugin would swamp discovery.

Thus BHSA, CUC, TLHdig-TF, and `pthu/greek_literature` are resources of `context-fabric`, not independent marketplace plugins.

## 8. Cross-client strategy

Agora should target at least:

- ChatGPT/Codex plugin marketplace support;
- Claude Code plugin marketplace support;
- Google Antigravity plugins.

Avoid hand-maintaining equivalent metadata in several formats. Define a canonical internal registry and generate client-specific manifests/configuration when formats cannot be shared directly.

## 9. Proposed repository structure

```text
Agora/
├── README.md
├── LICENSE
│
├── registry/
│   ├── plugins.yaml
│   ├── providers.yaml
│   ├── resources.yaml
│   └── schema/
│
├── plugins/
│   ├── context-fabric/
│   ├── perseus/
│   ├── sefaria/
│   └── sedra/
│
├── profiles/
│   └── ...
│
├── generated/
│   └── client-specific marketplace artifacts
│
├── scripts/
│   ├── validate_registry.py
│   ├── generate_marketplaces.py
│   ├── smoke_test.py
│   └── ...
│
├── tests/
│   ├── registry/
│   ├── plugins/
│   └── integration/
│
└── wiki/
    ├── README.md
    ├── architecture/
    ├── releases/
    ├── guides/
    ├── backlog/
    └── reviews/
```

Exact platform-required files such as `.claude-plugin/marketplace.json` or `.agents/...` should be generated or thin projections of the canonical registry.

## 10. Canonical registry

The registry is the core maintainability mechanism.

A plugin record should describe runtime/integration concerns. Resource records should describe corpus/data concerns and reference their provider/plugin.

A simplified plugin record might look like:

```yaml
id: perseus
name: Perseus Digital Library
upstream:
  repository: tonyjurg/Perseus-mcp
runtime:
  mode: local
  type: python
capabilities:
  - corpus-discovery
  - passage-retrieval
  - full-text-search
  - cts-navigation
verification:
  status: verified
```

A corpus resource record should be separately addressable:

```yaml
id: tlhdig-tf
plugin: context-fabric
provider: context-fabric
upstream:
  repository: alexsosn/TLHdig-TF
language:
  - hittite
resource:
  type: corpus
  version: 0.1.0
verification:
  status: community
```

The schema should distinguish software license, dataset/content license, redistribution rights, and remote-service terms.

## 11. Verification model

Marketplace verification communicates operational integration trust only. Upstream publishers remain authoritative for scholarly suitability and data quality.

### Plugin/integration status

**Verified** means the integration installs/connects, MCP initialization succeeds, tools are available, and representative operations pass CI.

### Resource integration status

Resource status describes Agora's confidence in acquisition, resolution, and loading:

- **Verified** — the advertised integration path is continuously tested to Agora's defined standard;
- **Community** — the integration is registered and usable but not continuously tested to the Verified standard;
- **Experimental** — the Agora-owned integration path is incomplete or unstable.

Tests should verify integration behavior without becoming upstream semantic tests. Examples include:

- a registered Context-Fabric resource resolves and loads from its configured source;
- Perseus reaches a published CTS retrieval operation and returns a structurally valid response;
- Sefaria and SEDRA endpoints initialize and expose their advertised tools.

## 12. Skills and scholarly guidance

A major advantage over generic MCP registries is that plugins can teach an agent how to use resources correctly.

Examples:

- Context-Fabric: graph model, query syntax, feature discovery, corpus switching.
- BHSA: ETCBC feature names and morphological query patterns.
- CUC: Ugaritic transliteration, tablet/line hierarchy, relevant features.
- TLHdig-TF: registered-resource loading, resolved-source provenance, and discovery of the matching upstream documentation.
- Perseus: CTS URNs, edition discovery, passage addressing.
- SEDRA: word IDs versus lexeme IDs.

Skills should be concise, source-grounded, and versioned with the integration. Mutable corpus semantics, suitability, and data-quality guidance should remain upstream and be consulted at the resolved source revision.

## 13. Upstream policy

Do not vendor third-party MCP implementations unless technically unavoidable.

Prefer:

1. reference upstream;
2. pin or constrain compatible versions when necessary;
3. add marketplace metadata;
4. add launch/adaptation logic;
5. add scholarly skills;
6. test the integration.

Where an upstream lacks packaging suitable for plugins, add a thin launcher or adapter rather than copying its source.

## 14. Code reuse policy

Agora should freely reuse suitable code and knowledge from `mcp-demo`, subject to normal licensing and attribution requirements, but reuse should be selective.

Prefer extracting small, well-understood components such as endpoint constants, verified corpus metadata, smoke-test fixtures, launch construction, transport adapters, and schema-discovery helpers.

Avoid importing old architectural coupling simply because working code already exists.

## 15. Key technical questions

1. What exact subset of Claude marketplace metadata is accepted directly by ChatGPT/Codex, and which fields require generated platform-specific variants?
2. What is the cleanest Antigravity packaging/install path for third-party plugins?
3. Can Context-Fabric MCP accept logical TF application/repository identifiers directly, or should Agora add a resolver?
4. How should Context-Fabric handle dynamically installed corpora: restart, lazy load, or separate process(es)?
5. How should collection resources such as `pthu/greek_literature` expose individual works without marketplace-entry explosion?
6. How should Agora test acquisition resolution for all 37 v0.1 Context-Fabric resources without downloading every large corpus on each PR?
7. Which marketplace files must live at fixed paths and therefore cannot remain only under `generated/`?
8. How should local corpus caches be shared across Claude, Codex, and Antigravity?
9. How should upstream corpus-catalog changes be detected after the v0.1 baseline is fixed?
10. What exact integration checks distinguish Verified, Community, and Experimental at both plugin and resource levels?

## 16. Success criteria

Agora's first implementation is successful when:

- the repository can be added as a marketplace in supported clients;
- `context-fabric`, `perseus`, `sefaria`, and `sedra` are independently represented as plugins;
- the Context-Fabric provider includes all 35 current catalog entries plus TLHdig-TF;
- collection repositories do not explode into one marketplace plugin per text;
- plugin/runtime and resource integration verification are modeled separately;
- third-party MCP code is referenced rather than unnecessarily forked;
- plugin/resource metadata is generated from one canonical registry;
- software/data licensing and upstream provenance are visible;
- CI verifies real MCP functionality and representative integration behavior;
- plugins/resources direct agents to authoritative upstream documentation for corpus semantics and suitability;
- no architectural requirement exists solely to preserve `mcp-demo` behavior.
