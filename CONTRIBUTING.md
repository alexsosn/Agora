# Contributing to Agora

Agora is a clean-slate marketplace for philology and related disciplines.

## Project rule

`mcp-demo` is prior art, not a compatibility target. Code, metadata, tests, and integration knowledge may be reused where their licenses permit, but new Agora components should follow Agora's own plugin and registry architecture. Do not add compatibility shims, legacy paths, or workshop-specific behavior solely to preserve `mcp-demo` interfaces.

## Repository areas

- `registry/` — canonical marketplace, plugin, provider, resource, and release metadata and schemas.
- `plugins/` — Agora plugin integrations, generated native manifests, and scholarly skills.
- `profiles/` — optional curated plugin/resource bundles.
- `scripts/` — repository tooling, generators, and validators.
- `tests/` — unit and integration tests.
- `generated/` — reserved for generated artifacts without client-mandated native paths.
- `wiki/` — design and research notes.

The detailed architecture and implementation sequence are documented in `wiki/research.md` and `wiki/plan.md`.

## Generated files

Claude Code and ChatGPT/Codex marketplace/plugin metadata is generated from the canonical registry:

```bash
python scripts/generate_marketplaces.py
```

Do not hand-edit:

- `.claude-plugin/marketplace.json`;
- `.agents/plugins/marketplace.json`;
- `plugins/*/.claude-plugin/plugin.json`;
- `plugins/*/.codex-plugin/plugin.json`.

Change the canonical registry or generator and regenerate instead. CI enforces freshness with:

```bash
python scripts/generate_marketplaces.py --check
```

Antigravity artifacts are not part of the current v0.1 generation target.
