# Agora agent instructions

Agora is a **thin plugin marketplace**. Before implementing or reviewing plugin-related work, read [`wiki/architecture/ref-plugin-boundary.md`](wiki/architecture/ref-plugin-boundary.md).

For any pull-request review, read [`CONTRIBUTING.md`](CONTRIBUTING.md) and use [`.agents/skills/agora-pr-review/SKILL.md`](.agents/skills/agora-pr-review/SKILL.md) as the default review entry point.

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
