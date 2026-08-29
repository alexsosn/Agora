# Plan: Building Agora as a Digital Philology Marketplace

Agora is a fresh repository. This plan does not assume a migration from `mcp-demo`, does not require preserving its interfaces, and does not treat workshop compatibility as a design goal.

`mcp-demo` may be mined for tested code, metadata, examples, and integration knowledge where useful, but every reused component should be adapted to Agora's architecture rather than carried over for compatibility.

The fixed first-implementation resource set is documented in [`wiki/v0.1-scope.md`](v0.1-scope.md).

## Phase 0 — Establish Agora's foundation

**Status: implemented.**

### Tasks

1. Define the canonical repository layout.
2. Add basic project metadata and licensing.
3. Add a minimal CI workflow.
4. Decide which generated marketplace artifacts must be committed and which can be built in CI.
5. Document the clean-slate rule: no compatibility obligation to `mcp-demo`.

**Exit criterion:** Agora has an intentional skeleton suitable for marketplace-first development.

## Phase 1 — Define the canonical marketplace and resource data model

The schema must be designed around the actual v0.1 scope rather than around a small proof-of-concept corpus set.

### Fixed plugin families

1. `context-fabric`
2. `perseus`
3. `sefaria`
4. `sedra`

### Fixed Context-Fabric resource baseline

The registry must include:

- all **35 concrete corpus entries** currently listed by the Context-Fabric corpus catalog source;
- `alexsosn/TLHdig-TF` as an additional Hittite corpus;
- therefore **36 Context-Fabric corpus resources** at initial release.

The exact list is in [`wiki/v0.1-scope.md`](v0.1-scope.md).

### Tasks

1. Add machine-readable schemas for:
   - marketplace/plugin metadata;
   - provider metadata;
   - corpus/resource metadata.
2. Add canonical registry files such as:
   - `registry/plugins.yaml`;
   - `registry/providers.yaml`;
   - `registry/resources.yaml` or a structured equivalent.
3. Register all four v0.1 plugin families.
4. Register all 36 initial Context-Fabric corpus resources.
5. Define controlled vocabularies for:
   - disciplines;
   - languages;
   - capabilities;
   - runtime modes;
   - data modes;
   - plugin verification status;
   - resource/data verification status.
6. Distinguish:
   - software license;
   - dataset/content license;
   - redistribution rights;
   - remote-service terms.
7. Model collections explicitly so repositories such as `pthu/greek_literature` do not become thousands of top-level plugins.
8. Allow resource-level known-issues/provenance metadata.
9. Mark TLHdig-TF `0.1.0` as `experimental` initially unless the upstream status changes before release.
10. Add JSON Schema or equivalent validation.
11. Add tests rejecting malformed IDs, duplicate plugin IDs, duplicate resource IDs, invalid references, and unknown controlled-vocabulary values.

### Design rule

**Plugin verification and resource verification are separate dimensions.** A Context-Fabric integration can be technically Verified while one of its corpus resources remains Community or Experimental.

**Exit criterion:** every resource in the fixed v0.1 scope can be represented cleanly without client-specific fields leaking into the canonical schema.

## Phase 2 — Build marketplace manifest generators

Generate client artifacts from the canonical registry.

### Tasks

1. Implement `scripts/generate_marketplaces.py`.
2. Generate the Claude marketplace manifest.
3. Generate the ChatGPT/Codex-compatible marketplace representation.
4. Generate Antigravity plugin descriptors/configuration where required.
5. Add a `--check` mode that fails if committed generated files are stale.
6. Add snapshot/schema tests for generated artifacts.
7. Add CI that runs generation and validation.

### Design rule

Do not hand-maintain equivalent plugin metadata in multiple platform formats.

**Exit criterion:** one canonical registry edit updates all supported marketplace formats deterministically.

## Phase 3 — Implement the Context-Fabric provider and full v0.1 corpus baseline

This is not a representative-corpus prototype. The first implementation must cover the full fixed Context-Fabric resource set.

### 3.1 Create the provider plugin

Create a clean provider structure, for example:

```text
plugins/context-fabric/
├── plugin metadata
├── skills/
├── scripts/
└── resources/
```

The plugin should expose Text-Fabric-format corpora through Context-Fabric MCP.

### 3.2 Corpus acquisition

Implement a corpus resolver that can map canonical resource IDs to upstream repositories and TF data locations.

Preferred behavior:

```text
request corpus
→ resolve registry entry
→ acquire/cache TF data
→ compile/load with Context-Fabric
→ expose through cfabric-mcp
```

Use native Text-Fabric acquisition/application mechanisms where practical. Avoid full repository clones when a narrower supported acquisition path exists.

### 3.3 Logical corpus addressing

