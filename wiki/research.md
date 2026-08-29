# Research: Agora — a Plugin Marketplace for Digital Philology

## 1. Goal

Agora is a new, clean-slate, cross-platform plugin marketplace for philology and related disciplines.

Its purpose is to make scholarly corpora, textual databases, lexica, search services, manuscript resources, and related research tools easy to discover, install, and use from AI agents.

Agora is not a continuation of `alexsosn/mcp-demo` and does not inherit that repository's workshop-oriented architecture, compatibility obligations, setup flow, or historical assumptions. The old repository may be used as a source of tested code, integration knowledge, configuration patterns, corpus metadata, and smoke tests, but Agora should only reuse pieces that fit the new architecture.

Text-Fabric is an important provider family, but it must not define the design. Agora should support heterogeneous upstreams, including:

- local MCP servers;
- hosted MCP endpoints;
- APIs wrapped by MCP servers;
- locally cached corpora;
- remote scholarly services;
- plugins that add domain-specific skills around external tools.

Initial integrations worth implementing include:

- ContextFabric / Text-Fabric corpora;
- Sefaria;
- Beth Mardutho / SEDRA;
- `tonyjurg/Perseus-mcp`;
- additional philological MCP servers as they become available.

## 2. Relationship to `mcp-demo`

`mcp-demo` should be treated as prior art and a reusable code source, not as the system being refactored.

Potentially reusable assets include:

- working ContextFabric launch/configuration code;
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

This separation is important because the clean-slate repository makes it possible to design around marketplace semantics from the beginning instead of gradually converting an installer into one.

## 3. Target abstraction

Agora should distinguish four concepts.

### 3.1 Marketplace

The repository/catalog that advertises installable scholarly plugins.

### 3.2 Plugin

The unit installed by an agent client. A plugin may contain:

- one or more MCP server definitions;
- skills/instructions;
- commands or agent definitions where supported;
- scripts or launchers;
- metadata;
- optional resource/catalog files.

A plugin is not synonymous with an MCP server.

### 3.3 Provider/backend

The mechanism supplying data or functionality. Examples:

- Text-Fabric / ContextFabric
- Perseus CTS / Scaife
- Sefaria
- SEDRA
- ORACC
- CDLI
- IIIF
- Wikidata

Several plugins may use the same backend, and one plugin may integrate several backends.

### 3.4 Corpus/resource

A scholarly dataset available through a plugin. Corpora should not automatically become top-level marketplace plugins.

This distinction is necessary because repositories such as `pthu/greek_literature` contain a very large number of separately loadable Text-Fabric works. Treating every corpus directory as a marketplace plugin would make the catalog unmanageable.

## 4. Marketplace scope

The intended domain is digital philology and adjacent historical-text disciplines rather than a specific data format.

Likely categories include:

- Classics
- Ancient Near East / Assyriology
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

The scope can include generic infrastructure when it has a clear philological use case. A generic Wikidata or IIIF MCP, for example, may belong in Agora if its plugin supplies useful scholarly instructions and has a defensible research workflow.

## 5. Proposed plugin families

### 5.1 `text-fabric`

A generic Text-Fabric/ContextFabric plugin should provide access to the TF ecosystem rather than hard-code a small curated corpus set.

Responsibilities:

- maintain or consume a registry of known TF corpora;
- discover/install/cache a requested corpus;
- expose installed corpora through ContextFabric MCP;
- list available and installed corpora;
- expose corpus metadata and important TF features;
- support collections such as `pthu/greek_literature`;
- provide TF-specific agent instructions.

The preferred design is to use Text-Fabric's own corpus/application acquisition mechanisms where possible rather than adopting the bespoke clone/path logic used by `mcp-demo`.

The TF corpus registry should record at least:

- stable marketplace ID;
- title;
- upstream repository;
- TF application/data location;
- language(s);
- discipline/category;
- license for data;
- citation/publication information;
- available/preferred TF versions;
- node types;
- important node/edge features;
- morphology/syntax availability;
- install/test status;
- known incompatibilities;
- collection membership.

### 5.2 `perseus`

Wrap/integrate `tonyjurg/Perseus-mcp` rather than vendoring it.

The marketplace plugin should add:

