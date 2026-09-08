# Research: automatic GitHub and Text-Fabric corpus version discovery (#107)

## Question

How can Agora discover new GitHub-hosted corpus versions without manual registry edits while preserving reproducibility, Text-Fabric dataset identity, feature-module compatibility, licensing/verification truthfulness, and collection semantics?

## Current Agora behavior

Agora already resolves more version information dynamically than the registry exposes:

- `ContextFabricResolver.corpus_versions()` asks `GitStore.dataset_roots()` for the selected upstream revision and derives the version from each TF dataset root.
- `default_corpus_version()` selects a default root when `upstream.tf_path` is absent.
- an explicit `upstream.tf_path` is a deliberate runtime pin: `_select_resource_root()` rejects a requested version that differs from that configured path.
- when `upstream.ref` is absent, Git metadata resolution follows current upstream state rather than an immutable reviewed release.

The registry therefore currently conflates two different concerns: runtime dataset-root selection and maintainer policy about which upstream publication Agora should advertise as supported/default. There is no resource-side analogue of registered-materializer `release_tracking`.

## Three version identities must remain distinct

A safe design needs three separately named identities:

1. **Upstream publication/source identity** — GitHub Release/tag plus the terminal immutable commit it resolves to, or an immutable branch-head commit observed during directory discovery.
2. **Text-Fabric dataset identity** — the concrete TF root and its dataset-version label, e.g. `tf/0.2.8`, `tf/2021`, or a collection member's `.../tf/1.0`.
3. **Agora support/default identity** — the source commit + TF root that Agora has validated and currently proposes/advertises as the supported default.

Equality between any two of these must never be assumed globally.

## Representative upstream evidence

### TLHdig-TF: release signal and branch TF roots diverge

Current Agora pins `upstream.tf_path: tf/0.1.0` while following the upstream default branch.

Primary GitHub evidence inspected 2026-09-09:

- Releases: `https://api.github.com/repos/alexsosn/TLHdig-TF/releases?per_page=20`
- `main/tf`: `https://api.github.com/repos/alexsosn/TLHdig-TF/contents/tf?ref=main`

The published stable release is tagged `tlhdig-0.3_tf-0.2.0` and explicitly describes TF dataset `0.2.0`. The current branch contains `tf/0.1.0`, `tf/0.2.0`, `tf/0.3.0`, and `tf/0.4.0`.

Consequences:

- TF-directory presence is **not** sufficient evidence that a dataset is a published/supported release.
- strict SemVer parsing of the whole release tag is insufficient for this repository; the TF version is a component of a project-specific release tag.
- a GitHub-release-tracked policy can safely ignore unreleased `0.3.0`/`0.4.0` branch directories until a release signal or explicit review says otherwise.

This is the motivating case for eliminating manual Agora bumps without turning `main/tf/*` into an automatic trust source.

### BHSA: release version and TF version are different namespaces

Primary evidence:

- Releases: `https://api.github.com/repos/ETCBC/bhsa/releases?per_page=20`
- TF roots: `https://api.github.com/repos/ETCBC/bhsa/contents/tf`

Latest inspected release tag is `v1.8.1`, while its release notes refer to TF data version `2021`. The repository currently contains TF roots `2016`, `2017`, `2021`, `3`, `4`, `4b`, and `c`.

Consequences:

- Git release SemVer cannot be copied into `tf_path`.
- TF root labels are not universally SemVer and may mix year-based, numeric, and opaque historical labels.
- Agora's existing natural root selection can remain runtime behavior, but release tracking must make promotion policy explicit rather than calling lexical/highest-directory order a publication guarantee.

BHSA also has many Agora feature modules explicitly compatible only with parent version `2021`, including `bhsa-phono`, `bhsa-parallels`, `bhsa-trees`, `bhsa-valence`, `bhsa-cantillation-trees`, and others in `registry/feature-modules.yaml`.

A parent default promotion therefore cannot silently leave those modules advertised as compatible with an unreviewed new parent version.

### CUC: modern Git release and TF root align

Primary evidence:

- Releases: `https://api.github.com/repos/DT-UCPH/cuc/releases?per_page=20`
- TF roots: `https://api.github.com/repos/DT-UCPH/cuc/contents/tf?ref=main`

Recent releases use tags such as `v0.2.8`, `v0.2.7`, `v0.2.6`; the repository contains corresponding `tf/0.2.x` roots as well as older `0.1*` versions.

