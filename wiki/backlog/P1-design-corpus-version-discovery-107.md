# Plan: automatic corpus version discovery and reviewable promotion (#107)

## Goal

Remove routine manual corpus-version bumps for GitHub-hosted resources without turning upstream mutable state into an unreviewed Agora default.

The implementation must distinguish:

- upstream publication/source identity;
- Text-Fabric dataset root/version identity;
- Agora-supported/default identity.

Research: `P1-research-corpus-version-discovery-107.md`.

## Scope boundary

This design owns Agora registry tracking policy and the contracts consumed by #108/#109. It does not modify corpus contents, invent upstream versions, alter Text-Fabric semantics, or automatically merge updates.

## Registry direction

Add an optional resource tracking object whose semantics separate three axes. Exact schema names may be normalized during #108, but the information model is normative:

```yaml
version_tracking:
  discovery:
    mode: github-releases | tf-directories | default-branch | disabled
    channel: stable             # when applicable
    tag_pattern: '...'          # optional maintained extraction rule
  dataset:
    mode: release-version-match | captured-version | latest-root | fixed | member-index
    root: tf                    # when applicable
    ordering: semver | natural | none
  promotion:
    mode: proposal | discovery-only | pinned
```

Rules:

1. absent `version_tracking` preserves current behavior exactly;
2. `promotion: pinned` never changes an explicit `tf_path`/source pin automatically;
3. `promotion: proposal` can only create/update a review PR;
4. `discovery-only` reports candidates but never rewrites the canonical default;
5. collections use `member-index` rather than a fabricated scalar dataset version;
6. a GitHub release/tag always resolves to a terminal immutable commit before corpus inspection;
7. a moving branch used for TF-directory discovery is first resolved to an immutable observed commit;
8. dataset selection is evaluated against TF roots at that immutable commit, not current branch state after discovery.

## Candidate record

The updater should produce an internal/report record equivalent to:

```text
resource_id
current_source_revision | null
current_tf_path | null
discovery_mode
candidate_signal          # release/tag/branch observation
candidate_source_revision # immutable commit
candidate_tf_path | null
candidate_tf_version | null
promotion_state           # proposed/discovery-only/blocked/no-change
blocking_reasons[]
validation_evidence[]
```

The immutable commit and TF root are separate fields even when their version strings happen to match.

## #108 TDD sequence

### RED 1 — schema and backward compatibility

Commit tests before implementation requiring:

- current resources without tracking remain valid and byte/runtime compatible;
- controlled discovery/dataset/promotion modes validate;
- mode-specific required/forbidden fields fail closed;
- collections cannot use corpus-only scalar TF promotion modes;
- deliberate `pinned` tracking cannot be combined with automatic promotion;
- malformed tag patterns/order modes are rejected;
- feature modules do not independently redefine their parent corpus default policy.

### GREEN 1

Add only optional schema/validator/runtime metadata projection if public description requires it. No GitHub calls yet.

### RED 2 — immutable upstream discovery

Freeze:

- stable GitHub Releases only; draft/prerelease filtering;
- strict SemVer comparison only where the configured release policy requests it;
- resource-maintained tag extraction for nonstandard tags such as TLHdig;
- lightweight/annotated tag dereference to terminal full commit SHA with cycle/depth bounds;
- same logical version/different commit ambiguity fails closed;
- selected invalid highest release does not silently fall back to a lower release;
- public upstream REST reads do not receive Agora's repository-scoped token;
- branch/directory discovery records the immutable branch-head commit before inspecting TF roots.

### GREEN 2

Extract/reuse the relevant GitHub/tag/SemVer primitives from the materializer updater where practical. Keep corpus-specific logic separate after immutable source resolution.

### RED 3 — TF dataset identity

Use synthetic repository/API fixtures plus representative policy fixtures to require:

- CUC-style release version → matching `tf/<version>`;
- TLHdig-style configured tag capture → matching TF root while ignoring newer unreleased branch roots;
- BHSA-style release version distinct from latest/selected TF root;
- non-SemVer TF labels are not forced through SemVer;
- configured `semver`, `natural`, and `none` ordering behave deterministically;
- missing/malformed TF root rejects or blocks promotion;
- an explicit fixed path is not rewritten by generic discovery;
- no upstream code is executed.

### GREEN 3

Implement passive dataset-root inspection and configured version extraction/selection against the immutable candidate commit.

### RED 4 — compatibility/trust carry-forward

Freeze candidate proposal behavior when:

