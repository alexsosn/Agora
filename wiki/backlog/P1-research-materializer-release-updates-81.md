# Research: passive registered-materializer release discovery (#81)

## Status

Research gate complete. No production implementation is authorized by this document; the next gate is an explicit design/TDD plan.

## Problem boundary

Agora owns discovery, registration metadata, immutable source identity, integration validation, and reviewable update proposals. Third-party materializers own their packaging and converter behavior. Release discovery therefore must remain passive: it may read GitHub metadata and candidate files, but it must not build, install, import, or execute candidate plugin code.

The current registry already requires every runtime `ref` to be a 40-character lowercase commit SHA. That invariant should remain unchanged. Release tracking is metadata for proposing a new immutable SHA, never a runtime `latest`/tag indirection.

## Source research

Primary GitHub documentation consulted:

- Releases REST API: <https://docs.github.com/en/rest/releases/releases>
- Git references REST API: <https://docs.github.com/en/rest/git/refs>
- Git tag-object REST API: <https://docs.github.com/en/rest/git/tags>
- REST API rate limits: <https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api>
- `GITHUB_TOKEN` behavior: <https://docs.github.com/en/actions/concepts/security/github_token>
- Workflow triggering: <https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow>

Repository inspection also covered the canonical materializer registry/schema, `scripts/agora_install_materializer.py`, existing validation/generation workflows, and the absence of an existing generic PR-creation automation in Agora.

## Releases API versus tags-only discovery

GitHub's Releases API exposes the policy signals Agora needs directly: draft and prerelease state, tag name, publication metadata, and release identity. Tags alone do not distinguish a project-declared public stable release from an arbitrary maintenance/checkpoint tag.

The `/releases/latest` endpoint is not sufficient for Agora's `latest-stable` policy. GitHub documents it as the latest published full release according to release metadata/creation semantics, and release authors can influence `make_latest`. Agora needs deterministic version ordering against the currently registered version. The checker should therefore list releases, discard drafts/prereleases, parse eligible tags as strict SemVer, and select the highest SemVer greater than the registered version.

Repositories without GitHub Releases should **not** silently fall back to tags under a `github-releases` policy. That would change the meaning of opt-in metadata and could promote a tag the upstream project never declared as a release. Such repositories remain manually pinned/disabled in v1; a separate explicit `github-tags` policy could be researched later.

## Stable release and SemVer policy

For v1, use strict SemVer 2.0 precedence for `MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]`, with an explicit per-plugin tag prefix (for example `v`). The stable channel accepts only versions without a prerelease component. GitHub `draft: true` and `prerelease: true` releases are excluded even if their tag text looks stable.

Selection rules:

1. parse the registry's current `version` as strict SemVer;
2. enumerate all published release records available to the workflow;
3. exclude draft and prerelease records;
4. require the tag to match the configured prefix plus a strict SemVer version;
5. ignore versions less than or equal to the registered version;
6. choose the single highest SemVer candidate; ties with different release/tag identities are ambiguous and fail closed.

Do not depend on third-party `packaging`/SemVer libraries merely for this small control-plane parser. A bounded internal SemVer value/parser keeps release discovery dependency-light and makes precedence rules directly testable. It must reject leading-zero numeric identifiers and implement SemVer prerelease precedence correctly even though the default stable policy filters prereleases; the parser should not contain a subtly different ordering model.

## Tag dereferencing and mutability

A Git tag name is a mutable reference. Persisting the tag name would violate Agora's existing immutable-pin contract.

GitHub's Git refs API returns the object currently referenced by `refs/tags/<name>`. For a lightweight tag the object can already be a commit. For an annotated tag it is a tag object; GitHub's tag-object endpoint applies only to annotated tag objects. Correct dereferencing is therefore:

1. fetch the exact tag ref;
2. if the target type is `commit`, use that commit SHA;
3. if the target type is `tag`, fetch that tag object and repeat on its target;
4. reject any other object type;
5. reject cycles and excessive nesting with a small fixed depth bound;
6. persist only the final 40-hex commit SHA.

The release record's `target_commitish` is useful context but is not the immutable pin. The Git ref/tag-object chain is authoritative for resolving the candidate at discovery time.

A later run may observe that a mutable tag moved. The updater must recompute the commit and proposal from current upstream state, but the canonical registry remains unchanged until the review PR is merged. Existing installed/runtime identity therefore remains pinned to the previously reviewed commit.

## Candidate manifest validation

The checker should fetch the configured manifest path from the **resolved immutable candidate commit**, not from the tag or default branch. It can reuse Agora's existing materializer-manifest schema/semantic loader logic on downloaded bytes or an equivalent pure validator.

Before producing a proposal, require all of the following:

- manifest exists and parses as JSON;
- manifest satisfies Agora's current materializer plugin schema and semantic checks;
- `plugin.id` exactly equals the registry entry id;
- `plugin.repository`, when declared by the manifest, exactly equals the registered `owner/repo`;
- manifest plugin version exactly equals the normalized candidate SemVer text;
- the set of declared materializer ids exactly equals the registry entry's `materializers` set;
- no unsupported schema/contract change is needed for validation.

A candidate that changes description, acquisition source, dependencies, or converter behavior may still be proposed if the identity contract above remains valid; those changes are for human/CI review after the passive proposal. Discovery must not execute the candidate to decide that.

Missing/malformed manifests, version mismatch, identity drift, unsupported schema, ambiguous tag resolution, or API/network failures produce an actionable failure result and **no registry mutation**.