- upstream installation/launch metadata;
- client-compatible MCP configuration;
- CTS/URN usage guidance;
- distinction between relevant Perseus and Scaife resources;
- smoke tests;
- upstream version/provenance metadata.

### 5.3 `sefaria`

Create Sefaria as an independent Agora plugin.

The existing `mcp-demo` integration can be consulted for tested endpoint and transport behavior, but Agora should own a clean plugin implementation rather than preserve the old integration structure.

The plugin should contain:

- hosted endpoint definition;
- transport compatibility/proxy behavior where clients still need it;
- scholarly instructions for text retrieval, links, dictionaries, commentaries, and related tools;
- health checks.

### 5.4 `sedra`

Create an independent Beth Mardutho / SEDRA plugin.

The old repository's integration can be reused selectively. The Agora plugin should document and test the distinction between word and lexeme lookup and expose relevant Syriac lexicographic workflows.

### 5.5 Future plugins

Candidate families should be evaluated individually rather than forced into a TF model. Examples worth investigating include:

- ORACC/ePSD/CDLI integrations;
- papyri.info;
- Trismegistos;
- Epigraphic Database Heidelberg and related epigraphic databases;
- IIIF tooling;
- morphological analyzers such as Morpheus-compatible services;
- lexicographic services;
- manuscript catalogues;
- bibliographic services;
- prosopographical/entity-linking tools.

## 6. Granularity rules

### A plugin should usually be created when:

- it has an independent upstream MCP server or service;
- it has a distinct installation/runtime lifecycle;
- it represents a coherent scholarly service;
- it benefits from its own domain instructions;
- users may reasonably want it without other Agora components.

### A corpus should usually remain inside a provider plugin when:

- many corpora share the same runtime;
- installation differs only by corpus identifier;
- the upstream repository contains hundreds/thousands of similar corpus units;
- making each corpus a plugin would swamp discovery.

Convenience/preset plugins may later be added for major workflows, but should depend on shared infrastructure rather than duplicate it.

## 7. Cross-client strategy

Agora should target at least:

- ChatGPT/Codex plugin marketplace support;
- Claude Code plugin marketplace support;
- Google Antigravity plugins.

Claude and ChatGPT/Codex currently have closely related marketplace concepts and should share metadata wherever feasible. Antigravity has plugin support but should be treated as an adapter target rather than allowed to dictate the canonical repository structure.

Avoid hand-maintaining equivalent metadata in several formats. Define a canonical internal registry and generate client-specific manifests/configuration when formats cannot be shared directly.

## 8. Proposed repository structure

```text
Agora/
├── README.md
├── LICENSE
├── pyproject.toml
│
├── registry/
│   ├── plugins.yaml
│   ├── providers.yaml
│   └── corpora/
│       └── ...
│
├── plugins/
│   ├── text-fabric/
│   ├── perseus/
│   ├── sefaria/
│   └── sedra/
│
├── profiles/
│   ├── classics.yaml
│   ├── biblical-studies.yaml
│   ├── assyriology.yaml
│   └── semitic-languages.yaml
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
    ├── research.md
    └── plan.md
```

Exact platform-required files such as `.claude-plugin/marketplace.json` or `.agents/...` should be generated or thin projections of the canonical registry.

## 9. Canonical registry

The registry is the core maintainability mechanism.

A plugin record should contain fields along these lines:

```yaml
id: perseus
name: Perseus Digital Library
description: Access Perseus and Scaife textual resources through MCP.

disciplines:
  - classics

languages:
  - ancient-greek
  - latin

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

data:
  mode: remote
  providers:
    - perseus
    - scaife

licenses:
  software: MIT
  data: upstream-dependent

verification:
  level: verified
  smoke_tests:
    - ...
```

The schema should distinguish:

- software license;
- dataset/content license;
- redistribution rights;
- remote-service terms where applicable.

That distinction is essential for scholarly datasets.

## 10. Verification model

Marketplace inclusion should communicate trust and maintenance state.

### Verified

- installs successfully in CI;
- MCP handshake succeeds;
- representative scholarly operation succeeds;
- upstream/version information is current enough to reproduce the test.

### Community

- metadata and integration are valid;
- useful upstream exists;
- not continuously integration-tested.

### Experimental

- unstable or incomplete upstream;
- partial functionality;
- unresolved compatibility/data issues.

