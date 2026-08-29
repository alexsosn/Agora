# Plan: Building Agora as a Digital Philology Marketplace

Agora is a fresh repository. This plan does not assume a migration from `mcp-demo`, does not require preserving its interfaces, and does not treat workshop compatibility as a design goal.

`mcp-demo` may be mined for tested code, metadata, examples, and integration knowledge where useful, but every reused component should be adapted to Agora's architecture rather than carried over for compatibility.

## Phase 0 — Establish Agora's foundation

### Tasks

1. Define the canonical repository layout.
2. Add basic project metadata and licensing.
3. Add a minimal CI workflow.
4. Decide which generated marketplace artifacts must be committed and which can be built in CI.
5. Document the clean-slate rule: no compatibility obligation to `mcp-demo`.

**Exit criterion:** Agora has an intentional skeleton suitable for marketplace-first development.

## Phase 1 — Define the marketplace data model

Create the canonical registry first, before implementing many plugins.

### Tasks

1. Add a machine-readable registry schema.
2. Add `registry/plugins.yaml` or an equivalent structured registry.
3. Register the initial provider families:
   - Text-Fabric / ContextFabric
   - Sefaria
   - SEDRA
   - Perseus
4. Define controlled vocabularies for:
   - disciplines;
   - languages;
   - capabilities;
   - runtime modes;
   - data modes;
   - verification status.
5. Separate software license from data/content license.
6. Add JSON Schema or equivalent validation.
7. Add tests that reject malformed or duplicate plugin IDs.

**Exit criterion:** the initial integrations can be described without client-specific fields leaking into the core schema.

## Phase 2 — Build manifest generators

Generate marketplace/client artifacts from the canonical registry.

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

**Exit criterion:** one registry edit updates all supported marketplace formats deterministically.

## Phase 3 — Implement Sefaria and SEDRA as clean plugins

These are useful early integrations because working behavior is already known from earlier experiments, but Agora should implement them as independent plugins from the start.

### Tasks

1. Create `plugins/sefaria/`.
2. Reuse endpoint/proxy knowledge from `mcp-demo` only where useful.
3. Add Sefaria-specific skill/instructions.
4. Add a known-reference smoke test.
5. Create `plugins/sedra/`.
6. Reuse Beth Mardutho launch/detection code selectively if it fits the new structure.
7. Add SEDRA-specific skill/instructions.
8. Add word and lexeme smoke tests.
9. Test each plugin independently.

**Exit criterion:** Sefaria and SEDRA are standalone Agora plugins with no dependency on the old repository.

## Phase 4 — Add Perseus

Use `tonyjurg/Perseus-mcp` as the first externally maintained marketplace integration.

### Tasks

1. Determine the upstream-supported installation method and compatible version policy.
2. Create `plugins/perseus/`.
3. Reference upstream rather than vendor it.
4. Add launcher/configuration only where needed.
5. Add a skill covering:
   - CTS URNs;
   - corpus/edition discovery;
   - passage retrieval;
   - Scaife search;
   - known resource distinctions/limitations.
6. Add smoke tests for:
   - MCP initialization;
   - resource discovery;
   - retrieval of a stable known passage;
   - a representative search where upstream behavior is stable.
7. Record software license and upstream data-service caveats.
8. Test in Claude, Codex, and Antigravity.

**Exit criterion:** installing the Perseus plugin gives a working, documented Perseus MCP integration without copying the upstream implementation into Agora.

## Phase 5 — Build Text-Fabric as a generic provider plugin

This should be designed for the broad TF ecosystem from the outset rather than reproducing the old curated corpus list.

### 5.1 Create the provider structure

Create:

```text
plugins/text-fabric/
├── plugin metadata
├── skills/
├── scripts/
└── registry/
```

### 5.2 Define the TF corpus schema

For each corpus/collection record support:

- ID;
- title;
- upstream;
- language;
- discipline;
- TF versions;
- preferred version;
- data license;
- citation;
- TF app availability;
- important node/edge features;
- known issues;
- verification state.

Use known-good corpus metadata from `mcp-demo` where it saves work, but do not inherit its Python constants or path assumptions as architecture.

### 5.3 Use TF-native acquisition where possible

Investigate Text-Fabric-native repository/app acquisition.

Preferred behavior:

```text
request corpus
→ resolve upstream/version
→ download/cache through TF-compatible mechanism
→ expose through cfabric-mcp
```

Avoid full Git clones when TF's normal data acquisition can retrieve the required data more efficiently.

### 5.4 Extend `cfabric-mcp` integration

If necessary, add a resolver layer so a corpus can be specified by logical/upstream ID rather than machine-specific absolute path.

Possible target interface:

```bash
cfabric-mcp --tf-app ETCBC/bhsa
```

If this requires changes to `cfabric-mcp`, keep them as a separable upstream contribution rather than embedding a permanent fork in Agora.

### 5.5 Add corpus discovery

Provide agent-facing operations or supporting tooling for:

- list known corpora;
- filter by language/discipline;
- list installed corpora;
- install/prepare corpus;
- inspect corpus metadata/features.

### 5.6 Handle collections

Treat `pthu/greek_literature` as a collection rather than thousands of marketplace plugins.

The Greek cataloging work from `mcp-demo` can be reused as input data if useful, but Agora should store it in a provider-appropriate registry/search structure.

**Exit criterion:** the TF plugin can install/load representative corpora and can represent large collections without top-level plugin explosion.

## Phase 6 — Expand Text-Fabric coverage