## Registry metadata shape

Release policy must be explicit rather than inferred from repository host/name. Recommended optional field:

```yaml
release_tracking:
  mode: github-releases
  channel: stable
  tag_prefix: v
```

Explicit opt-out is also valid:

```yaml
release_tracking:
  mode: disabled
```

For backward compatibility, absence of `release_tracking` is equivalent to disabled/manual. Schema `additionalProperties: false` means this field requires an intentional schema extension; that is desirable because it prevents silent policy typos.

V1 needs only `github-releases` + stable and disabled/manual semantics. Do not add speculative providers or execution policy to this field.

## Scheduled polling versus webhooks

A scheduled workflow is the generic default. It requires no cooperation or installed workflow in third-party repositories and works for every registered public GitHub materializer.

`repository_dispatch` or upstream webhooks can reduce latency but require upstream configuration/credentials and undermine the marketplace goal of thin generic integration. They may be optional future accelerators, not the v1 dependency.

A daily schedule is sufficient for release discovery. Add `workflow_dispatch` for manual verification/debugging. The checker itself should be a normal deterministic CLI so scheduling is orchestration, not business logic.

## API authentication and rate limits

GitHub documents a primary REST limit of 1,000 requests/hour/repository for the Actions `GITHUB_TOKEN` outside higher Enterprise limits. A daily check over the current small registry is comfortably below this if the checker paginates releases efficiently and only fetches tag/manifest data for the selected newer candidate.

The client should:

- authenticate with `GITHUB_TOKEN` when available;
- send an explicit API version and JSON accept header;
- use bounded request timeouts;
- surface HTTP status and rate-limit exhaustion actionably without mutating state;
- paginate list-releases responses instead of assuming one page;
- avoid search endpoints and redundant per-release calls.

No third-party repository token is needed for public release/source metadata.

## Deterministic proposal and idempotency

Separate discovery from mutation. A pure-ish discovery layer should return a structured proposal such as:

```json
{
  "plugin_id": "pseudepigrapha-tf",
  "previous_version": "0.1.0",
  "previous_ref": "...",
  "candidate_version": "0.2.0",
  "candidate_tag": "v0.2.0",
  "candidate_ref": "<40-hex commit>",
  "release_url": "...",
  "manifest_sha256": "..."
}
```

Applying proposals should update only `version` and `ref` for the matching registry entry. YAML output must be deterministic and preserve unrelated registry entries/fields semantically; tests should catch accidental broad rewrites.

One automation branch name, e.g. `automation/materializer-releases`, and one open PR title are sufficient. Repeated runs should update that branch/PR to the current deterministic proposal set instead of opening duplicates. If there is no valid newer proposal, the checker exits successfully with no canonical registry mutation and no new PR.

Multiple materializer updates can share one PR if each passes independent passive validation; this reduces bot churn and makes the fixed branch naturally idempotent. The PR body should list per-plugin old/new versions, tag/release URL, resolved commit, and manifest digest.

## Workflow-created PRs and CI

GitHub documents special anti-recursion behavior for `GITHUB_TOKEN`. A PR created/updated by a workflow with that token can create `pull_request` workflow runs in an approval-required state; ordinary pushes made with that token do not recursively start workflows. A GitHub App installation token or PAT can trigger normal downstream workflow behavior without that approval requirement.

V1 should not require a new long-lived PAT merely to automate discovery. The scheduled job can run the required Agora-owned registry/generator/unit validation **before** creating/updating the PR, then create the reviewable PR with the repository `GITHUB_TOKEN`. The PR remains deliberately non-auto-mergeable and maintainers can approve any additional PR-triggered runs. If fully unattended downstream CI becomes a requirement, use a least-privilege GitHub App token as a separate hardening/operations change.

Required workflow permissions should be minimized to `contents: write` and `pull-requests: write`; discovery itself needs read access only.

## Trust model

The release checker is a proposal engine, not an updater of trusted runtime state.

- upstream release/tag metadata is untrusted input;
- tag names are mutable and never persisted as runtime refs;
- the candidate manifest is untrusted data and never imported/executed;
- only a resolved commit SHA can enter the registry proposal;
- current canonical registry remains unchanged on discovery/validation failure;
- bot PRs are never auto-merged;
- package/build execution still requires the existing explicit-code-execution approval after a reviewed pin reaches canonical registry.

This keeps #81 inside Agora's marketplace boundary and does not grant the bot authority to bless third-party code.

## Alternatives rejected for v1

- **Use `/releases/latest` only:** does not implement highest-stable-SemVer policy reliably.
- **Track tags without Releases:** cannot distinguish project-declared releases from arbitrary tags under the proposed policy.
- **Store tag names in `ref`:** violates the immutable source identity contract.
- **Clone/install candidate repositories:** unnecessary execution/trust expansion; passive API reads are sufficient.
- **Require upstream dispatch/webhooks:** poor generic compatibility and extra upstream coupling.
- **Auto-merge bot PRs:** collapses discovery/proposal and trust approval into one step.
- **Use a PAT by default:** avoidable secret/lifecycle burden for a review-first workflow.

## Research conclusion

Proceed with an explicit optional `release_tracking` registry contract, a standalone passive GitHub release checker with injected/mockable API transport, strict SemVer selection, recursive tag-to-commit dereferencing, immutable-commit manifest validation, deterministic proposal/application output, and a scheduled review-PR workflow. Keep PR creation/orchestration thin around the tested checker and preserve manual immutable pins for all non-opted-in entries.