Avoid machine-specific absolute paths in canonical metadata.

If necessary, add a resolver around Context-Fabric MCP so users/plugins can specify logical corpus IDs or upstream applications rather than precomputed local paths.

A conceptual target is:

```bash
cfabric-mcp --tf-app ETCBC/bhsa
```

or an Agora wrapper with equivalent semantics.

If upstream changes to `cfabric-mcp` are needed, keep them as separable upstream contributions rather than a permanent Agora fork.

### 3.4 Implement all 36 initial resources

The plugin must represent and be able to prepare the 35 current Context-Fabric catalog resources plus TLHdig-TF.

This includes, among others:

- BHSA, DSS, Samaritan Pentateuch, Extra-biblical Hebrew;
- LXX and multiple Greek New Testament corpora;
- `pthu/bible`, `pthu/patristics`, `pthu/greek_literature`, Athenaeus;
- Peshitta and Syriac NT/resources;
- Quran and Fusus;
- Neo-Aramaic;
- Uruk, Old Assyrian, Old Babylonian, NinMed;
- Copenhagen Ugaritic Corpus;
- Dhammapada;
- Latin/Dutch/French/Italian/English historical and literary corpora;
- TLHdig-TF.

The exact authoritative v0.1 list is [`wiki/v0.1-scope.md`](v0.1-scope.md).

### 3.5 Collections

Treat collection repositories as resources/collections rather than marketplace plugin explosions.

In particular, `pthu/greek_literature` must remain one registered collection resource even though it contains many separately loadable TF works.

### 3.6 TLHdig-TF

Add `alexsosn/TLHdig-TF` through Context-Fabric MCP.

Initial metadata must preserve its upstream warning that `0.1.0` is an integration prototype and should not yet be relied on for research. Inclusion is required; `experimental` status is also required unless upstream validation improves before release.

### 3.7 Testing strategy

Do not require every large corpus to be fully downloaded in every ordinary CI job.

Use layered testing:

1. registry/schema checks for all 36 resources;
2. acquisition-resolution checks for all resources;
3. lightweight/small-corpus end-to-end tests on every PR where practical;
4. batched or scheduled integration tests for larger corpora;
5. resource-specific smoke tests where meaningful.

**Exit criterion:** all 36 initial corpus resources are first-class registry entries and the Context-Fabric plugin can resolve, acquire, and expose them according to documented status and testing policy.

## Phase 4 — Implement Perseus, Sefaria, and SEDRA

These are independent plugins, not sub-resources of Context-Fabric.

### 4.1 Perseus

Use `tonyjurg/Perseus-mcp` upstream rather than vendoring it.

Tasks:

1. determine supported installation/version policy;
2. create `plugins/perseus/`;
3. reference upstream;
4. add launch/configuration only where necessary;
5. document CTS URNs, corpus/edition discovery, passage retrieval, Scaife search, and known limitations;
6. test MCP initialization, discovery, known-passage retrieval, and representative search;
7. record software license and upstream data-service caveats;
8. test supported clients.

### 4.2 Sefaria

Create `plugins/sefaria/` with:

- hosted endpoint configuration;
- transport adaptation only where required;
- text/reference/link/dictionary usage guidance;
- health and known-reference smoke tests.

Reuse endpoint/proxy knowledge from `mcp-demo` where helpful without inheriting its architecture.

### 4.3 SEDRA

Create `plugins/sedra/` with:

- Beth Mardutho / SEDRA launch/integration logic;
- explicit word-versus-lexeme guidance;
- representative lexicographic smoke tests.

**Exit criterion:** Perseus, Sefaria, and SEDRA can each be installed/enabled independently from the Context-Fabric plugin.

## Phase 5 — Scholarly skills

Add concise, source-grounded skills to the first-release plugins and high-value corpus resources.

Initial skills should include:

- **Context-Fabric:** graph model, search syntax, corpus discovery, feature inspection, collection handling.
- **BHSA/ETCBC:** morphology/features, phrase/clause structure, useful query patterns.
- **CUC:** Ugaritic transliteration, tablet/line hierarchy, feature semantics.
- **TLHdig-TF:** Hittite corpus hierarchy, morphology/analysis nodes, damage/editorial apparatus, explicit known limitations.
- **Perseus:** CTS, edition discovery, passage retrieval/search, Perseus vs Scaife distinctions.
- **Sefaria:** reference conventions, text/link/dictionary workflows.
- **SEDRA:** word/lexeme lookup semantics.

Skills should be tested against the actual tools where possible.

**Exit criterion:** a newly installed plugin provides enough domain context for a capable model to make correct first attempts without reading repository internals.

## Phase 6 — Verification and trust layer

