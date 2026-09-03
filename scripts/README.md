# Scripts

Repository tooling lives here: registry validation, deterministic marketplace generation, verification helpers, and maintenance scripts.

## Registry validation

```bash
python scripts/validate_registry.py
```

Validates Agora's canonical marketplace, plugin, provider, resource, collection, vocabulary, and v0.1 scope documents.

## Marketplace generation

```bash
python scripts/generate_marketplaces.py
```

Generates the native Claude Code and ChatGPT/Codex marketplace/plugin metadata from the canonical registry.

Use the freshness-only mode in CI or before committing registry changes:

```bash
python scripts/generate_marketplaces.py --check
```

Phase 2 intentionally does not generate Antigravity artifacts.

## Context-Fabric source coverage

```bash
python scripts/audit_context_fabric_sources.py
```

Audits every Context-Fabric resource in the fixed v0.1 catalog using upstream Git tree metadata. The report records the resolved source revision, discovered TF-root count, and selected root for ordinary corpora; collection roots are reported without materializing corpus blobs.

This is an installation and source-resolution check. It does not assess upstream corpus semantics, data quality, or research suitability.
