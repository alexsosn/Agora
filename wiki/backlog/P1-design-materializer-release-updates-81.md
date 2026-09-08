# Design: registered-materializer release updater (#81)

## Gate

This is the implementation/TDD plan following `P1-research-materializer-release-updates-81.md`. The original production implementation was preceded by committed RED tests. Adversarial review later found additional binding/workflow gaps; those were also taken through a separate tests-only RED gate before revision.

## Acceptance contract

V1 adds an explicit optional release-tracking policy to registered materializers, a passive deterministic discovery/update CLI, and a scheduled workflow that maintains one review PR. It never executes candidate plugin code and never auto-merges.

Backward compatibility:

- entries without `release_tracking` remain manual and unchanged;
- `release_tracking.mode: disabled` is explicit manual mode;
- only `mode: github-releases`, `channel: stable` is automated in v1;
- canonical runtime `ref` remains a full immutable commit SHA.

## Registry schema

Supported opt-in:

```yaml
release_tracking:
  mode: github-releases
  channel: stable
  tag_prefix: v
```

Explicit manual mode:

```yaml
release_tracking:
  mode: disabled
```

`release_tracking` is optional, each branch has `additionalProperties: false`, the GitHub mode requires channel and prefix, and v1 accepts only the stable channel. Pseudepigrapha-TF is the first opted-in materializer.

## Module boundaries

`scripts/check_materializer_releases.py` is control-plane code only. It owns:

- strict SemVer parsing and ordering;
- injectable GitHub API reads;
- release selection;
- recursive tag dereference;
- passive immutable-commit manifest validation;
- aggregate proposal construction;
- byte-preserving registry application;
- deterministic report/PR-body rendering.

It has no candidate build/install/import/execute path.

## GitHub API contract

The client:

- paginates `GET /repos/{owner}/{repo}/releases`;
- URL-quotes repository/tag/path/ref values appropriately;
- resolves `git/ref/tags/...` and annotated tag objects;
- fetches the manifest through Contents API at the resolved commit SHA;
- sends explicit GitHub JSON accept/API-version headers and a bounded timeout;
- accepts injected transport for deterministic tests;
- turns HTTP/API/JSON failures into actionable release-discovery errors.

## SemVer and candidate selection

Use strict SemVer 2.0 precedence:

- no leading-zero numeric core components;
- correct numeric/string prerelease ordering;
- build metadata ignored for precedence;
- stable above prerelease for the same core version.

For each opted-in plugin:

1. validate current registry version as SemVer;
2. list releases;
3. ignore draft/prerelease release records;
4. parse only exact `tag_prefix + SemVer` tags;
5. ignore candidates not strictly newer than current;
6. choose the unique highest stable SemVer;
7. fail closed on equal-highest ambiguity;
8. fully dereference its tag to a commit;
9. validate the manifest from that exact commit;
10. return an immutable `ReleaseProposal`.

An invalid selected highest candidate fails closed; the checker does not silently downgrade to an older release.

## Recursive tag resolution

The initial tag ref may target a commit or an annotated tag. Follow tag objects until a commit, tracking visited SHAs and enforcing a depth bound of 8. Reject cycles, malformed SHAs, unsupported object types, or missing objects. Return only a lowercase 40-hex commit SHA.

## Candidate manifest binding

Parse candidate bytes as UTF-8 JSON and run the existing materializer schema plus semantic validation. Then enforce a proposal binding **identical in strength to install-time `_validate_binding`**:

- `manifest.plugin.id == registry.id`;
- `manifest.plugin.name == registry.name`;
- `manifest.plugin.repository` is present and equals `registry.repository`;
- `manifest.plugin.version == candidate SemVer text`;
- `[item.id for manifest.materializers] == registry.materializers` as an exact ordered list;
- record the manifest SHA-256 in the proposal.

This deliberately rejects a candidate that would later fail solely because the release checker accepted weaker identity semantics than installation.

Descriptions, acquisition details, dependencies, and converter implementation are not semantically approved by discovery and candidate modules are never imported.

## Aggregate fail-closed behavior

`discover_updates(registry, api)` evaluates opted-in entries in registry order. A network/API/binding failure for any selected candidate prevents the aggregate proposal from being applied. Manual/disabled entries make no network call.

