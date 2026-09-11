# Agora agent instructions

Agora is a **thin plugin marketplace**. Before implementing or reviewing plugin-related work, read [`wiki/architecture/ref-plugin-boundary.md`](wiki/architecture/ref-plugin-boundary.md).

For any pull-request review, read [`CONTRIBUTING.md`](CONTRIBUTING.md) and use [`.agents/skills/agora-pr-review/SKILL.md`](.agents/skills/agora-pr-review/SKILL.md) as the default review entry point.

## Agora 1.0 release mode

Until [#148](https://github.com/alexsosn/Agora/issues/148) is complete, the 1.0 release tracker controls work selection.

1. Pick an actionable 1.0 item before post-release architecture, automation, optimization, or catalog expansion.
2. If a release item is blocked, choose another actionable release item. A blocked ticket is not permission to start speculative platform work.
3. A newly discovered issue belongs on the 1.0 path only when it can cause incorrect or misleading results, failed installation/launch, data loss or resource exhaustion, severe first-time-user confusion, or an invalid documented support claim.
4. Keep other findings as post-1.0 work. Do not reopen issues closed as `not planned` during release grooming unless new evidence makes them release-critical.
5. Prefer the smallest change that makes the user-visible release contract true. Generalized infrastructure needs evidence that the release case actually requires it.
6. Do not expand the four-plugin 1.0 scope merely because an additional provider or corpus is available.

During release mode, prioritize installation, first successful use, truthful capability claims, bounded disk/time behavior, clear failure/cancellation behavior, documentation, and regression prevention.

### Risk-proportional development gates

TDD and logically independent adversarial review remain the default quality controls. Their depth must match the risk of the change.

- **High-risk runtime/security/data-integrity changes:** research actual current behavior and relevant sources; write a plan when the change spans multiple components or has meaningful design choices; preserve a focused RED regression before production changes; run the directly relevant integration/end-to-end gates; independently review the frozen final head.
- **Ordinary bug fixes:** reproduce the user-visible failure, add a focused regression, implement the smallest fix, run affected tests plus Foundation as appropriate, and independently review the final head. A standalone research document or dedicated plan document is optional unless uncertainty warrants one.
- **Registry/version/generated-metadata changes:** validate the canonical source, regenerate owned projections, run schema/generation plus directly relevant install/launch smoke where the changed pin affects execution, and independently review the final head. Do not manufacture architecture work to justify a metadata update.
- **Documentation-only changes:** verify commands, links, and claims against current behavior. Run lightweight documentation/generated-artifact checks where applicable. Do not require runtime RED/GREEN history or unrelated cross-platform live smokes.

A review finding becomes immediate follow-up work only when it threatens the release contract, safety, correctness, or the specific PR's stated contract. Otherwise record it for post-1.0 rather than recursively expanding the current PR or spawning release-blocking work.

## Non-negotiable boundary

Agora owns discovery, description, installation, launch, transport/configuration adaptation, resource selection, compatibility metadata, and marketplace UX. Third-party plugins own their domain behavior, bugs, missing features, and substantive scholarly capabilities.

Use this test:

> If the same bug or missing capability exists when the third-party plugin is run directly without Agora, the substantive fix normally belongs upstream.

Do not add monkey-patches, private-internal shims, replacement algorithms, new query modes, or local semantic fixes to third-party plugins merely because Agora exposes them.

When an upstream limitation matters to Agora users, link/report it upstream, direct users to the authoritative upstream documentation, constrain a version when required for integration compatibility, and adjust Agora's integration verification metadata rather than silently repairing it locally. Do not copy mutable upstream suitability or data-quality assessments into Agora.

## Repository-maintenance skills

Use these skills for repository development and review:

- [`.agents/skills/agora-pr-review/SKILL.md`](.agents/skills/agora-pr-review/SKILL.md) — reviewing any PR against `CONTRIBUTING.md`, agent instructions, applicable architecture policy, tests, generated artifacts, and documentation requirements;
- [`.agents/skills/agora-plugin-integration/SKILL.md`](.agents/skills/agora-plugin-integration/SKILL.md) — deciding ownership and implementing thin integrations;
- [`.agents/skills/agora-plugin-review/SKILL.md`](.agents/skills/agora-plugin-review/SKILL.md) — specialized review of plugin-related issues/PRs for scope creep and misplaced upstream fixes; apply it as a subreview of `agora-pr-review` when relevant.

## Skill placement

Substantive skills for a third-party plugin should live upstream whenever practical. Agora-packaged plugin-specific skills may only facilitate capabilities the plugin already exposes. Generic marketplace skills and repository-maintenance skills are appropriate Agora-owned skills.

## Tests

Test Agora-owned contracts: registry, generated manifests, installation/launch, transport, tool discovery, Agora-owned resource resolution, and small smoke checks. Do not turn Agora CI into the semantic regression suite for third-party algorithms.
