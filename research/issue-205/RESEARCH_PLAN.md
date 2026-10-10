# Issue #205: selective, immutable Git acquisition for large TT corpora

## Research (2026-10-10)

- Actual baseline failure: CopticScriptorium/corpora pinned `3ac067f1709a0012daf39ea8da2fac79980176a5`, full depth-one fetch (120s) failed with `fatal: early EOF` in PR #198 CI. GitHub reports ~2.7 GiB repository size.
- The converter accepts `corpus/dataset_TT/` and `corpus/dataset_TT.zip`, not the full parallel ANNIS, PAULA, CoNLL-U, TEI, etc. Pinned Git tree API sampling: sahidica.nt 61,280,149 B across 262 blobs, 5,749,949 B TT ZIP; thomas-gospel 12,307,173 B across 28 blobs, 1,474,064 B TT directory; AP 27,673,453 B across 405 blobs, 3,422,340 B TT files.
- Verified on a real local Git fixture: `git fetch --filter=blob:none --depth 1 origin <revision>`, before checkout `git sparse-checkout set --no-cone '/*/*_TT/**' '/*/*_TT.zip'`, then detach checkout selected both TT directory files and TT ZIP but not adjacent formats. A local filesystem remote warns it ignores object filtering; GitHub remote support and full upstream timings still require live CI verification.

## Complete pinned upstream tree census (independent Git object evidence)

Inspected the root Git tree and **all 79 child directory trees** at
`3ac067f1709a0012daf39ea8da2fac79980176a5` using GitHub Git Trees API
(`?recursive=1` for each child). None of the 79 results was truncated.
A TT payload blob is any file at `<corpus>/<dataset>_TT.zip` or beneath
`<corpus>/<dataset>_TT/`; the recursive child-tree paths were matched with
`^([^/]+)_TT\\.zip# Issue #205: selective, immutable Git acquisition for large TT corpora

## Research (2026-10-10)

- Actual baseline failure: CopticScriptorium/corpora pinned `3ac067f1709a0012daf39ea8da2fac79980176a5`, full depth-one fetch (120s) failed with `fatal: early EOF` in PR #198 CI. GitHub reports ~2.7 GiB repository size.
- The converter accepts `corpus/dataset_TT/` and `corpus/dataset_TT.zip`, not the full parallel ANNIS, PAULA, CoNLL-U, TEI, etc. Pinned Git tree API sampling: sahidica.nt 61,280,149 B across 262 blobs, 5,749,949 B TT ZIP; thomas-gospel 12,307,173 B across 28 blobs, 1,474,064 B TT directory; AP 27,673,453 B across 405 blobs, 3,422,340 B TT files.
- Verified on a real local Git fixture: `git fetch --filter=blob:none --depth 1 origin <revision>`, before checkout `git sparse-checkout set --no-cone '/*/*_TT/**' '/*/*_TT.zip'`, then detach checkout selected both TT directory files and TT ZIP but not adjacent formats. A local filesystem remote warns it ignores object filtering; GitHub remote support and full upstream timings still require live CI verification.

 or `^([^/]+)_TT/.*# Issue #205: selective, immutable Git acquisition for large TT corpora

## Research (2026-10-10)

- Actual baseline failure: CopticScriptorium/corpora pinned `3ac067f1709a0012daf39ea8da2fac79980176a5`, full depth-one fetch (120s) failed with `fatal: early EOF` in PR #198 CI. GitHub reports ~2.7 GiB repository size.
- The converter accepts `corpus/dataset_TT/` and `corpus/dataset_TT.zip`, not the full parallel ANNIS, PAULA, CoNLL-U, TEI, etc. Pinned Git tree API sampling: sahidica.nt 61,280,149 B across 262 blobs, 5,749,949 B TT ZIP; thomas-gospel 12,307,173 B across 28 blobs, 1,474,064 B TT directory; AP 27,673,453 B across 405 blobs, 3,422,340 B TT files.
- Verified on a real local Git fixture: `git fetch --filter=blob:none --depth 1 origin <revision>`, before checkout `git sparse-checkout set --no-cone '/*/*_TT/**' '/*/*_TT.zip'`, then detach checkout selected both TT directory files and TT ZIP but not adjacent formats. A local filesystem remote warns it ignores object filtering; GitHub remote support and full upstream timings still require live CI verification.

 before adding the top-level
