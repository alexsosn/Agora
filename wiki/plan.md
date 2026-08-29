# Plan: Building Agora as a Digital Philology Marketplace

Agora is a fresh repository. `mcp-demo` is prior art and a source of reusable code/knowledge, not a compatibility target. The fixed first-implementation scope is defined in [`wiki/v0.1-scope.md`](v0.1-scope.md) and machine-enforced by `registry/v0.1.yaml`.

## Phase 0 — Establish Agora's foundation

**Status: implemented.**

Completed:

- canonical repository layout;
- MIT project license and contribution policy;
- clean-slate rule relative to `mcp-demo`;
- generated-artifact policy;
- baseline GitHub Actions workflow.

**Exit criterion met:** Agora has a marketplace-first skeleton independent of the old demo repository.

## Phase 1 — Canonical marketplace and resource data model

**Status: implemented.**

Completed:

- `registry/plugins.yaml` — four v0.1 plugin families: `context-fabric`, `perseus`, `sefaria`, `sedra`;
- `registry/providers.yaml` — provider/runtime boundary for each family;
- `registry/resources.yaml` — all 35 Context-Fabric catalog resources plus TLHdig-TF;
- `registry/vocabularies.yaml` — controlled languages, disciplines, capabilities, runtime/data modes, resource kinds, acquisition strategies, and verification states;
- `registry/v0.1.yaml` — machine-readable fixed release contract: 4 plugins and 36 Context-Fabric resources;
- JSON Schemas for plugins, providers, resources, collection indexes, and release scope;
- explicit separation of plugin/integration status from resource/data status;
- explicit separation of software license, data/content license, redistribution status, and service terms;
- resource-level provenance and known-issue fields;
- collection model for repositories containing many independent TF corpora;
- collection-index contracts for `pthu/bible`, `pthu/patristics`, and `pthu/greek_literature`;
- `scripts/validate_registry.py`;
- negative tests for malformed IDs, duplicates, broken references, and unknown controlled-vocabulary values;
- CI validation of the canonical registry and fixed v0.1 scope.

The three PTHU collection indexes are intentionally present but `pending`; enumerating and testing their individual TF members belongs to Phase 3.

TLHdig-TF is registered as Experimental without pinning a stale TF data path/version. The current upstream layout must be resolved during implementation.

**Exit criterion met:** every v0.1 resource can be represented without client-specific fields leaking into the canonical schema, and the model is enforced in CI.

## Phase 2 — Generate marketplace manifests

**Status: implemented for Claude Code and ChatGPT/Codex. Antigravity is intentionally deferred.**

Completed:

- re-checked the current native Claude Code and OpenAI Codex plugin/marketplace formats;
- added platform-neutral `registry/marketplace.yaml` publisher/catalog metadata plus JSON Schema validation;
- implemented `scripts/generate_marketplaces.py`;
- generated `.claude-plugin/marketplace.json`;
- generated `.agents/plugins/marketplace.json`;
- generated per-plugin `.claude-plugin/plugin.json` for all four v0.1 plugins;
- generated per-plugin `.codex-plugin/plugin.json` for all four v0.1 plugins;
- kept client-specific category/policy/presentation defaults in generator adapters rather than leaking them into scholarly resource metadata;
- made output ordering deterministic from `registry/v0.1.yaml`;
- derived plugin semantic version `0.1.0` deterministically from the `v0.1` release identifier;
- added `--check` mode for missing/stale generated files;
- added tests for native output paths, ordering, Codex local-source/policy shape, Claude local sources, version conversion, freshness, and the explicit absence of Antigravity output;
- added CI freshness enforcement.

The native artifacts live at client-required paths rather than under `generated/`. The generator is their only source of truth.

The generated plugin manifests are deliberately metadata-only in Phase 2. They do not declare MCP servers, skills, hooks, or apps that have not yet been implemented. Runtime-specific declarations are added in Phases 3–5.

**Design rule:** the canonical registry is the source of truth; generated client files are projections of it.

**Exit criterion met:** one registry edit deterministically updates all currently supported marketplace representations, and CI fails if committed projections become stale.

## Phase 3 — Implement Context-Fabric and the 36-resource baseline

**Status: next.**

This is the main corpus implementation phase, not a representative-corpus prototype.

### Provider/runtime

Create `plugins/context-fabric/` with the runtime adapter, resource resolver, acquisition/cache logic, and Context-Fabric-specific instructions.

Target flow:

```text
resource/member ID
→ resolve canonical registry metadata
→ acquire/cache required TF data
→ determine actual TF corpus path
→ compile/load with Context-Fabric
→ expose through Context-Fabric MCP
```

Canonical metadata must not contain machine-specific absolute paths.

### All 36 resources

The plugin must resolve and prepare every resource in `registry/v0.1.yaml`, not only BHSA/CUC examples.

Use supported Text-Fabric/Context-Fabric acquisition mechanisms where practical. Full Git clones should not be the default when a narrower reliable method exists.

### Collection resources

Populate the pending member indexes for:

- `pthu/bible`;
- `pthu/patristics`;
- `pthu/greek_literature`.

Each member should receive a stable internal ID, repository-relative TF location, useful author/title/canonical identifiers where available, and member-level status.

Collection members remain independent TF corpora. Agora must not assume common node types, section models, or feature sets across Greek works.