## Minimal deterministic registry application

Do not reserialize the entire YAML document. The patcher:

- starts from a schema-valid canonical registry;
- finds exact plugin blocks;
- requires one expected old `ref` and one expected old `version` line;
- changes only those scalar bytes;
- preserves unrelated comments/order/indentation/line endings;
- rejects stale/duplicate/missing targets;
- reparses/revalidates after mutation;
- verifies semantic changes are limited to intended fields;
- is idempotent when the candidate is already applied.

## CLI

```bash
python scripts/check_materializer_releases.py \
  --registry registry/materializers.yaml \
  --report /tmp/materializer-release-report.json \
  [--apply]
```

Default mode discovers/reports only. `--apply` writes the validated registry patch atomically. `GITHUB_TOKEN` comes from the environment, not argv. Errors exit non-zero and leave canonical remote state untouched.

## Scheduled workflow

`.github/workflows/materializer-release-updates.yml` runs daily and supports manual dispatch.

Required orchestration:

1. explicitly check out `ref: main` with sufficient history; do not inherit a user-selected `workflow_dispatch` ref;
2. set up Python/dependencies;
3. run passive discovery with `--apply` against the working tree;
4. on discovery failure, push nothing and mutate no PR;
5. on no diff, succeed and optionally close an obsolete fixed automation PR only after successful discovery;
6. on diff, run registry validation, generator freshness checks, and the full unit suite before any push;
7. recreate/update fixed branch `automation/materializer-releases` from that canonical-main checkout;
8. commit only the registry update;
9. push with lease protection;
10. create or refresh one PR against `main` with deterministic provenance body;
11. never approve or merge automatically.

Permissions stay `contents: write` and `pull-requests: write`. V1 uses the repository `GITHUB_TOKEN`; if repository policy disallows Actions-created PRs, the workflow should fail visibly instead of falling back to a PAT or bypassing review.

## TDD gates

The initial tests-only RED contract covers:

- release-tracking schema and backward compatibility;
- strict SemVer and deterministic highest-stable selection;
- draft/prerelease/prefix filtering;
- lightweight, annotated, nested, cyclic, malformed and unsupported tag targets;
- immutable SHA persistence;
- candidate manifest missing/malformed/schema/version/id/repository/materializer drift;
- selected-highest invalid candidate fail-closed behavior;
- API pagination/headers/timeouts;
- aggregate failure without partial mutation;
- byte-preserving and stale-safe registry mutation;
- idempotent repeated application;
- workflow scheduling, permissions, fixed branch/PR, validation-before-push, no candidate execution and no auto-merge.

Adversarial review added a second tests-only RED tranche for discrepancies between proposal and install-time binding:

- plugin name drift must fail;
- missing candidate `plugin.repository` must fail;
- reordered materializer IDs must fail even when the set is unchanged;
- workflow checkout must explicitly use canonical `main` for manual dispatch as well as schedule.

The review RED head produced 486 tests with exactly five failures (the three binding cases plus two independent main-checkout contract tests), while unrelated lock/cache lanes remained green. Production revision follows only after that evidence.

## Validation sequence

After GREEN:

1. targeted release-updater/review regression tests;
2. registry/schema validation;
3. generated marketplace/catalog/release-status freshness checks;
4. full Foundation unit suite;
5. cross-platform materializer lock/cache lanes;
6. registered materializer install smoke;
7. real Linux/macOS materialization sandbox E2E;
8. Pseudepigrapha-TF reference materialization;
9. exact-head logically independent adversarial review.

## Independent adversarial review gate

Freeze the exact final head and challenge:

- SemVer false positives and equal precedence;
- mutable tag/ref behavior and full dereference;
- candidate schema/binding spoofing, including parity with installation;
- API path/ref quoting and response-shape trust;
- candidate code execution accidentally entering discovery;
- partial failures mutating registry or bot branch;
- byte preservation and stale-base handling;
- workflow-dispatch base correctness;
- fixed branch force-with-lease/idempotency;
- token permissions/secret exposure and PR-creation operational dependency;
- no auto-merge and preservation of explicit install/build approval.

No PR is finalized without green exact-head CI and this frozen-head review.
