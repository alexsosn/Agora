# Plan: Digital Philology Marketplace Refactor

## Phase 0 — Preserve the baseline

Before structural changes:

1. Tag or otherwise record the current working `mcp-demo` state.
2. Run the existing verification suite and record expected results.
3. Ensure `./setup.sh`, Antigravity, Codex, Claude, Sefaria, TF, and SEDRA behavior are covered by reproducible smoke tests.
4. Do not change current workshop behavior in this phase.

**Exit criterion:** there is a known-good baseline against which the refactor can be tested.

## Phase 1 — Introduce the marketplace data model

Create a canonical registry without changing runtime behavior.

### Tasks

1. Add a machine-readable registry schema.
2. Add `registry/plugins.yaml`.
3. Register the currently supported provider families:
   - Text-Fabric / ContextFabric
   - Sefaria
   - SEDRA
4. Add Perseus as the first new third-party integration target.
5. Define controlled vocabularies for:
   - disciplines;
   - languages;
   - capabilities;
   - runtime modes;
   - data modes;
   - verification status.
6. Separate software license from data/content license.
7. Add JSON Schema or equivalent validation.
8. Add tests that reject malformed/duplicate plugin IDs.

**Exit criterion:** all current integrations and Perseus can be described without client-specific fields leaking into the core schema.

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

## Phase 3 — Extract Sefaria and SEDRA into independent plugins

These are already supported and provide a low-risk test of the plugin architecture.

### Tasks

1. Create `plugins/sefaria/`.
2. Move or adapt Sefaria launch/proxy configuration into the plugin.
3. Preserve client transport compatibility.
4. Add Sefaria-specific skill/instructions.
5. Add a known-reference smoke test.
6. Create `plugins/sedra/`.
7. Move Beth Mardutho detection/launch logic into the plugin.
8. Add SEDRA-specific skill/instructions.
9. Add word and lexeme smoke tests.
10. Remove corresponding hard-coded branches from the central config generator only after plugin paths work.

**Exit criterion:** Sefaria and SEDRA can be installed/enabled independently and pass existing verification.

## Phase 4 — Add Perseus

Use `tonyjurg/Perseus-mcp` as the first externally maintained marketplace integration.

### Tasks

1. Determine the upstream-supported installation method and compatible version policy.
2. Create `plugins/perseus/`.
3. Reference upstream rather than vendor it.
4. Add launcher/configuration only where needed.
5. Add a skill covering CTS URNs, corpus/edition discovery, passage retrieval, Scaife search, and known resource distinctions/limitations.
6. Add smoke tests for MCP initialization, resource discovery, retrieval of a stable known passage, and a representative search where upstream behavior is stable.
7. Record software license and upstream data-service caveats.
8. Test in Claude, Codex, and Antigravity.

**Exit criterion:** installing the Perseus plugin gives a working, documented Perseus MCP integration without copying the upstream implementation into this repository.

## Phase 5 — Refactor Text-Fabric into a provider plugin

This is the largest structural change.

### 5.1 Separate corpus registry from runtime

Create:

```text
plugins/text-fabric/
├── plugin metadata
├── skills/
├── scripts/
└── registry/
```

Move corpus metadata out of Python constants where practical.

### 5.2 Define TF corpus schema

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

### 5.3 Replace bespoke acquisition where possible

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

If this requires changes to `cfabric-mcp`, keep them as a separable upstream contribution rather than embedding a permanent fork in the marketplace.

### 5.5 Add corpus discovery

Provide agent-facing operations or supporting tooling for:

- list known corpora;
- filter by language/discipline;
- list installed corpora;
- install/prepare corpus;
- inspect corpus metadata/features.

### 5.6 Handle collections

Treat `pthu/greek_literature` as a collection rather than thousands of marketplace plugins. Retain the existing catalog-building work and convert it into collection metadata/search.

**Exit criterion:** the TF plugin can install/load at least the existing workshop corpora from registry metadata and can represent large collections without top-level plugin explosion.

## Phase 6 — Import the wider Text-Fabric ecosystem

After the TF provider is generic:

1. Seed from the official Text-Fabric corpus/app list.
2. Search for additional public TF repositories.
3. Validate repository structure and licensing.
4. Add metadata.
5. Smoke-test representative corpora.
6. Mark untested integrations Community rather than Verified.
7. Add CI matrices in batches to keep runtime manageable.
8. Add collection-level indexing where repositories contain many works.

Do not block marketplace launch on exhaustive TF coverage.

**Exit criterion:** coverage is broad, registry-driven, and adding another TF corpus normally requires metadata plus tests rather than Python code.

## Phase 7 — Add profiles

Create declarative profiles:

- `summer-school`
- `classics`
- `biblical-studies`
- `assyriology`
- `semitic-languages`

### Tasks

1. Define profile schema.
2. Allow profiles to select plugins.
3. Allow provider-specific selections, especially TF corpora.
4. Reproduce the current workshop installation as `summer-school`.
5. Make `setup.sh` a compatibility/convenience frontend to the profile mechanism.
6. Keep profiles optional: users must still be able to install individual plugins.

**Exit criterion:** the existing workshop setup can be reproduced from a profile with no loss of functionality.

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

**Exit criterion:** a newly installed plugin provides enough domain context for a capable model to make correct first attempts without reading the repository README.

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

**Exit criterion:** "Verified" is machine-enforced rather than an informal label.

## Phase 10 — Documentation and repository identity

Once the new structure is usable:

1. Rewrite README around Agora marketplace installation and discovery.
2. Keep a short workshop quick start.
3. Document how to install the marketplace and plugins, add a third-party MCP, add a TF corpus, understand verification, licensing policy, upstream policy, and client compatibility.
4. Generate plugin/resource tables from registry data.
5. Preserve historical attribution and links to upstream projects.

**Exit criterion:** a contributor can add a straightforward external philological MCP plugin by following documentation without modifying central runtime code.

## Phase 11 — Expand beyond current integrations

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

For each candidate, record scholarly scope, upstream authority, access mechanism, software and data licenses, authentication requirements, local/remote mode, MCP implementation status, maintenance activity, client compatibility, and proposed smoke test.

## Migration sequence

```text
baseline tests
→ registry
→ manifest generation
→ Sefaria plugin
→ SEDRA plugin
→ Perseus plugin
→ Text-Fabric provider refactor
→ TF corpus expansion
→ profiles
→ skills
→ common verification
→ documentation
→ additional scholarly services
```

Do not begin by reorganizing every file or importing every known corpus.

## Non-goals for the first release

- writing new MCP adapters for every desirable scholarly database;
- supporting every TF corpus before marketplace release;
- creating one plugin per Greek work or TF corpus;
- vendoring all upstream MCP servers;
- guaranteeing identical capabilities across all clients;
- hiding upstream licensing restrictions;
- replacing the original data providers.

## First-release milestone

A good `v0.1` marketplace should contain four independently usable Verified plugins:

1. Text-Fabric / ContextFabric
2. Perseus
3. Sefaria
4. SEDRA

It should also provide:

- canonical registry;
- generated Claude + ChatGPT/Codex marketplace metadata;
- Antigravity-compatible packaging/configuration;
- `summer-school` profile;
- existing CUC/BHSA/Greek workshop functionality;
- real integration tests;
- plugin-specific scholarly skills;
- contributor documentation.

This is enough to validate the architecture before importing dozens of resources.

## Definition of done

The work is complete when Agora is primarily a curated digital-philology marketplace rather than a monolithic workshop MCP configuration, while the workshop remains reproducible as one profile of the broader system.