- parent version lacks one or more feature-module `compatibility.parent_versions` declarations;
- verification status is `verified` but the candidate has not yet run its load smoke;
- known issues exist;
- licence evidence is unresolved/component/member-specific;
- repository-level licence evidence is explicitly reusable across releases;
- candidate is a collection with member-level versions.

The automatic updater must not strengthen compatibility, verification, or licensing claims.

### GREEN 4

Add a proposal classifier/report with explicit blockers/caveats. Do not guess module compatibility or licence applicability.

### RED 5 — deterministic registry PR automation

Freeze:

- only policy-owned canonical fields change;
- unrelated YAML bytes/semantics are preserved;
- generated Context-Fabric catalog is refreshed/lossless when canonical metadata changes;
- no-op/idempotent runs do not create duplicate PRs;
- one deterministic aggregate bot branch/PR is refreshed from canonical `main`;
- manual workflow dispatch checks out `main` explicitly;
- partial selected-candidate failure is visible and does not silently create a partial-success proposal;
- bot automation never auto-merges.

### GREEN 5

Add scheduled + manual workflow and deterministic proposal branch/PR mechanics, reusing materializer release-update patterns where possible.

## #109 migration/audit gate

After #108 policy/schema exists, #109 must inventory every current corpus and collection before opt-in. It must record primary GitHub evidence and one explicit disposition per resource:

- GitHub-release proposal;
- TF-directory proposal;
- default-branch discovery-only;
- deliberate pinned/disabled;
- collection/member-specific.

No mechanical migration.

Representative expected directions from #107 research, pending full #109 audit:

- **TLHdig-TF:** strong candidate for GitHub-release tracking with configured TF-version extraction; current unreleased `tf/0.3.0`/`0.4.0` prove branch directory discovery alone must not promote it.
- **CUC:** strong candidate for stable GitHub-release + same-version TF-root matching.
- **BHSA:** release-tracked source may be useful, but release version and TF root are separate; parent `2021` module compatibility must block unsafe default promotion.
- **Greek Literature:** collection/member-index tracking, no collection scalar TF version.
- **Pseudepigrapha-TF:** evidence/reference pattern only unless/until it is registered as a canonical corpus; currently it is a materializer.

## Feature-module compatibility gate

Before a proposed parent default change, compute the set of registered modules for that parent.

If any currently advertised module does not include the candidate parent version:

- do not silently add compatibility;
- do not silently remove the module;
- mark the proposal blocked or explicitly requiring a reviewed companion compatibility change.

The PR may contain that companion change only if separately evidenced/reviewed; the updater itself must not infer it.

## Licensing/verification gate

The proposal report must distinguish metadata copied unchanged from evidence actively rerun for the candidate.

At minimum:

- `verified` is not considered candidate-verified until the candidate's configured smoke/evidence passes;
- known issues remain unless explicitly reviewed away;
- unresolved/component/member-specific licensing cannot become stronger through an update;
- repository-wide licence evidence may remain descriptive only when its source clearly applies to versions generically;
- #109 records the per-resource carry-forward disposition.

## Collections

Collection update behavior is source-revision/index oriented:

1. resolve candidate repository commit;
2. regenerate/validate member index;
3. diff member identities/TF paths;
4. preserve member-level version/licence/verification semantics;
5. never derive a collection version from `max(member.version)`.

## Validation gates before final #108 merge

- focused release/TF-selection/proposal tests;
- canonical registry validation;
- generated catalog freshness/losslessness;
- current Context-Fabric resolver/version tests;
- representative passive GitHub fixtures for TLHdig/CUC/BHSA policy shapes;
- collection-index tests;
- feature-module compatibility tests;
- Foundation full suite;
- any workflow-specific dry/no-update smoke possible without executing upstream code;
- frozen exact-head logically independent adversarial review.

## Independent review focus

Challenge the implementation for:

1. conflating release version with TF root version;
2. using mutable branch/tag text as immutable identity;
3. treating directory presence as publication/acceptance;
4. global SemVer assumptions over historical TF labels;
5. retag/same-version commit substitution;
6. silent fallback after selected-candidate failure;
7. feature-module compatibility drift;
8. verification/licensing strengthening without evidence;
9. collection scalar-version invention;
10. upstream credential leakage;
11. YAML churn outside owned fields;
12. duplicate/no-op PR races;
13. any automatic merge or bypass of ordinary Agora review.

Every material finding becomes a focused RED regression before its minimal fix.

## Definition of done

#107 is complete when this evidence/design is exact-head green, independently reviewed, and merged. That only authorizes #108 implementation; it does not itself eliminate manual updates. The user-facing maintenance problem is complete when #108 is merged and #109 has opted the eligible existing resources into reviewed policies.
