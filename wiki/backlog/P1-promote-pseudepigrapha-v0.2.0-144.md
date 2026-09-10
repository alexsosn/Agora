# #144 — Promote Pseudepigrapha-TF v0.2.0

## Research checkpoint

### Agora-owned scope

Agora owns the stable materializer registry identity used for discovery, installation, and materialization. The upstream converter owns corpus semantics. This task therefore changes only Agora compatibility/registry metadata and integration verification; it must not patch or duplicate Pseudepigrapha-TF behavior.

Normative references:

- `AGENTS.md`;
- `CONTRIBUTING.md`;
- `wiki/architecture/ref-plugin-boundary.md`;
- `.agents/skills/agora-plugin-integration/SKILL.md`.

### Current canonical registry

At research base `9973902324f44eaeea6bd79c91cbd45a88b4519d`, `registry/materializers.yaml` records Pseudepigrapha-TF as:

- repository `alexsosn/Pseudepigrapha-TF`;
- version `0.1.0`;
- immutable ref `315439284e765c1d7ea89ffdefdd10f403aa1293`;
- stable GitHub release tracking with prefix `v`;
- ordered materializer IDs `[ocp-text-fabric]`.

### Published upstream candidate

The public stable release is `v0.2.0`.

- annotated tag object: `8d855e0b0f7d83be1e510865f380f3589f37eb8a`;
- dereferenced commit: `317e960e05ca7f36f35a11fcf567285312951095`;
- package/materializer version: `0.2.0`;
- Text-Fabric data version: `0.2`;
- OCP source commit: `c939dcbacad78c5d18d2c4282cad23c47e19ac07`.

Pseudepigrapha-TF read-only post-publication verifier run `34484002904`, job `102893575717`, succeeded: exact public assets passed distribution validation, stock Text-Fabric acquired `v0.2.0` from a fresh cache, then reloaded through `checkout="local"` after socket connection entry points were replaced with fail-fast functions. Post-verification tag dereference and public release records remained unchanged.

At exact release commit `317e960e...`, `agora.materializer.json` preserves the Agora-facing identity expected by the existing registry:

- plugin id `pseudepigrapha-tf`;
- name `Pseudepigrapha-TF`;
- repository `alexsosn/Pseudepigrapha-TF`;
- version `0.2.0`;
- ordered materializer IDs exactly `[ocp-text-fabric]`.

### Existing release-discovery mechanism

`scripts/check_materializer_releases.py` already implements the required promotion semantics. For `github-releases` / `stable` it enumerates public releases, selects the highest applicable SemVer, recursively dereferences annotated tags to a full commit SHA, fetches the candidate manifest at that exact commit, validates schema/semantic safety, and rejects plugin id/name/version/repository or ordered materializer-id drift.

Relevant regression coverage already exists in:

- `tests/test_materializer_release_updates.py`;
- `tests/test_materializer_release_review_regressions.py`.

No new resolver implementation is justified.

### Generated-artifact boundary

`scripts/generate_marketplaces.py` reads `registry/marketplace.yaml`, `registry/plugins.yaml`, and `registry/v0.1.yaml`. It does **not** consume `registry/materializers.yaml`. Therefore this promotion should not change Claude/Codex marketplace/plugin generated files. The correct generation gate is that `python scripts/generate_marketplaces.py --check` remains green and generated artifacts remain unchanged.

## Implementation plan

1. Add a focused RED regression for the canonical Pseudepigrapha-TF stable registry identity: version `0.2.0`, exact commit `317e960...`, unchanged repository/tracking/materializer IDs.
2. Demonstrate RED while the canonical registry still contains `0.1.0` / `315439284...`.
3. Update only the canonical `registry/materializers.yaml` version/ref fields unless another canonical drift is proven.
4. Do not hand-edit generated marketplace artifacts; they are outside this registry input path and should remain fresh/no-op.
5. Run registry validation, marketplace-generation check, materializer release-update tests, and the canonical test suite.
6. Obtain read-only live evidence that the real release-discovery path resolves `v0.2.0` through the annotated tag to exact commit `317e960...` and accepts the exact upstream manifest.
7. Exercise an Agora-owned install/materialization smoke against the promoted registry identity when supported by existing CI/workflow infrastructure; do not assert upstream scholarly semantics.
8. Read `.agents/skills/agora-pr-review/SKILL.md` and `.agents/skills/agora-plugin-review/SKILL.md`, then perform a fresh logically independent exact-head review.
9. Merge only if exact-head tests and review are green; verify permanent `main` state and report evidence to Pseudepigrapha-TF #104.

## TDD expectations

The regression must fail on the old stable pin for the intended reason and become green solely from canonical registry promotion. It must additionally preserve:

- exact 40-character commit pinning rather than tag/branch strings;
- `alexsosn/Pseudepigrapha-TF` repository identity;
- `github-releases` / `stable` / `v` tracking policy;
- ordered materializer IDs `[ocp-text-fabric]`.

Generic release-discovery behavior is already tested and should not be duplicated unless live integration reveals a new Agora-owned defect.
