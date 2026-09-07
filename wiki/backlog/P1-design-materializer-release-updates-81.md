# Design: registered-materializer release updater (#81)

## Gate

This is the implementation/TDD plan following `P1-research-materializer-release-updates-81.md`. Production code starts only after the RED tests below are committed and observed failing for the intended missing behavior.

## Acceptance contract

V1 adds an explicit optional release-tracking policy to registered materializers, a passive deterministic discovery/update CLI, and a scheduled workflow that maintains one review PR. It never executes candidate plugin code and never auto-merges.

Backward compatibility:

- entries without `release_tracking` remain manual and unchanged;
- `release_tracking.mode: disabled` is explicit manual mode;
- only `mode: github-releases`, `channel: stable` is automated in v1;
- canonical runtime `ref` remains a 40-hex immutable commit SHA.

## Registry schema

Extend each materializer plugin with optional:

```yaml
release_tracking:
  mode: github-releases
  channel: stable
  tag_prefix: v
```

or:

```yaml
release_tracking:
  mode: disabled
```

Schema design:

- `release_tracking` is optional;
- one `oneOf` branch accepts only `{mode: disabled}`;
- the GitHub branch requires `mode`, `channel`, and `tag_prefix`;
- `channel` is `stable` only in v1;
- `tag_prefix` is a short string without `/`, whitespace, braces, or control characters;
- `additionalProperties: false` at every level.

Opt Pseudepigrapha-TF into `github-releases/stable` with prefix `v` as the first exercised entry.

## Module boundaries

Add `scripts/check_materializer_releases.py` with no candidate execution path.

### Pure/control-plane types

Use small frozen dataclasses:

- `SemVer`: parsed precedence value plus canonical text;
- `ReleaseCandidate`: release/tag metadata before manifest validation;
- `ReleaseProposal`: plugin id, previous/new version/ref, tag, release URL, manifest SHA-256;
- `DiscoveryFailure`: plugin id plus actionable failure category/message where aggregate reporting is useful.

Use explicit exceptions for malformed upstream/API contracts instead of broad `Exception` swallowing.

### `GitHubApi`

A thin injectable transport owns HTTP only:

- constructor accepts token, API base URL, timeout and opener/callable for tests;
- `list_releases(repository)` paginates `GET /repos/{owner}/{repo}/releases?per_page=100&page=N`;
- `get_ref(repository, tag)` fetches `git/ref/tags/...` with URL quoting;
- `get_tag_object(repository, sha)` fetches annotated tag objects;
- `get_file(repository, path, ref=commit_sha)` fetches candidate manifest bytes from the immutable commit;
- all requests send GitHub JSON accept and explicit API version headers;
- HTTP/API/JSON failures become actionable discovery errors;
- no search API and no clone/build/install/import.

Tests inject an in-memory fake API/transport; deterministic unit tests never call GitHub.

### SemVer parser

Implement strict SemVer 2.0 parsing with a compiled regex and tuple comparison rules:

- numeric major/minor/patch, no leading zeros except `0`;
- optional prerelease identifiers with SemVer numeric-vs-string precedence;
- optional build metadata ignored for precedence;
- stable versions sort above prereleases of the same core version.

Release-tag parsing requires exact `tag_prefix + version`; no loose substring extraction.

### Candidate selection

`discover_plugin_update(plugin, api)`:

1. return no proposal for absent/disabled tracking;
2. validate current registry version as SemVer;
3. list all releases;
4. ignore `draft` or `prerelease` releases;
5. parse only exact configured-prefix SemVer tags;
6. select the highest stable SemVer strictly greater than current;
7. if two release records claim the same highest SemVer with different tags/ids, fail closed;
8. resolve candidate tag recursively to a commit;
9. validate the candidate manifest at that commit;
10. return immutable `ReleaseProposal`.

Invalid lower/irrelevant releases do not poison discovery. An invalid **selected highest** candidate fails closed rather than silently falling back to an older release: silently selecting a lower release can hide a broken or identity-changing current upstream release.