CUC demonstrates the simple case where a stable GitHub release and same-version TF root can be validated together. The design should support it without assuming every corpus follows it.

### Pseudepigrapha-TF: publication version can map to a different TF label

Primary release evidence:

`https://api.github.com/repos/alexsosn/Pseudepigrapha-TF/releases?per_page=20`

Release `v0.1.0` is pinned to commit `315439284e765c1d7ea89ffdefdd10f403aa1293` but documents its generated TF dataset path/version as `tf/0.1`.

Pseudepigrapha-TF is currently a registered materializer rather than a canonical downloadable corpus resource, so it is not a migration target for #109. It is useful evidence that even a well-engineered release should not imply `release_version == tf_directory_name`.

### PTHU Greek Literature: collection source revision, member-level dataset versions

Primary evidence:

- Releases: `https://api.github.com/repos/pthu/greek_literature/releases?per_page=20` (none at inspection time)
- root tree: `https://api.github.com/repos/pthu/greek_literature/contents`
- Agora generated member index: `registry/collections/greek_literature.yaml`

This repository is a branch-published collection (`First1KGreek/`, `canonical-greekLit/`) rather than a single `tf/<version>` corpus. Agora's index pins a source revision and each member carries its own TF path, e.g. `canonical-greekLit/.../tf/1.0`.

Consequences:

- no collection-wide scalar TF version should be invented;
- collection tracking is primarily source-revision/index refresh plus member-level TF identity;
- #108 may propose a new immutable collection source revision/index, but member versions remain member metadata.

## Discovery is not acceptance

GitHub provides candidate signals, not Agora support decisions.

A safe update pipeline is:

```text
configured discovery signal
        ↓
resolve signal to immutable commit
        ↓
inspect TF roots/member structure at that commit
        ↓
derive candidate dataset identity by configured policy
        ↓
passive structural validation
        ↓
compatibility/licensing/verification carry-forward checks
        ↓
reviewable registry/default proposal
        ↓
normal PR CI + independent review
```

No candidate should become the canonical default merely because it is newest by release date, tag order, or directory order.

## Recommended tracking model

The registry needs one optional resource-owned tracking object with **orthogonal discovery, TF-selection, and promotion semantics**. Exact field names may change during implementation, but the model should be equivalent to:

```yaml
version_tracking:
  discovery:
    mode: github-releases | tf-directories | default-branch | disabled
    channel: stable             # github-releases only
    tag_pattern: '...'          # optional maintained pattern/captures
  dataset:
    mode: release-version-match | captured-version | latest-root | fixed | member-index
    root: tf                    # where applicable
  promotion:
    mode: proposal | discovery-only | pinned
```

Important semantics:

- `github-releases` means only non-draft/non-prerelease eligible Releases are publication candidates; the selected tag is fully dereferenced to a terminal commit SHA exactly as materializer release tracking does.
- `tf-directories` observes a moving branch only as a discovery source, first resolving that branch state to an immutable commit. It does not make every new directory a supported release automatically.
- `default-branch` is discovery/status only unless an explicit later policy says otherwise; a moving branch must never be persisted or described as an immutable release identity.
- `disabled` / `pinned` preserves deliberate fixed behavior.
- `member-index` avoids inventing a collection-wide dataset version.
- `release-version-match` is appropriate only when evidence shows release version and TF root label are the same convention (e.g. modern CUC).
- `captured-version` supports reviewed release-tag conventions such as TLHdig's `tlhdig-0.3_tf-0.2.0` without pretending the entire tag is SemVer.
- `latest-root` uses a separately specified root-order policy and remains reviewable; it is not an implicit global fallback.
- `fixed` preserves explicit TF path pins even if upstream has newer roots.

This structure is intentionally more explicit than copying materializer `release_tracking`: corpus publication identity and TF dataset identity are genuinely separate.

## Ordering and ambiguity

### GitHub releases

Reuse the materializer updater's strict, bounded rules where applicable:

- ignore drafts/prereleases for the stable channel;
- fully dereference lightweight/annotated tags to commit SHA;
- never persist `target_commitish` as immutable identity;
- reject ambiguous highest eligible candidates;
- reject same logical version resolving to conflicting commits rather than silently repinning;
- do not silently fall back to a lower candidate when the selected candidate fails validation.

