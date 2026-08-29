# Generated artifacts

Agora generates client-specific marketplace files deterministically from the canonical registry.

## Native-path policy

Platform-required artifacts are committed at the paths their clients require rather than duplicated under this directory:

- `.claude-plugin/marketplace.json` — Claude Code marketplace catalog;
- `.agents/plugins/marketplace.json` — ChatGPT/Codex marketplace catalog;
- `plugins/<id>/.claude-plugin/plugin.json` — Claude plugin metadata;
- `plugins/<id>/.codex-plugin/plugin.json` — Codex plugin metadata.

`generated/` remains reserved for future derived artifacts that do not have a client-mandated repository path.

## Source of truth

The generator reads:

- `registry/marketplace.yaml`;
- `registry/plugins.yaml`;
- `registry/v0.1.yaml`.

The canonical scholarly/provider/resource registry remains platform-neutral. Client-specific policy and presentation defaults live in the generator adapters.

## Regeneration

```bash
python scripts/generate_marketplaces.py
```

Check committed output without modifying files:

```bash
python scripts/generate_marketplaces.py --check
```

Every committed generated artifact has:

1. a deterministic generator;
2. a documented source of truth;
3. a CI freshness check.

Phase 2 targets Claude Code and ChatGPT/Codex. Antigravity generation is intentionally deferred.
