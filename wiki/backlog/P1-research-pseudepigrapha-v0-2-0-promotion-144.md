# Research: Pseudepigrapha-TF v0.2.0 promotion (#144)

## Scope and ownership

Agora owns the stable materializer registry identity used for discovery, installation, and materialization. Pseudepigrapha-TF owns converter and corpus semantics. This task therefore changes only Agora registry identity and Agora-side compatibility verification; it must not patch upstream behavior.

Normative repository boundaries are `AGENTS.md`, `CONTRIBUTING.md`, `wiki/architecture/ref-plugin-boundary.md`, and `.agents/skills/agora-plugin-integration/SKILL.md`.

## Current Agora state

At research base `9973902324f44eaeea6bd79c91cbd45a88b4519d`, `registry/materializers.yaml` records:

- plugin id `pseudepigrapha-tf`;
- repository `alexsosn/Pseudepigrapha-TF`;
- version `0.1.0`;
- immutable ref `315439284e765c1d7ea89ffdefdd10f403aa1293`;
- release tracking `github-releases` / `stable` / prefix `v`;
- ordered materializer IDs `[ocp-text-fabric]`.

## Published upstream candidate

The public GitHub release `v0.2.0` is published, non-draft, and non-prerelease. Its annotated tag object `8d855e0b0f7d83be1e510865f380f3589f37eb8a` dereferences to immutable commit `317e960e05ca7f36f35a11fcf567285312951095`.

The release publishes the canonical TF asset set and identifies package/materializer version `0.2.0`, TF data version `0.2`, and OCP source commit `c939dcbacad78c5d18d2c4282cad23c47e19ac07`. At the release commit, `agora.materializer.json` preserves Agora-facing plugin id, name, repository, and ordered materializer IDs while changing the version to `0.2.0`.

A read-only post-publication upstream verifier previously succeeded against the public assets. Agora still needs its own registry/install/materialization evidence; upstream semantic verification does not substitute for Agora compatibility checks.

## Existing Agora mechanism

`scripts/check_materializer_releases.py` already implements stable GitHub-release discovery, SemVer selection, recursive annotated-tag dereference, exact-commit manifest loading, schema validation, and fail-closed plugin id/name/version/repository/materializer-order binding. No new release resolver is justified for this promotion.

`registry/materializers.yaml` is not an input to marketplace generation, so Claude/Codex generated marketplace files should remain unchanged. Registry validation and generation freshness should remain green after the pin update.

## Conclusion

The candidate is eligible for a narrow Agora-owned promotion if a tests-first regression demonstrates the current stable pin is stale, the canonical registry changes only the expected version/ref identity, and exact-head install/materialization verification succeeds before merge.
