# #203 research and implementation plan — Aleppo Text-Fabric native corpus

Date: 2026-10-12. This ticket registers an existing published **native corpus**; there is no converter to run or output data to relicense. Do not conflate the separate reverse BHSA projection with the Aleppo corpus itself.

## Primary upstream data inspected before implementation

- Exact immutable upstream source revision: `MartijnNaaijer/aleppo@db38ddc918fd5d6e47a118f24545bd925975a597` (main as observed on 2026-10-12), not a floating branch.
- [`tf/1.0/otype.tf`](https://github.com/MartijnNaaijer/aleppo/blob/db38ddc918fd5d6e47a118f24545bd925975a597/tf/1.0/otype.tf) directly declares slots `1-426562 word`, nodes `426563-426601 book` (39), `426602-427530 chapter` (929), `427531-450732 verse` (23,202).
- Actual upstream [`tf/1.0/otext.tf`](https://github.com/MartijnNaaijer/aleppo/blob/db38ddc918fd5d6e47a118f24545bd925975a597/tf/1.0/otext.tf) declares `@version=1.0`, `@sectionTypes=book,chapter,verse`, `@license=CC-BY-SA 4.0`, attribution to Hebrew Wikisource `מקרא על פי המסורה` and says the edition fills lost codex parts from related Tiberian manuscripts. First observed copy downloaded 2026-10-09.
- [`aleppo_extant.tf`](https://github.com/MartijnNaaijer/aleppo/blob/db38ddc918fd5d6e47a118f24545bd925975a597/tf/1.0/aleppo_extant.tf) is an integer node feature **on verses**, 1 if a verse is wholly or partly on a surviving codex page and 0 if the edition uses related witnesses. At upstream HEAD its first verse rows (Genesis) are `0`.
- Upstream documentation identifies 7,965 lost verses out of 23,202, explains BHSA-aligned word segmentation and the `bhsa` / `bhsa_seg` features, including 30 BHSA words without Aleppo target and one Aleppo word without BHSA target; it notes 118 numbered-verse differences. The reverse projection `tf/bhsa-mapping/2021/aleppo.tf` is an **extra feature module** (not part of the native `tf/1.0` corpus). The corpus's `bhsa` node field is a *reference to* BHSA 2021 node IDs and does not establish compatibility with other BHSA versions.
- Observed root TF feature set includes `otype.tf`, `oslots.tf`, `otext.tf`, `g_word_utf8.tf`, `g_word_norm.tf`, `bhsa.tf`, `bhsa_seg.tf`, `aleppo_extant.tf`, `qere_utf8.tf`; no GitHub Release ZIP was assumed.

## TDD and implementation gates

1. RED before registry edits: `tests/test_aleppo_registration_203.py` requires exactly one `aleppo` resource in both canonical and packaged catalog, `repository`/immutable commit/`tf_path=tf/1.0`, native corpus `kind`, honest CC BY-SA data and provenance, `verification=community` until a load is actually demonstrated, a version-preserving lazy repository strategy, no standalone reverse feature-module claim, JSON schema compliance, and lossless generator projection.
2. GREEN: add a single canonical resource row, regenerate bundled Context-Fabric catalog and human resource guide through existing deterministic generators. Keep frozen `registry/v0.1.yaml` untouched.
3. Full Foundation + register-specific RED unit tests (and generated catalog/docs checks) on exact PR head. For trustworthy `verification=verified`, require **actual pinned upstream corpus load** and functional checks, not assertions against README alone. A separate live load check may remain necessary; do not mark it verified until it passes.
4. Skeptical independent review: source pin vs `tf_path`/version, generated catalog exact equivalence, source licences with ShareAlike attribution, proper lost-codex disclosure, parent BHSA reference identities, cache/network safety, no converter execution or synthetic/alleged reverse-module registration.
5. Merge only after exact-head relevant CI and a separate failure-oriented review. Avoid any claim that the 23,202 verses all survive in the medieval codex.

## Scope boundary

A future BHSA reverse feature-module integration must validate `tf/bhsa-mapping/2021/aleppo.tf` node identity against BHSA 2021 before registration, independent of this native-corpus ticket. No further architecture/release-plumbing tickets are prerequisites to simple corpus discovery here.