corpus component.

- 79 top-level directories, **78 containing TT payloads**; `bible/`
  has no TT files.
- **565 TT payload Git blobs, total 220,289,125 bytes (210.08 MiB)**.
- All tracked file blobs in the pinned root tree: **1,894,430,888 bytes**
  including root `README.md` (3,511 B) and `meta.json` (2,461,846 B).
- TT files are **11.63% of tracked raw file bytes** at that exact commit.
  These are uncompressed Git *tree blob-size* totals, **not measured network
  transfer size, Git pack size, unpacked disk footprint or elapsed time**.
- Every tracked path containing `_TT` matched one of the two TT payload
  shapes; no unexpected nested TT-package location was found in any of the
  79 complete recursive child-tree listings.
- The root `meta.json` is intentionally *not* selected by the proposed
  sparse patterns. Current `copticscriptorium_tf.parser.parse_source_tree`
  only reads `*_TT` directories and `*_TT.zip` packages, so this does
  not omit an input used by the current converter. Future supplemental
  metadata / CoNLL-U features must revisit selection explicitly.

Census data is derived from the immutable upstream Git **tree objects**,
independently of running the converter and does not assert a successful
source fetch. The remaining full-source E2E gate must verify the selected
TT checkout against that expected 565-blob inventory before conversion.

## Design and scope

1. Introduce optional `sparse_patterns` on a Git acquisition declaration. **Never** derive sparse selection from `required_globs`, which only proves nonemptiness, not corpus completeness.
2. Require a 40-character lowercase hex commit pin for sparse mode; reject absolute filesystem escapes, negations, unexpected Git pattern syntax, `..`, and ambiguous patterns at validation time. Legacy Git strategies without `sparse_patterns` use unchanged full checkout.
3. For sparse mode: init repository, register HTTPS remote, set Git promisor/partial-clone configuration, `fetch --filter=blob:none --depth 1` at exactly the pinned SHA, configure non-cone sparse patterns *before* checkout, detached checkout, verify `HEAD == requested SHA`, validate input contract, and record the selected patterns in provenance. Acquisition remains outside the network-denied conversion sandbox, with existing transactional cleanup.
4. Tests first (RED): schema bad and good inputs; real local Git fixture ensuring wanted TT files and exclusion of adjacent formats; asserted Git fetch/select ordering, immutable-revision mismatch refusal, failure cleanup, unchanged full-source behavior. Run cross-platform foundation suites.
5. Follow-on dependent delivery: CopticScriptorium-TF adds the opt-in manifest paths and its own tests; Agora subsequently updates immutable plugin registry pin and runs **actual pinned remote Git download + representative/full real source conversion**. Until that verification succeeds, #205 and Coptic #17 **remain open**.

## Adversarial questions before merge

- Does Git non-cone `/*/*_TT/**` include *every* nested TT file or omit a TT variant?
- What if server does not advertise partial-clone filters? Does the code accidentally fetch all blobs while calling itself bounded?
- Are requested and resolved commits compared exactly, including force-push scenarios?
- Can attacker-controlled patterns turn Git sparse-checkout into config/options injection, or escape the source root?
- Are `--source` local overrides unchanged and errors informative?
- Can a test go green despite completely removing `--filter` or moving sparse selection after checkout?

## Gates

- [x] Research on repository/source layouts and local Git semantics
- [ ] RED contract in exact-head CI (workflow scheduled; no completion observed yet)
- [ ] Implementation + passing exact-head CI (implementation committed; final-run verification pending)
- [ ] Separate adversarial review of exact PR head
- [ ] Merge only if independent review yields no blockers
- [ ] Full Coptic remote source verification + upstream issue closure (separate dependent gate)
