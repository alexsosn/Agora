# #226: Register published Pseudepigrapha-TF on the shared archive resolver

## Research — immutable upstream facts (11 October 2026)
- [Pseudepigrapha-TF v1.0.0](https://github.com/alexsosn/Pseudepigrapha-TF/releases/tag/v1.0.0) published 2026-09-17, immutable tag commit `7c4b757bb543a110ae9a252d1281835859136852`.
- Data-only native `tf-1.0.zip`: 9,632,449 B, GitHub SHA256 `d2dfad7e643699617a9493b9f5d724868f8027dd5f2e88bd558451e3e7819b7a`. 96 native TF features / 101,762,166 uncompressed TF feature bytes; **flat ZIP TF root**. Stock Text-Fabric `complete.zip` is a different layout/asset (9,643,332 B, SHA256 `1ea4488202d1e9fbc008abaabff14f220328118fc52bed3a06a2d331b145bb7d`). Pin **only one archive**, not both, and never use `latest`.
- Native TF data version `1.0`; source work `1En__Ethiopic`; representative section `('1En__Ethiopic','1','2')` and `source_ref`. Apparatus `reading_of`, `witness`, `is_primary`; generated English/French translation `version_kind=generated_translation` and `translation_of` / `translation_unit_of`. These are not historical witnesses.
- OCP textual editions and TEI XML `static/docs/` are **CC BY 4.0**, pinned source `c939dcbacad78c5d18d2c4282cad23c47e19ac07`; OCP app is GPL-3.0, converter code MIT. Source-level edition/editor attributions in OCP `intros.json` must be preserved. References: [DATA_LICENSE.md](https://github.com/alexsosn/Pseudepigrapha-TF/blob/v1.0.0/DATA_LICENSE.md).
- Agora already merged generic `github-release-archive` resolver and `ReleaseSnapshots` (#260), with cumulative source checks, published-asset CRC/digest, bounded extraction, per-feature integrity receipts, `.tf/` and `.cfm/` derived cache handling, and network-denied warm reload. The first published Pseudepigrapha release already passed the generic direct TF-core native load + offline resolver smoke but is **not yet a discovered corpus**.
- The existing registered `pseudepigrapha-tf` is an explicit-approval **converter/materializer**, not this corpus, and must remain separately supported.

## Plan, RED → GREEN → real tests → independent review
1. **RED:** registered `pseudepigrapha` appears in canonical and bundled Context-Fabric catalogs with exact `acquisition.archive` identity and tagged source commit; clear CC-BY-4.0 content provenance, permit-with-attribution status, and separately labeled source/translation/witness features. Missing/changed digest/version/asset and a bogus concurrent legacy release field fail before network. No Git clone on default version/describe/offline cold miss. Converter remains separately present.
2. **GREEN:** Add one post-1.0 corpus entry; regenerate canonical bundled catalog and researcher catalog/guide, preserve 37-item frozen v1 baseline, adjust explicit snapshot tests from 38 to 39, add minimal research guidance without conflating apparatus with machine translations.
3. **Real public archive workflow:** exact PR head, pinned HTTPS digest/bytes, fresh managed Context-Fabric prepare/load/query `T.nodeFromSection(('1En__Ethiopic','1','2'))`, nonempty source text/`source_ref`, no unapproved converter; inspect historical apparatus and generated-translation semantics by actual feature oracles (don't guess missing edges), unload and fully network-blocked offline reload from new service instance. Never claim that generated translations are historical witnesses. Measure cache bytes and loading time as observation only.
4. Run full exact-head Foundation/catalog/regression/collection/load CI, independent adversarial review grounded in exact real source and workflow; approve/merge only with passing gates. Rebase onto `main` once ORACC #261 merges. Separate release certification and full OCP scholarly coverage remain out of scope.

## Rejected approaches
- Registering generated TF as a guessed committed `upstream.tf_path` under upstream Git.
- Running the converter or cloning OCP when users request the released corpus.
- Using the stock `complete.zip` and flattening nested paths ad hoc when flat digest-pinned `tf-1.0.zip` is available.
- Treating GPL software, MIT converter, CC BY text or generated translations as a single unqualified license/status.