After the TF provider works generically:

1. Seed from the official Text-Fabric corpus/app list.
2. Search for additional public TF repositories.
3. Validate repository structure and licensing.
4. Add metadata.
5. Smoke-test representative corpora.
6. Mark untested integrations Community rather than Verified.
7. Add CI matrices in batches to keep runtime manageable.
8. Add collection-level indexing where repositories contain many works.

Do not block marketplace launch on exhaustive TF coverage.

**Exit criterion:** adding another TF corpus normally requires metadata plus tests rather than new integration code.

## Phase 7 — Add optional curated profiles

Profiles are optional convenience bundles, not compatibility layers.

Possible initial profiles:

- `classics`
- `biblical-studies`
- `assyriology`
- `semitic-languages`

### Tasks

1. Define a profile schema if profiles prove useful.
2. Allow profiles to select plugins.
3. Allow provider-specific selections, especially TF corpora.
4. Keep profiles optional: users must still be able to install individual plugins.

Do not create a `summer-school` profile solely to reproduce `mcp-demo`. Such a profile can be added later only if there is an independent use case for it.

**Exit criterion:** profiles, if implemented, are clean declarative bundles and not remnants of the old repository.

## Phase 8 — Scholarly skills

Add concise, source-grounded skills to Verified plugins.

Initial skills:

- **Text-Fabric:** TF node/edge model, query syntax, corpus discovery, feature inspection.
- **BHSA/ETCBC:** morphology/features, phrase/clause features, query examples.
- **CUC:** Ugaritic transliteration, tablet/line hierarchy, CUC feature names.
- **Perseus:** CTS, edition discovery, passage retrieval/search.
- **Sefaria:** reference conventions, text/link/dictionary workflows.
- **SEDRA:** word/lexeme lookup semantics.

Skills should be tested against the actual exposed tools where possible.

**Exit criterion:** a newly installed plugin provides enough domain context for a capable model to make correct first attempts without reading repository internals.

## Phase 9 — Verification and trust layer

Create a common plugin verification harness.

### Required checks

1. metadata/schema validation;
2. installation resolution;
3. server startup or hosted-endpoint reachability;
4. MCP initialization;
5. tool enumeration;
6. representative scholarly operation;
7. cleanup;
8. version/provenance recording.

### Status policy

- **Verified:** CI-tested end to end.
- **Community:** valid integration, not continuously tested.
- **Experimental:** incomplete/unstable.

Generate a compatibility/status table in README from CI/registry data.

**Exit criterion:** `Verified` is machine-enforced rather than an informal label.

## Phase 10 — Documentation

Once the initial marketplace works:

1. Rewrite/expand README around Agora marketplace installation and discovery.
2. Document:
   - how to install the marketplace;
   - how to install a plugin;
   - how to add a third-party MCP;
   - how to add a TF corpus;
   - verification policy;
   - licensing policy;
   - upstream policy;
   - client compatibility.
3. Generate plugin/resource tables from registry data where practical.
4. Preserve attribution and links to upstream projects.
5. Document `mcp-demo` only as historical/reference material if mentioning it at all.

**Exit criterion:** a contributor can add a straightforward external philological MCP plugin by following documentation without modifying central runtime code.

## Phase 11 — Expand beyond initial integrations

Prioritize additions by scholarly usefulness, openness, API quality, and implementation effort.

Suggested investigation order:

1. existing open-source philological MCP servers;
2. ORACC/ePSD/CDLI ecosystem;
3. papyri.info / papyrological resources;
4. epigraphic databases;
5. IIIF/manuscript tooling;
6. morphology and lexicography services;
7. prosopographical/entity-linking resources;
8. bibliographic discovery.

For each candidate, record:

- scholarly scope;
- upstream authority;
- access mechanism;
- software license;
- data license/terms;
- authentication requirements;
- local/remote mode;
- MCP implementation status;
- maintenance activity;
- client compatibility;
- proposed smoke test.

## Recommended implementation sequence

```text
Agora skeleton
→ canonical registry
→ manifest generation
→ Sefaria plugin
→ SEDRA plugin
→ Perseus plugin
→ Text-Fabric provider
→ TF corpus expansion
→ optional profiles
→ scholarly skills
→ common verification
→ documentation
→ additional scholarly services
```

Do not begin by porting the old repository wholesale or importing every known corpus.

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

## Non-goals for the first release

- migrating `mcp-demo` users or preserving its command-line interface;
- reproducing the summer-school setup;
- writing new MCP adapters for every desirable scholarly database;
- supporting every TF corpus before marketplace release;
- creating one plugin per Greek work or TF corpus;
- vendoring all upstream MCP servers;
- guaranteeing identical capabilities across all clients;
- hiding upstream licensing restrictions;
- replacing original data providers.

## First-release milestone

A good `v0.1` should contain four independently usable Verified plugins:

1. Text-Fabric / ContextFabric
2. Perseus
3. Sefaria
4. SEDRA

It should also provide:

- a canonical registry;
- generated Claude + ChatGPT/Codex marketplace metadata;
- Antigravity-compatible packaging/configuration;
- real integration tests;
- plugin-specific scholarly skills;
- contributor documentation.

This is enough to validate Agora's architecture before importing dozens of resources.

## Definition of done

The work is complete when Agora functions as a curated, cross-platform marketplace for digital philology tools and resources, with independently installable integrations, clear provenance/licensing, domain-specific skills, and reproducible verification — without depending on or preserving the architecture of `mcp-demo`.
