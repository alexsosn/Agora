# #267 — Tischendorf morphology module: pinned upstream research and plan

Date: 2026-10-12.

## Source/data evidence
Canonical source: `codykingham/tischendorf_tf` at immutable master revision `ca96bd44f38fd716d4a1faa6d451f3716f0dce46`.
Parent is already registered in Agora as `tischendorf_tf` (no pinned revision), native `tf/2.8/`. Inspected `otype.tf` declares 1–137711 word slots, 27 books, 262 chapters, 732 paragraphs, 7951 verses and 5394 lexeme nodes, largest ID 152077. The source's `LICENSE` declares the text **and analysis public domain**, and its README credits Ulrik Sandborg-Petersen, G. Clint Yale, Maurice A. Robinson and converter Cody Kingham; the morphology-addition headers additionally name Oliver Glanz.

Source directory `FeatureAdditions/` has exactly 14 non-warp `.tf` files: `case.tf`, `freq_lex_og.tf`, `gn.tf`, `lex_abc.tf`, `lex_og.tf`, `mood.tf`, `nountype.tf`, `nu.tf`, `originterrdiff.tf`, `prntyp.tf`, `ps.tf`, `sp.tf`, `voice.tf`, `vt.tf`. It also has an unrelated plain file named `test` which must not be acquired as a module feature. The TF feature names do not collide with any of the 17 parent `tf/2.8/*.tf` basenames.

Direct samples show `case.tf` string entries (e.g. nominative/genitive), `ps.tf` person values, `freq_lex_og.tf` an integer frequency field and `lex_og.tf` Greek lexical transliteration. The four sampled headers contain proper Text-Fabric `@node` feature metadata.

## Existing Agora path, no new abstraction
`GitStore.feature_files()` finds direct-child `*.tf` in any repository directory, rejects warp files, and ignores `test`. `GitStore.materialize_feature_module()` snapshots exactly those files, while `ContextFabricResolver._overlay()` preserves parent `otype.tf`/`oslots.tf`. Thus register `upstream.repository: codykingham/tischendorf_tf`, `upstream.tf_path: FeatureAdditions`, `upstream.module: codykingham/tischendorf_tf/FeatureAdditions`, `upstream.ref: ca96...ce46`.

Parent is currently unpinned in Agora, so a module `parent-base` dependency **must require that same immutable commit**. Without this, future parent changes might silently misalign word/lexeme IDs. If an operator has a different parent revision, fail closed with the existing resolver's error instead of loading misaligned morphology.

## Gates
1. RED registration test before canonical edits: one discoverable optional `tischendorf-morphology-additions` feature module; schema; provenance; parent ID, version 2.8, exact pinned source/revision and `parent-base`; 14 expected canonical names; no duplicate or parent warp files; bundled module catalog equality; parent-only remains independent.
2. GREEN canonical registration, generator outputs (plugin module catalog and researcher guide), precise cardinality regression adjustment; never silently override original parent features.
3. **Real pinned-data integration CI**, not only README: verify GitStore snapshots exactly 14 files from `FeatureAdditions`; node ranges bounded by 152077; no missing/duplicate/parent-colliding names; compare parent-only and module-enabled load/cold-warm navigation and representative morphology values. Reject unexpected missing features and node identity mismatches.
4. Logically independent adversarial diff/data review, exact-head CI and live source acceptance before merge. Keep integration status `community` pending actual checks. No licensed dataset duplication or converter execution.

Upstream links:
- https://github.com/codykingham/tischendorf_tf/blob/ca96bd44f38fd716d4a1faa6d451f3716f0dce46/tf/2.8/otype.tf
- https://github.com/codykingham/tischendorf_tf/tree/ca96bd44f38fd716d4a1faa6d451f3716f0dce46/FeatureAdditions
- https://github.com/codykingham/tischendorf_tf/blob/ca96bd44f38fd716d4a1faa6d451f3716f0dce46/LICENSE

Research evidence proves source identity and design compatibility, **not** that a live compound Context-Fabric load has passed.

## Real-source CI observation (2026-10-12)

At exact-head Actions run 38242611873, the initial smoke failed because it assumed the immutable GitStore *snapshot* contained only `*.tf` files. The actual `_gitstore._export_snapshot` archives all files under `FeatureAdditions` (including the non-TF `test`). `ContextFabricResolver._link_features` correctly composes only `*.tf` files, rejecting warp override. The RED regression is committed before the GREEN fix: verify the final **overlay** excludes `test`, do not falsely demand the source snapshot drop unrelated files. The 14 feature-name oracle and exact source pin remain intact.
