# Agora #223 — ORACC-TF v1.0.0 registered release acquisition

## Research (2026-10-11, immutable published evidence)
- Upstream GitHub Release `alexsosn/ORACC-TF@v1.0.0`, published 2026-10-11 09:37:52 UTC, commit `60db4b724a687c0f425e78eae924fce89454e106`.
- Asset `assyrian-royal-inscriptions-1.0.0.zip`: 41,285,702 B; published asset SHA-256 `788f580604e30054fab34c4c3ea60ec3eb4f399412f1da90f778469d03507468`. Published separately verified `.sha256` sidecar. Upstream fresh independent TF-only install/browser acceptance PR #156 merged; source release issues #23/#83/#89/#155 closed.
- Unlike an ordinary Git-backed resource, corpus data is in a *release ZIP*, not the ORACC-TF builder repository. Upstream docs specify archive root `manifest.json`, `tf/<tf_version>/`, `app/`, `docs/`; `manifest.json` provides dataset, release_id, tf_version, tf_root, builder_commit, source_state.
- Agora `release_archive.staged_verified_tf_zip` already checks sha256, central directory, dangerous paths, duplicate names, safe TF headers, bounded expansion and portable features. It intentionally does *not* download or publish. `ContextFabricResolver.prepare` handles only repository, collection and user-local paths; existing cache store accepts snapshots under `snapshots/<resource>/<revision>/corpora/__root__`, with transitions, object leases and eviction.
- Upstream licence scope is *not* the builder's MIT: ORACC corpusjson has mixed CC0 and disputed upstream CC BY-SA 3.0 claims; official TEI translations require qualified upstream CC BY-SA 3.0 attribution. Keep conservative redistribution and source-specific rights.

## Implementation boundaries
1. RED-first tests: registry rejects incomplete/mutable release descriptors; canonical bundled catalog supports one `github-release-archive` resource; offline never fetches; exact digest and manifest identity checked; checksum changes or malformed ZIP do not publish; existing destination corruption fails closed; no Git clone; source provenance and TF version stay stable; successful cached reload reuses same path.
2. Add typed declarative `github-release-archive` acquisition strategy for corpus only with immutable commit, exact release tag/asset/sha256/size and dataset/release metadata. No `latest`, ambient URL, converter execution or guessed Git TF path.
3. Add HTTPS/allowlisted-host bounded download, existing pinned staged TF extraction, manifest-vs-descriptor checks, one cache-key lock, atomic registered snapshot publication, verified receipt and reuse. Respect source_mode offline/require-fresh and operation time/cancellation. Never extract scripts or arbitrary app code into the managed TF cache.
4. Register only `assyrian-royal-inscriptions` from release v1.0.0 (RIAO+RINAP). Record mixed source/data rights and source-specific limitations; keep verification `community` until full consumer CI passes.
5. Exact-head Foundation + dedicated real public release clean-cache/TF query/offline smoke; independent skeptical review of real asset, malicious fixtures, cache tampering, redirects, path/manifest hazards, budget/cancellation and source-provenance claims.

## Explicit non-goals
- Cloning the multi-GB ORACC builder/source monorepo.
- Adding all ORACC subprojects as a collection.
- Running the third-party converter or hosting a standalone Text-Fabric web app through the Agora MCP plugin.
- Replacing upstream's per-project licensing claims with a blanket MIT/CC0 assertion.

## Published-release identity correction
The GitHub **distribution release ID** is `1.0.0`, while the **Text-Fabric data schema** is `0.4.0` (`TF_VERSION` from immutable ORACC-TF `v1.0.0` commit `programs/oracc_tf/__init__.py`). The exact archive manifests `tf/0.4.0`, not `tf/1.0.0`. Keep these independently pinned; the builder package is `0.1.0`.
