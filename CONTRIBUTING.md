# Contributing to Agora

Agora is a clean-slate marketplace for philology and related disciplines.

## Project rule

`mcp-demo` is prior art, not a compatibility target. Code, metadata, tests, and integration knowledge may be reused where their licenses permit, but new Agora components should follow Agora's own plugin and registry architecture. Do not add compatibility shims, legacy paths, or workshop-specific behavior solely to preserve `mcp-demo` interfaces.

## Repository areas

- `registry/` — canonical marketplace metadata and schemas.
- `plugins/` — Agora plugin integrations and scholarly skills.
- `profiles/` — optional curated plugin/resource bundles.
- `scripts/` — repository tooling, generators, and validators.
- `tests/` — unit and integration tests.
- `generated/` — generated marketplace artifacts that are intentionally committed.
- `wiki/` — design and research notes.

The detailed architecture and implementation sequence are documented in `wiki/research.md` and `wiki/plan.md`.

## Generated files

Generated marketplace artifacts are committed only when a target client requires a file at a stable repository path or when committing the artifact materially improves installation/discovery. Other derived output should be produced in CI or locally and remain untracked.

Every committed generated artifact must eventually have a deterministic generator and a CI freshness check. Phase 0 establishes this policy; the generators themselves are Phase 2 work.
