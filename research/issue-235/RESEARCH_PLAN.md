# #235 — one authoritative immutable materializer release pin

## Research: actual active dependencies (2026-10-11)

The canonical live Coptic materializer release pin is the 40-hex `ref` for `copticscriptorium-tf` in `registry/materializers.yaml`; currently `3cde20ec41efb1cacf1710643f01f924f11cbf0b` at reviewed upstream `alexsosn/CopticScriptorium-TF`. Following PR #234, identical **plugin release** SHA literals are duplicated in:
- `.github/workflows/coptic-registered-full-source.yml` install-preflight;
- `tests/test_copticscriptorium_materializer_registry.py` static registry assertion;
- `tests/test_issue214_coptic_full_registered.py` static acceptance assertion;
- `tests/live_issue214_full_coptic.py` native-TF and runtime receipt verification.

These are redundant references **to the same installed package identity**. They must not be confused with independent immutable *upstream TT source* `CopticScriptorium/corpora@3ac067f1709a0012daf39ea8da2fac79980176a5`, Coptic-to-LXX module or source-byte identity, which remain independently verified. The currently installed Agora materializer path (`scripts/agora_install_materializer.py`) already verifies `git rev-parse HEAD` equals `plugin['ref']`, and installation receipt `plugin.commit` equals the same value while enforcing execution identity checks. The full runtime acceptance uses registered exact plugin installation, tests automatic pinned sparse upstream Git acquisition, retains non-redistribution and live TF + Context-Fabric MCP load/search/unload/remove.

**Observed failure:** PR #234 changed canonical Coptic registry ref but left a duplicate workflow literal stale; real full-source run 38083800417 failed before acquisition even though the registry ref itself was reviewed. The repaired #234 final run 38083907986 passed all real conversion and MCP checks.

## Plan and security constraints

1. Preserve `registry/materializers.yaml` as the single authoritative Coptic release SHA. Do **not** replace with moving `main`, a Git tag, or an unverified short SHA; require exact 40-hex lower-case SHA and pinned repository identity.
2. Add RED unit tests: a) the current release SHA does not occur literally anywhere in the *active dependent workflow/tests* (historical research prose excluded); b) load_registry rejects mutable/invalid refs; c) live acceptance compares installation receipt `plugin.commit` to the current registry `plugin.ref`, not to another constant; d) the full Git checkout and `execution_identity_sha256` checks remain.
3. GREEN: remove redundant literals from those four active surfaces, dynamically obtaining `plugin['ref']` **from canonical local registry at checked-out exact head**. Never use remote mutable state in the expected value.
4. Keep immutable Coptic TT source commit, sparse patterns, explicit third-party code approval, sandbox network denial, and native TF graph/MCP acceptance unchanged. An intentionally mutated installation receipt/manifest must still be rejected by the existing registered installer and runner rather than accepted merely because its SHA is well formed.
5. Compare old four duplicate literal touch points vs after single canonical registry ref; run exact-head Foundation, registered-install smoke, sandbox E2E and real full-source acceptance; independent skeptical review must re-check the active Git paths and actual source/receipt identity checks. Close #235 only after successful CI.

## Exclusions

No source conversion algorithm change, no mass pin change for other independent upstream corpora, no hardcoded constant spread into additional modules, and no bypass of installer checks, reviewed-registry pull requests, or full-data acceptance.
