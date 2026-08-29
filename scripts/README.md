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