Create a common verification harness that distinguishes integration health from scholarly-resource status.

### Plugin checks

1. metadata/schema validation;
2. installation resolution;
3. server startup or hosted endpoint reachability;
4. MCP initialization;
5. tool enumeration;
6. representative operation;
7. cleanup;
8. version/provenance recording.

### Resource checks

1. upstream availability;
2. acquisition resolution;
3. loadability;
4. representative text/feature access;
5. known-issue metadata;
6. license/provenance metadata;
7. resource verification state.

### Status policy

For both plugins and resources, use explicit states such as:

- **Verified** — tested to the defined level in CI;
- **Community** — valid/useful but not continuously tested to Verified standard;
- **Experimental** — incomplete, unstable, or known to have unresolved correctness problems.

A plugin's Verified status must not automatically propagate to all of its resources.

**Exit criterion:** status labels are machine-enforced and accurately scoped.

## Phase 7 — Documentation and optional profiles

### Documentation

Document:

- marketplace installation;
- plugin installation;
- the fixed v0.1 resource catalog;
- adding a third-party MCP;
- adding a Context-Fabric corpus;
- collection semantics;
- verification policy;
- licensing policy;
- upstream policy;
- client compatibility.

Generate plugin/resource tables from registry data where practical.

### Profiles

Profiles may be added as optional convenience bundles, for example:

- `classics`
- `biblical-studies`
- `assyriology`
- `semitic-languages`

They are not compatibility layers and are not required to reproduce `mcp-demo`.

## Phase 8 — Post-v0.1 expansion

Only after the fixed first implementation works should Agora expand to new provider families/resources.

Suggested investigation areas:

1. ORACC/ePSD/CDLI ecosystem;
2. papyri.info / papyrological resources;
3. epigraphic databases;
4. IIIF/manuscript tooling;
5. morphology and lexicography services;
6. prosopographical/entity-linking resources;
7. bibliographic discovery;
8. other open philological MCP servers.

The Context-Fabric catalog itself may also grow. New upstream catalog entries can be added after the v0.1 baseline, but must not displace completion of the fixed baseline defined in `wiki/v0.1-scope.md`.

## Recommended implementation sequence

```text
Phase 0 foundation
→ Phase 1 canonical plugin/resource schema + all v0.1 registry entries
→ Phase 2 marketplace manifest generation
→ Phase 3 Context-Fabric plugin + all 36 corpus resources
→ Phase 4 Perseus + Sefaria + SEDRA
→ Phase 5 scholarly skills
→ Phase 6 verification/trust layer
→ Phase 7 documentation/profiles
→ Phase 8 additional providers/resources
```

## Code reuse guidance

When consulting `mcp-demo`:

### Reuse freely when useful

- tested endpoint URLs;
- known-good launch arguments;
- corpus identifiers;
- TF feature metadata;
- test fixtures;
- transport workarounds;
- utility code that is already cleanly separable.

### Prefer rewriting when old assumptions leak through

- absolute checkout paths;
- monolithic multi-corpus server configuration;
- workshop-only setup logic;
- centralized client config generation tied to one installation;
- environment bootstrap code that has no role in marketplace installation.

Do not add shims solely to make Agora behave like `mcp-demo`.

## Non-goals for v0.1

- migrating `mcp-demo` users or preserving its command-line interface;
- reproducing the summer-school setup;
- writing new MCP adapters for every desirable scholarly database;
- enumerating every work inside large collection repositories as a marketplace plugin;
- vendoring third-party MCP implementations unnecessarily;
- guaranteeing identical capabilities across all clients;
- hiding upstream licensing restrictions or data-quality warnings;
- requiring every included corpus to have Verified scholarly-data status before inclusion.

## v0.1 milestone

Agora v0.1 is not complete with only four empty plugin shells.

It must contain:

1. a working **Context-Fabric** provider plugin;
2. **all 35 corpus resources in the current Context-Fabric catalog**;
3. **TLHdig-TF** as the 36th Context-Fabric resource;
4. a working **Perseus-MCP** integration;
5. a working **Sefaria** integration;
6. a working **SEDRA** integration;
7. canonical registry/schema;
8. generated marketplace metadata for supported clients;
9. resource-level provenance, licensing, and verification status;
10. integration and representative scholarly tests;
11. plugin/resource-specific scholarly guidance;
12. contributor documentation.

## Definition of done

The first implementation is complete when Agora functions as a curated cross-platform marketplace exposing the entire fixed v0.1 resource set in [`wiki/v0.1-scope.md`](v0.1-scope.md), with independent plugin installation, clear provider/resource boundaries, explicit provenance/licensing, scholarly guidance, and reproducible verification — without depending on or preserving the architecture of `mcp-demo`.