### Recursive tag resolution

`resolve_tag_commit(api, repository, tag)`:

- initial ref may target `commit` or `tag`;
- follow annotated tag objects until `commit`;
- track visited object SHAs;
- maximum depth 8;
- reject blob/tree/unknown types, cycles, malformed SHAs, or missing objects;
- return only a lowercase 40-hex commit SHA.

### Candidate manifest validation

Parse bytes as UTF-8 JSON and validate using the existing materializer plugin schema plus the same semantic validation used by `scripts.agora_materialize.load_manifest`. To avoid filesystem/import execution ambiguity, factor schema+semantic validation into a reusable function accepting a document, then keep `load_manifest(path)` as the filesystem wrapper.

Require:

- `manifest.plugin.id == registry.id`;
- optional `manifest.plugin.repository == registry.repository` when present;
- `manifest.plugin.version == proposal candidate canonical SemVer`;
- exact set equality of materializer ids;
- manifest SHA-256 recorded in proposal.

Do not compare converter implementation/dependencies semantically in discovery and do not import candidate modules.

### Aggregate discovery

`discover_updates(registry_doc, api)` evaluates every opted-in entry in registry order and returns proposals. Network/API/selected-candidate validation failure exits non-zero with plugin-specific diagnostics and returns **no applied registry mutation**. This keeps a partial network failure from producing a misleading incomplete aggregate PR.

Manual/disabled entries cause no network call.

## Minimal deterministic registry application

Do not `safe_dump` the entire canonical registry: that would turn a two-field release update into a formatting rewrite.

`apply_proposals_to_text(original_text, parsed_registry, proposals)` must:

- start from schema-validated canonical YAML;
- locate each target plugin block by the exact canonical `  - id: ...` line;
- within that block require exactly one current `ref:` line matching `previous_ref` and one `version:` line matching `previous_version`;
- replace only those scalar values, preserving line endings, comments, order, indentation and all unrelated bytes;
- reject duplicate/missing/mismatched target lines;
- reparse/revalidate the resulting registry;
- verify only the intended plugin version/ref values changed semantically;
- apply proposals in registry order, independent of API response ordering.

Repeated application of the same proposal set to already-updated canonical state produces no change rather than duplicate edits.

## CLI

Proposed interface:

```bash
python scripts/check_materializer_releases.py \
  --registry registry/materializers.yaml \
  --report /tmp/materializer-release-report.json \
  [--apply]
```

Behavior:

- default: discover/report only; never writes registry;
- `--apply`: write the deterministic validated patch atomically only when proposals exist;
- token from `GITHUB_TOKEN` environment, never CLI argv;
- report JSON is stable/sorted and contains proposal provenance, not secrets;
- output distinguishes `no-update`, `updated`, and `error` states;
- API/discovery failure exits non-zero and leaves the registry byte-for-byte unchanged.

## Scheduled workflow

Add `.github/workflows/materializer-release-updates.yml`:

Triggers:

- daily `schedule` at a non-round minute;
- `workflow_dispatch`.

Permissions:

```yaml
permissions:
  contents: write
  pull-requests: write
```

Job sequence:

1. checkout `main` with full enough history for a bot branch;
2. set up supported Python and install Agora dev validation dependencies;
3. run checker with `--apply` and report path;
4. if checker fails: fail workflow, push nothing, modify no PR;
5. if no diff: finish successfully; if a fixed automation PR exists but the candidate is now genuinely absent/obsolete, close it only from a successful no-proposal state, never from an API failure;
6. if diff exists: run canonical registry validation, generator freshness checks and the complete unit suite before any push;
7. recreate/update fixed branch `automation/materializer-releases` from the current default-branch SHA;
8. commit only the validated registry update;
9. push that automation-owned branch with lease protection;
10. create the single PR if absent or update its body if already open;
11. PR body comes from the deterministic JSON report and lists old/new version/ref, tag/release URL, manifest digest and passive-validation statement;
12. never merge or approve the PR automatically.

