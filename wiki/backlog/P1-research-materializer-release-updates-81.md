# Research: passive registered-materializer release discovery (#81)

## Status

Research gate complete. The implementation must preserve the conclusions below and the stronger install-time binding and authentication contracts identified during adversarial review.

## Problem boundary

Agora owns discovery, registration metadata, immutable source identity, integration validation, and reviewable update proposals. Third-party materializers own packaging and converter behavior. Release discovery therefore remains passive: it may read GitHub metadata and candidate files, but it must not build, install, import, or execute candidate plugin code.

The canonical materializer registry already requires runtime `ref` values to be 40-character commit SHAs. Release tracking only proposes a new immutable SHA; it never changes runtime resolution to a branch, tag, release alias, or `latest`.

## Source research

Primary GitHub documentation consulted:

- Releases REST API: <https://docs.github.com/en/rest/releases/releases>
- Git references REST API: <https://docs.github.com/en/rest/git/refs>
- Git tag-object REST API: <https://docs.github.com/en/rest/git/tags>
- REST API rate limits: <https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api>
- REST authentication: <https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api>
- `GITHUB_TOKEN` behavior: <https://docs.github.com/en/actions/concepts/security/github_token>
- Workflow triggering: <https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow>

Repository inspection covered `registry/materializers.yaml`, its schema, the materializer manifest schema, `scripts/agora_install_materializer.py`, validation/generation workflows, and existing GitHub automation patterns.

## Discovery source and version policy

Use GitHub Releases, not tags-only discovery. Releases expose draft/prerelease state and upstream publication intent; raw tags do not. Do not use `/releases/latest` as the selector because Agora needs deterministic version ordering against the registered version rather than GitHub's mutable/latest-release presentation semantics.

V1 policy:

1. list all GitHub Releases, with pagination;
2. reject drafts and prereleases;
3. require configured `tag_prefix + strict SemVer`;
4. reject SemVer prerelease versions on the stable channel;
5. consider only versions strictly greater than the registered version;
6. choose the single highest SemVer candidate;
7. if multiple release records have equal highest precedence, fail closed rather than guessing.

Repositories without GitHub Releases do not silently fall back to tags. They stay manual/disabled in v1; a future explicit `github-tags` policy would be a separate design.

The SemVer parser should be dependency-light and directly tested: numeric major/minor/patch without leading zeros, correct prerelease precedence, build metadata ignored for precedence, and stable versions above prereleases of the same core version.

## Tag dereferencing and immutable identity

A release tag is mutable discovery metadata. Persisting it would violate Agora's immutable-pin contract.

Resolve the release tag through the Git refs/tag-object APIs:

1. fetch `refs/tags/<name>`;
2. if it points to a commit, use that commit;
3. if it points to an annotated tag object, fetch that object and continue;
4. reject other object types;
5. reject cycles and excessive nesting with a fixed bound;
6. persist only the terminal lowercase 40-hex commit SHA.

`target_commitish` is not an immutable trust anchor. A later run may observe a moved tag and recompute its proposed SHA, but the canonical registry remains on its previously reviewed commit until a human-reviewed PR merges.

## Candidate manifest validation

Fetch the configured `agora.materializer.json` from the **resolved immutable candidate commit**, decode it as UTF-8 JSON, and run Agora's existing manifest schema plus semantic validation without importing candidate modules.

The proposal gate must be **at least as strict as `scripts/agora_install_materializer.py::_validate_binding`**. A release is proposal-compatible only when:

- `plugin.id` exactly equals the registered id;
- `plugin.name` exactly equals the registered name;
- `plugin.repository` is present and exactly equals the registered `owner/repo`;
- `plugin.version` exactly equals the normalized candidate SemVer text;
- materializer IDs exactly equal the registered ordered list, not merely the same set.

This stronger rule was confirmed by adversarial review: allowing missing repository metadata, name drift, or reordered IDs would let the automation propose a release that Agora's installer would later reject. Generic manifest schema permissiveness does not weaken this registry-bound proposal contract.

Changes to descriptions, acquisition details, dependencies, or converter implementation may still appear in a proposal when the binding contract remains valid; those substantive changes are review material, not something the passive checker executes or semantically blesses.

Missing/malformed manifests, schema errors, binding drift, version mismatch, tag ambiguity, unsupported contracts, or API/network failures fail closed and produce no canonical registry mutation.

## Registry metadata

Release policy is explicit and opt-in:

```yaml
release_tracking:
  mode: github-releases
  channel: stable
  tag_prefix: v
```