Tests should verify actual scholarly behavior rather than only process startup. Examples:

- BHSA morphological query returns results;
- CUC Ugaritic query returns expected hits;
- Perseus retrieves a known CTS passage;
- Sefaria retrieves a known reference;
- SEDRA resolves a known word/lexeme.

Tests should avoid brittle assertions on large result sets unless required.

## 11. Profiles

Profiles may be useful as optional curated bundles, but they are not required for Agora's core design and should not exist merely to preserve `mcp-demo` workflows.

Possible profiles include:

### `classics`

Perseus plus relevant Text-Fabric Greek corpora and future classical lexicographic/epigraphic tools.

### `biblical-studies`

BHSA, LXX, DSS/extrabiblical corpora, Sefaria, Syriac/Peshitta resources, etc.

### `assyriology`

Relevant TF cuneiform corpora plus future ORACC/ePSD/CDLI integrations.

Profiles should be declarative selections, not duplicated plugin implementations.

## 12. Skills and scholarly guidance

A major advantage over generic MCP registries is that every plugin can teach an agent how to use the resource correctly.

Examples:

- BHSA: ETCBC feature names and morphological query patterns.
- CUC: Ugaritic transliteration, tablet/line hierarchy, relevant features.
- Perseus: CTS URNs, edition discovery, passage addressing.
- SEDRA: word IDs versus lexeme IDs.
- ORACC: project IDs, lemmatization conventions, transliteration.
- IIIF: manifests, canvases, regions, image services.

Skills should be concise, source-grounded, and versioned with the integration. They should not silently claim capabilities that the underlying resource lacks.

## 13. Upstream policy

Do not vendor third-party MCP implementations unless technically unavoidable.

Prefer:

1. reference upstream;
2. pin or constrain compatible versions when necessary;
3. add marketplace metadata;
4. add launch/adaptation logic;
5. add scholarly skills;
6. test the integration.

This minimizes fork maintenance and gives upstream authors proper ownership and attribution.

Where an upstream lacks packaging suitable for plugins, add a thin launcher or adapter rather than copying its source.

## 14. Code reuse policy

Agora should freely reuse suitable code and knowledge from `mcp-demo`, subject to normal licensing and attribution requirements, but reuse should be selective.

Prefer extracting small, well-understood components such as:

- endpoint constants;
- verified corpus metadata;
- smoke-test fixtures;
- launch command construction;
- transport adapters;
- schema-discovery helpers.

Avoid importing old architectural coupling simply because working code already exists.

If reused code assumes the old monolithic setup, rewrite it around Agora's plugin boundaries instead of adding compatibility layers.

## 15. Key technical questions to resolve during implementation

1. What exact subset of Claude marketplace metadata is accepted directly by ChatGPT/Codex, and which fields require generated platform-specific variants?
2. What is the cleanest Antigravity packaging/install path for third-party plugins?
3. Can `cfabric-mcp` accept TF app/repository identifiers directly, or should that resolver be added?
4. How should ContextFabric handle dynamically installed corpora: restart, lazy load, or separate process per provider/profile?
5. How should TF collections such as `pthu/greek_literature` be indexed without enumerating thousands of marketplace plugins?
6. Which marketplace files must live at fixed paths and therefore cannot be kept only under `generated/`?
7. How should local caches be shared across Claude, Codex, and Antigravity?
8. How should upstream updates be detected and tested automatically?
9. What metadata is mandatory before a plugin can be marked Verified?
10. Which non-MCP resources merit plugins because a useful MCP adapter already exists, and which require new adapter development?

## 16. Success criteria

Agora is successful when:

- the repository can be added as a marketplace in supported clients;
- Perseus, Sefaria, SEDRA, and Text-Fabric are independently installable integrations;
- Text-Fabric can expose broad corpus coverage without one plugin per individual work;
- third-party MCP code is referenced rather than unnecessarily forked;
- plugin metadata is generated from one canonical registry;
- software/data licensing and upstream provenance are visible;
- CI verifies real MCP functionality;
- plugins include enough scholarly guidance for agents to use their resources correctly;
- adding a new external philological MCP server requires a small, documented integration rather than edits throughout the repository;
- no architectural requirement exists solely to preserve `mcp-demo` behavior.
