# Issue #304 — researcher guide matches native Pseudepigrapha 1.1

## Research — 2026-11-18

This branch is temporarily stacked on PR #303 to avoid editing the same generated Context-Fabric guide before #303's exact-head CI and merge. After #303 merges, retarget #304 to main and re-verify the exact diff and CI.

- Canonical `registry/resources.yaml` selects `pseudepigrapha` release `v1.1.0`, `tf-1.1.zip` (9,632,817 compressed bytes), archive sha256 `88f23ac9106c6ea8b35f89b19d760cf5d4ee544a3f8d8262d6ed7e2092e447e9`, source Git commit `39bd9fb895d1201e9cd9260170512fd8c399a3ac`, native data version `1.1` and `verification.status=community`.
- The user-facing generated plugin detail page and its **source of truth**, `scripts/generate_plugin_docs.py`, still identify native data **1.0**, release `v1.0.0` and `tf-1.0.zip` and link old versioned rights/schema documentation. The generator `--check` prevents editing the output alone.
- Verified upstream content **at immutable 1.1 source commit**: `DATA_LICENSE.md` and `docs/features/0_home.md` both exist, including `source_ref`, `witness`, `reading_of`, `translation_of` and `translation_unit_of`; README refers explicitly to the `v1.1.0/tf-1.1.zip` released data archive. Data rights remain OCP CC BY 4.0, with specific OCP/editor attribution, distinct from MIT converter.
- The Context-Fabric first-success guide is BHSA-focused and does not hard-code an older Pseudepigrapha version. The generated resource catalog displays corpus metadata and community verification, not obsolete 1.0 archive version. No unrelated page change is required.
- The `pseudepigrapha-tf` converter/materializer registration is a separate product with its own version. Do not change its pin or overstate the released native corpus's Agora E2E verification.

## TDD/implementation gates

1. RED: add a focused test reading the canonical registry, parsing only the Pseudepigrapha section of generated researcher page and asserting its exact current release tag/data version/archive name, current source and feature reference links, and no old 1.0 claim. Assert community evidence remains explicitly qualified, and generated-page freshness.
2. GREEN: correct the archived-corpus prose **in `scripts/generate_plugin_docs.py`** and regenerate its output `wiki/guides/plugins/context-fabric.md`, with no registry or engine changes.
3. Exact-head Foundation CI and independent adversarial review, check source URL targets and version claims. Recheck after any changes, merge only on passing final head.
4. Release-candidate host-level research journey and the separate published-corpus E2E remain independent gates.

## Non-goals

No release asset downloads in documentation tests, no converter upgrade, no migration of older research-history references, no new adapter, no claims of new source witnesses without a live content check.