Explicit opt-out:

```yaml
release_tracking:
  mode: disabled
```

Absence remains equivalent to manual/disabled for backward compatibility. V1 does not add speculative providers or execution policy.

## Scheduling and workflow base

Use a daily scheduled GitHub Actions workflow plus `workflow_dispatch`. Polling is generic and requires no upstream webhook/action installation; repository dispatch/webhooks may be future latency optimizations but are not dependencies.

The workflow must explicitly check out canonical `main`, including on `workflow_dispatch`. Manual dispatch can select another ref, so relying on the event ref would make the fixed automation branch non-deterministically based on arbitrary branch state.

The checker remains a normal deterministic CLI; scheduling is orchestration only.

## API authentication and limits

V1 automated discovery only targets public GitHub repositories. GitHub documents the workflow `GITHUB_TOKEN` as a GitHub App installation token whose permissions are limited to the repository containing the workflow. It must therefore **not** be forwarded as generic authentication for release/tag/manifest reads from unrelated upstream repositories.

The scheduled discovery step performs those public upstream REST reads unauthenticated. GitHub currently documents a primary unauthenticated REST limit of 60 requests/hour per source IP. The present opted-in registry is small enough for a daily serialized poll under that budget, and the checker minimizes requests by fully paginating releases but resolving tags/manifests only for the selected newer candidate.

If the registry grows beyond that public-read budget, use an explicitly provisioned read-only GitHub App installation token whose installation actually covers the upstream repositories (or another deliberately scoped credential). Do not repurpose Agora's repository-scoped write token. The CLI may still accept an operator-supplied `GITHUB_TOKEN` environment value when that credential is intentionally authorized for the targets.

All requests use explicit GitHub JSON/API-version headers, bounded timeouts, and complete pagination. Avoid search endpoints and redundant per-release calls. HTTP, JSON, authentication, connectivity, or rate-limit failures must be actionable and must not mutate canonical state.

## Deterministic proposal and idempotency

Discovery returns structured proposals containing plugin id, old/new version and ref, release/tag URL identity, resolved commit, and candidate-manifest SHA-256. Mutation is a separate step.

The registry mutator changes only the target entries' `version` and `ref` scalar values, preserving comments, ordering, indentation, line endings, and unrelated bytes; it reparses and revalidates the result and rejects stale expected old values.

Use one fixed aggregate branch/PR, `automation/materializer-releases`. Each successful run begins from current `main`, computes the complete valid proposal set, and creates or refreshes that one review artifact. Repeated runs therefore converge instead of creating duplicate PRs. A selected-candidate or network failure prevents a partial aggregate proposal.

## Workflow-created PRs and trust

The scheduled job runs Agora-owned registry/generator/unit validation before any push. It uses only `contents: write` and `pull-requests: write`, never auto-merges, and does not require a PAT in v1.

The repository `GITHUB_TOKEN` is reserved for operations against Agora itself: pushing the automation branch and creating/editing/closing its PR. GitHub repositories may disable PR creation by Actions; the workflow should fail visibly if that token is not allowed to create/update a PR and must not bypass review with another hidden credential. PR-triggered workflow behavior for bot-created changes is secondary evidence because the proposal workflow already validates before push.

The release checker is a proposal engine, not a runtime updater or trust authority:

- release/tag metadata is untrusted input;
- mutable tag names are never runtime refs;
- the manifest is untrusted data and never executed;
- only a resolved commit SHA may enter a proposal;
- failures leave canonical registry unchanged;
- bot PRs are never auto-merged;
- explicit code-execution approval remains required after a reviewed pin reaches the canonical registry.

## Alternatives rejected for v1

- `/releases/latest` only: not deterministic highest-stable-SemVer selection.
- tags without Releases: no reliable upstream publication/stability signal under this policy.
- storing tags/branches/latest: violates immutable runtime identity.
- cloning/installing/importing candidates: expands trust unnecessarily.
- mandatory upstream webhooks: poor generic compatibility.
- auto-merge: collapses proposal and trust review.
- forwarding Agora's `GITHUB_TOKEN` to upstream discovery: repository-scoped installation credential with the wrong authorization boundary.
- PAT by default: unnecessary long-lived credential burden.

## Research conclusion

Proceed with explicit optional `release_tracking`, a passive injectable GitHub API client, strict SemVer release selection, recursive tag-to-commit dereferencing, proposal validation no weaker than install-time binding, public unauthenticated upstream polling in v1, deterministic byte-preserving registry mutation, and one scheduled/manual review-PR workflow always based on canonical `main`.
