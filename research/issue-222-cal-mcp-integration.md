# #222 — released CAL-MCP integration into Agora post-1.0

Date: 2026-10-12. Issue: [Agora#222](https://github.com/alexsosn/Agora/issues/222), upstream [CAL-MCP#16](https://github.com/alexsosn/CAL-MCP/issues/16).

## Verified release and ownership

- Upstream [v0.1.0](https://github.com/alexsosn/CAL-MCP/releases/tag/v0.1.0) was published from tag commit `d8aa7fe269198ee37b4da8d71f5ed2f7eb5fe1fb`. [Release CI](https://github.com/alexsosn/CAL-MCP/actions/runs/38178217487) successfully verified wheel+sdist clean installs, 36-tool stdio MCP surface, bounded installed-wheel 12-case CAL smoke, PyPI publication and GitHub Release.
- Upstream `pyproject.toml`: published `cal-mcp==0.1.0`, command `cal-mcp` with no args, local stdio, Python >=3.11, MIT software; remote `https://cal.huc.edu/` data and terms are upstream-dependent. [CAL-MCP Agora handoff](https://github.com/alexsosn/CAL-MCP/blob/main/docs/integrations/agora.md) includes an **unverified candidate** `uvx --from cal-mcp==0.1.0 cal-mcp`, explicitly not a completed Agora integration.
- Representative upstream fixed 12-case smoke includes one `cal_lexicon_lookup` with `{"query":"br","lemma_key":"br N"}` expecting `found`. Initial client startup and `list_tools` can be checked offline; live smoke must make *at most one* such CAL request and stop on upstream backpressure, not reproduce the upstream suite.
- CAL-specific semantics belong in upstream, following `CONTRIBUTING.md`, `AGENTS.md`, and `wiki/architecture/ref-plugin-boundary.md`. Agora owns canonical metadata, launch, manifests, verification, not parsing or CAL HTTP client logic.

## Actual Agora constraints

- Four released 1.0 plugin families: context-fabric, perseus, sefaria, sedra, with `registry/plugins.yaml`/ `registry/providers.yaml` and generated client manifests. Published Agora 1.0 and closed tracker #148 mean CAL is a **post-1.0** plugin.
- `registry/v0.1.yaml` is historical/frozen with *exactly four* required plugin IDs and 37 Context-Fabric resources. Both `scripts/validate_registry.py` and `scripts/generate_marketplaces.py` explicitly read that file; `tests/test_generation.py` hardcodes the expected four plugins and checks generated artifacts. **Do not silently alter frozen historical v0.1 scope** to shoehorn CAL in. A prospective release scope must select the extra plugin and be used by validation/generation. Preserve validation of old scope.
- Current plugin evidence requires client-specific checks and explicit dependency environment provenance, not bare marketing claims; `verification.status=verified` requires live evidence, not simply a released upstream package. Start at `community` and record a deterministic generated-manifest check, then upgrade only after both client live paths are observed. Provider health starts `unknown` until real downstream smoke.
- Existing Perseus integration provides a thin `uvx --constraint <plugin-root>/runtime-constraints.txt --from perseus-mcp==1.0.2 perseus-mcp` pattern for Claude and Codex. CAL can follow it with upstream pin `cal-mcp==0.1.0`; use explicit truthful environment/hash and no CAL parser code.
- Current `.github/workflows/external-mcp-smoke.yml` matrix only includes four plugins. The generic smoke harness knows these explicit plugin cases; CAL needs a separate bounded case to produce *genuine* downstream verification and cannot be promoted on startup-only evidence.

## Plan boundary

Expose CAL as a proposed fifth plugin through a **new post-1.0 scope**, regenerate native manifests from the canonical entries, and test offline registry/launch correctness first. Before claiming actual integration, run bounded real one-operation client smoke and independent exact-head review. Do not auto-crawl CAL or run repeated rate-calibration probes.