A resource-specific maintained tag pattern may extract a TF version, but upstream-controlled tag text must still be validated against configured syntax and the actual TF root at the resolved commit.

### TF directory labels

Do not impose global SemVer. Existing repositories prove labels may be SemVer-like, years, integers, suffixes, or opaque historical conventions.

The v1 policy should use an explicit ordering mode per tracked resource, with at least:

- `semver` for strict SemVer directory labels;
- `natural` only when the resource audit establishes that Agora's current natural ordering matches upstream intent;
- `none`/discovery-only when no safe total ordering is known.

Unknown labels should not be guessed into SemVer.

## Feature modules

Parent default-version promotion must run compatibility analysis against `registry/feature-modules.yaml`.

For a candidate parent version:

- modules whose `compatibility.parent_versions` contains the candidate remain eligible;
- a module without candidate compatibility must not silently remain selectable as compatible;
- #108 should fail the automatic promotion proposal or surface an explicit blocking compatibility section requiring a human metadata update;
- it must never fabricate module compatibility from path similarity or matching repository tags.

For BHSA this is material: current modules are explicitly aligned to `2021`. A hypothetical new parent default must not silently carry those declarations forward.

## Licensing and verification carry-forward

A new source commit/TF dataset may change content/provenance even when the repository identity is stable.

Automation may preserve descriptive fields byte-for-byte while constructing a proposal, but it must not silently **strengthen** licensing or verification claims for the candidate.

Recommended v1 behavior:

- existing data-license classification may be carried as *repository-level policy* only where the evidence explicitly applies generically to repository dataset releases;
- component/member-specific and unresolved licensing stays equally or more conservative;
- `verification.status: verified` must not automatically imply the new version has passed the same load check until candidate CI does so;
- known issues are retained until independently shown inapplicable; automation does not auto-close them;
- candidate proposal/report names which evidence was reused versus which checks were rerun.

#109 performs the resource-by-resource audit needed to classify which existing evidence is genuinely release-generic.

## Collections

Collections should be tracked as source-revision/index publications, not forced into the corpus version model.

A collection update proposal may:

- resolve a new immutable repository commit;
- regenerate/validate its member index;
- report added/removed/changed member TF identities;
- retain member-level verification/licensing semantics.

It should not synthesize a collection `version` from the maximum member version.

## Reuse from materializer release automation

#108 should reuse, extract, or generalize existing supply-chain-sensitive primitives from `scripts/check_materializer_releases.py` rather than reimplement them independently:

- GitHub public REST transport and bounded pagination;
- release filtering;
- strict SemVer where configured;
- annotated/lightweight tag dereference with cycle/depth bounds;
- immutable commit validation;
- fail-closed candidate aggregation;
- deterministic byte-preserving YAML mutation;
- aggregate bot branch/PR idempotency patterns.

Do not send Agora's repository-scoped `GITHUB_TOKEN` to unrelated public upstream repositories. It remains for Agora-owned branch/PR writes.

Corpus-specific code should begin after immutable candidate resolution: dataset-root inspection, configured version extraction/ordering, compatibility and verification/licensing policy, and generated Context-Fabric catalog updates.

## Recommended implementation split

The already filed tickets are the right separation:

1. **#107 research/design** — this policy and explicit contracts.
2. **#108 generic updater** — schema, discovery, immutable resolution, passive TF validation, proposal workflow.
3. **#109 migration/audit** — classify every current corpus/collection and opt in only resources whose upstream conventions support the selected policy.

#108 must not mechanically turn all existing resources into tracked resources; absent tracking remains backward compatible.

## Security/reproducibility properties

The implementation must preserve:

- no upstream code execution during discovery;
- no arbitrary branch/tag name persisted as immutable identity;
- no automatic merge;
- no token leakage to public upstream reads;
- no silent semantic edits outside fields owned by the selected tracking policy;
- no silent promotion across feature-module incompatibility;
- no silent verification/licensing strengthening;
- no duplicate/no-op bot PRs;
- all accepted/default changes pass ordinary Agora CI and independent review.

## Conclusion

Agora can eliminate manual corpus-version maintenance, but the safe primitive is **automatic discovery plus reviewable promotion**, not "always use latest". Git publication identity, Text-Fabric dataset identity, and Agora-supported/default identity are separate. The registry should opt each resource into an explicit discovery + dataset-selection + promotion policy; #108 automates proposals and #109 audits/migrates the current catalog.