Member acquisition/loading should be lazy where practical; using one Greek work must not require loading the entire collection.

### TLHdig-TF

Resolve the current actual TF dataset location/version from upstream rather than relying on an older README path. Preserve upstream known-issue warnings and Experimental status unless upstream validation improves.

### Generated plugin metadata

Once the Context-Fabric runtime exists, extend the generated Claude/Codex plugin package with the real MCP declaration and any required launcher/configuration files. Do not hand-edit the generated metadata fields that belong to Phase 2.

### Testing

Use layered CI:

1. registry and resolver checks for all 36 resources;
2. lightweight end-to-end tests on small representative corpora on normal PRs;
3. representative collection-member tests;
4. scheduled/batched tests for larger resources;
5. per-resource/member known-issue status.

**Exit criterion:** all 36 resources can be resolved through the Context-Fabric plugin, and collection members can be discovered and loaded independently.

## Phase 4 — Implement Perseus, Sefaria, and SEDRA

### Perseus

Integrate upstream `tonyjurg/Perseus-mcp` without vendoring it. Add installation/version policy, launch metadata, CTS/URN guidance, resource discovery guidance, and smoke tests for initialization, passage retrieval, and search.

### Sefaria

Use the official Sefaria Texts MCP endpoint. Add client transport adaptation only where necessary, plus reference/search/link/dictionary guidance and known-reference tests.

### SEDRA

Create the Agora SEDRA adapter around Beth Mardutho SEDRA IV. Resolve and document the adapter's software provenance/licensing, preserve the distinction between lexeme and word lookup, and add representative Syriac lexical tests.

**Exit criterion:** all three integrations install/connect independently of Context-Fabric and pass representative MCP operations.

## Phase 5 — Scholarly skills

Add concise, source-grounded skills/instructions for:

- Context-Fabric graph/search/feature discovery and corpus switching;
- BHSA/ETCBC morphology and syntax features;
- CUC/Ugaritic conventions;
- TLHdig-TF morphology, ambiguity nodes, damage/editorial apparatus, and known limitations;
- Greek collection discovery and per-work schema inspection;
- Perseus CTS/edition/search workflows;
- Sefaria references/links/dictionaries;
- SEDRA word/lexeme semantics.

**Exit criterion:** a capable model can make correct first attempts after installing a plugin without reverse-engineering repository internals.

## Phase 6 — Verification and trust layer

Machine-enforce separate verification scopes.

### Plugin/integration checks

- installation or endpoint resolution;
- server startup/reachability;
- MCP initialization;
- tool enumeration;
- representative operation;
- version/provenance recording.

### Resource/member checks

- upstream availability;
- acquisition resolution;
- loadability;
- representative text/feature access;
- license/provenance metadata;
- known issues;
- resource/member status.

Statuses remain `verified`, `community`, and `experimental`. Plugin verification must never automatically promote all resources underneath it.

**Exit criterion:** status labels describe a defined, CI-enforced level of evidence.

## Phase 7 — Documentation and optional profiles

Document marketplace installation, plugin installation, resource discovery, collection semantics, adding an MCP/plugin, adding a Context-Fabric resource, verification policy, licensing policy, upstream policy, and client compatibility.

Generate resource/plugin tables from the registry where practical.

Optional profiles such as `classics`, `biblical-studies`, `assyriology`, and `semitic-languages` may be added as declarative convenience bundles. They are not compatibility layers for `mcp-demo`.

## Phase 8 — Post-v0.1 expansion

After the fixed implementation works, investigate additional open scholarly providers and MCPs, including:

- ORACC / ePSD / CDLI;
- papyri.info and papyrological resources;
- epigraphic databases;
- IIIF/manuscript tooling;
- morphology and lexicography services;
- prosopographical/entity-linking resources;
- bibliographic discovery;
- additional philological MCP servers;
- new Context-Fabric catalog entries;
- additional client adapters, including Antigravity if useful.

## Recommended sequence

```text
Phase 0 foundation                  ✓
→ Phase 1 canonical registry        ✓
→ Phase 2 Claude/Codex generation   ✓
→ Phase 3 Context-Fabric + 36 resources   NEXT
→ Phase 4 Perseus + Sefaria + SEDRA
→ Phase 5 scholarly skills
→ Phase 6 verification/trust layer
→ Phase 7 documentation/profiles
→ Phase 8 expansion/client adapters
```

## Non-goals for v0.1

- preserving `mcp-demo` interfaces or workshop behavior;
- writing new adapters for every desirable scholarly database;
- flattening individual Greek TF works into marketplace plugins/resources;
- vendoring third-party MCP implementations unnecessarily;
- pretending all clients have identical capabilities;
- requiring Antigravity support in the first implementation;
- inventing licenses or hiding unknown licensing status;
- treating inclusion as proof that an upstream dataset is research-grade.

## v0.1 definition of done

Agora v0.1 requires:

1. a working Context-Fabric plugin covering all 36 fixed resources;
2. member-aware support for the PTHU Greek collections;
3. working Perseus-MCP, Sefaria, and SEDRA integrations;
4. deterministic Claude Code and ChatGPT/Codex marketplace manifests;
5. resource-level provenance, licensing, and verification metadata;
6. representative integration and scholarly tests;
7. plugin/resource-specific scholarly guidance;
8. contributor documentation.