Because `GITHUB_TOKEN`-created PR workflow runs may require maintainer approval, the updater workflow itself supplies the pre-PR validation gate. Do not add a PAT secret in this ticket.

## TDD: RED commits required before implementation

Add `tests/test_materializer_release_updates.py` first. At minimum cover:

### Schema/policy

1. existing entries without release tracking remain valid/manual;
2. explicit disabled mode accepted;
3. GitHub stable policy accepted only with required prefix/channel;
4. unknown mode/channel/extra properties rejected;
5. Pseudepigrapha-TF is opted in only after implementation schema exists.

### SemVer/selection

6. already-current release -> no proposal;
7. newer stable release -> deterministic version/ref proposal;
8. draft ignored;
9. prerelease ignored;
10. multiple releases choose highest SemVer, not API order/creation order;
11. leading-zero/invalid tags ignored;
12. configured prefix is exact;
13. equal precedence ambiguity fails closed.

### Tag identity

14. lightweight tag resolves directly to commit;
15. annotated tag resolves tag object to commit;
16. nested annotated tags resolve recursively;
17. cycles/excessive depth/unsupported object type fail closed;
18. mutable tag name never appears in persisted registry `ref`;
19. malformed commit SHA fails closed.

### Candidate manifest

20. valid immutable candidate manifest passes;
21. missing/malformed manifest fails closed;
22. schema-invalid manifest fails closed;
23. plugin id drift fails closed;
24. repository drift fails closed;
25. version mismatch fails closed;
26. materializer id addition/removal fails closed;
27. selected highest invalid candidate does not silently downgrade to older candidate.

### Deterministic mutation / failure

28. registry patch changes only target `ref` and `version` bytes/semantics;
29. unrelated comments/order/entries remain byte-identical;
30. multiple proposals apply in canonical registry order;
31. repeated application is idempotent;
32. stale expected old values fail closed;
33. network/API failure leaves registry bytes unchanged;
34. one plugin failure prevents partial aggregate mutation.

### API/workflow contract

35. fake pagination proves all release pages are consumed;
36. HTTP client sends token/API-version/accept headers and bounded timeout;
37. workflow is schedule + manual dispatch only for discovery, declares minimal write permissions, runs validation before push, uses one fixed bot branch/PR and contains no auto-merge;
38. workflow uses repository `GITHUB_TOKEN`, not a committed/prompted PAT;
39. candidate installation/import commands are absent from discovery workflow/script.

The initial RED commit should fail because schema/module/workflow do not yet exist, not because fixtures are malformed.

## Implementation order after RED

1. reusable in-memory materializer-manifest validator;
2. registry release-tracking schema;
3. SemVer parser/value;
4. GitHub API transport and pagination;
5. release selection and tag dereference;
6. immutable candidate manifest validation;
7. aggregate proposal engine;
8. byte-preserving registry application and atomic write;
9. CLI/reporting;
10. opt in Pseudepigrapha-TF;
11. scheduled PR-maintenance workflow;
12. registry/architecture/operator documentation;
13. targeted unit suite, registry/generator checks, then full Foundation suite.

Each implementation step should turn a bounded subset of the committed RED tests green without weakening tests.

## Independent adversarial review gate

Before merge, freeze the exact PR head and review independently for:

- tag/ref mutability and full annotated/lightweight dereference;
- SemVer precedence and false-positive upgrades;
- candidate manifest identity spoofing/drift;
- path/ref URL encoding and API response trust;
- partial failure accidentally mutating registry;
- byte-preserving patch correctness and stale-base handling;
- idempotent bot branch/PR behavior under repeated schedules;
- permissions/token/secret exposure;
- candidate code execution sneaking into discovery;
- workflow recursion/CI evidence limitations;
- preservation of existing explicit install/build approval after the pin is merged.

No PR is finalized without this frozen-head review and green relevant CI.
