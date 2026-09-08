# Registered materializer release tracking

Agora materializer runtime entries remain pinned to immutable 40-character Git commit SHAs. Optional `release_tracking` metadata only controls passive discovery of review candidates; it never changes runtime resolution to a branch, tag, or `latest` alias.

## Registry policy

A materializer without `release_tracking` is maintained manually. The explicit equivalent is:

```yaml
release_tracking:
  mode: disabled
```

A public GitHub materializer may opt into the v1 stable-release policy:

```yaml
release_tracking:
  mode: github-releases
  channel: stable
  tag_prefix: v
```

Only published, non-draft, non-prerelease GitHub Releases whose tag is the configured prefix plus a strict SemVer version are eligible. Agora lists releases and selects the highest eligible SemVer greater than the currently registered version; it does not rely on GitHub's mutable notion of a single "latest" release and does not silently fall back to plain repository tags.

## Immutable identity and passive validation

A release tag is untrusted mutable metadata. For an eligible release Agora resolves the tag through GitHub's Git ref/tag-object APIs until it reaches a full commit SHA. Lightweight and annotated tags are supported; cycles, malformed SHAs, excessive nesting, or non-commit terminal objects fail closed. Only the resolved commit SHA can be proposed in `registry/materializers.yaml`.

The configured `agora.materializer.json` is then fetched from that exact immutable commit and treated as data. Before a proposal is produced, Agora requires the candidate manifest to satisfy the current materializer schema/semantic checks and to preserve the same binding that installation enforces:

- the registered plugin `id`;
- the registered plugin `name`;
- the registered repository identity (it must be present and exactly equal);
- the release version selected from the tag;
- the exact registered materializer-id sequence, including order.

The proposal gate is intentionally no weaker than install-time registry ↔ manifest validation: automation must not create a review candidate that Agora would later refuse to fetch/install solely because of identity drift.

Discovery does not clone, build, install, import, or execute candidate plugin code. A missing/malformed manifest, identity/version drift, unsupported contract, tag ambiguity, or API/network failure leaves the canonical registry unchanged.

## Proposal workflow

`.github/workflows/materializer-release-updates.yml` runs daily and can also be dispatched manually. The workflow explicitly checks out canonical `main` even for `workflow_dispatch`, so the fixed bot branch is always rebuilt from current main rather than from an arbitrary selected dispatch ref. It uses the repository `GITHUB_TOKEN`, applies proposals only to a working copy, runs Agora's registry/generator/unit validation before any push, and maintains one fixed review branch/PR: `automation/materializer-releases`.

The registry patcher changes only the selected entries' `version` and `ref` scalar bytes and verifies the resulting YAML semantically. Repeated successful runs are idempotent. A failure produces no partial aggregate proposal; a successful no-update run may close an obsolete automation PR.

Creating or updating the automation PR requires the repository to permit GitHub Actions to create pull requests with `GITHUB_TOKEN`. If that repository setting is disabled, the workflow must fail visibly at the PR operation rather than bypassing review or using a hidden long-lived credential.

Automation PRs are review artifacts, not trust decisions. The workflow never merges them. After a reviewed pin is eventually merged, the existing `explicit-code-execution` approval remains required before third-party Python packaging/build code can execute.

## Manual check

Discovery/report only:

```bash
GITHUB_TOKEN=... python scripts/check_materializer_releases.py \
  --report /tmp/materializer-release-report.json
```

Apply validated proposals to the local registry working tree:

```bash
GITHUB_TOKEN=... python scripts/check_materializer_releases.py \
  --apply \
  --report /tmp/materializer-release-report.json \
  --pr-body /tmp/materializer-release-pr.md
```

Run `python scripts/validate_registry.py` and the normal generated-artifact/unit gates before committing any resulting registry change.
