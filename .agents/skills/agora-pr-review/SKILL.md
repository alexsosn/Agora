---
name: agora-pr-review
description: "Use this skill when reviewing any Agora pull request for compliance with repository contribution rules, agent instructions, architecture policy, tests, generated artifacts, documentation, and other applicable maintainer requirements."
license: MIT
metadata:
  scope: repository-maintenance
  project: Agora
---

# Agora pull request review

Use this skill as the default entry point for reviewing an Agora pull request.

The review must evaluate the actual diff against the repository's current contribution rules. Do not assume that passing CI, following the PR template, or looking reasonable is sufficient evidence of compliance.

## 1. Load the governing rules first

Before judging the implementation, read the policy files from the PR's target branch and any policy changes made by the PR itself:

- `CONTRIBUTING.md`;
- `AGENTS.md`;
- `.github/pull_request_template.md` when present;
- architecture references or other documents explicitly linked by those files;
- directory-local instructions when the changed area defines them.

If the PR modifies a governing document, distinguish between the rules that apply to the contribution as submitted and the policy change the PR proposes. Flag self-serving policy changes that merely make an otherwise non-compliant implementation appear compliant.

Do not invent contribution requirements. A reviewer preference, common convention, or desirable improvement is not a compliance finding unless it follows from repository policy, an explicit issue/acceptance criterion, or a correctness requirement.

## 2. Establish the PR's claimed scope

Read the PR description, linked issue when available, and changed files. State the intended behavior in neutral terms.

Then identify which contribution requirements actually apply to this PR. Examples include:

- architectural ownership and repository boundaries;
- canonical-vs-generated file rules;
- tests and validation commands;
- documentation updates;
- plugin metadata and integration constraints;
- skill placement and ownership;
- backward-compatibility or version declarations when repository policy requires them.

Do not mechanically apply plugin-specific requirements to unrelated changes.

## 3. Review the diff against each applicable rule

Inspect the implementation rather than trusting checkboxes or author claims.

For every applicable requirement, determine whether the diff:

- complies;
- violates the rule;
- lacks enough evidence to verify compliance; or
- is not applicable.

A compliance finding must cite both:

1. the repository rule or acceptance criterion being enforced; and
2. concrete evidence in the PR diff, tests, generated artifacts, or behavior.

Prefer precise file/line references and reproducible validation steps.

## 4. Run specialized review when needed

If the PR touches third-party plugins, plugin adapters, plugin-specific tests, plugin-facilitation skills, provider wiring, or plugin runtime metadata, also apply `.agents/skills/agora-plugin-review/SKILL.md`.

Treat `agora-plugin-review` as a specialized subreview. Its architectural ownership findings are part of the final PR review rather than a separate optional exercise.

For implementation work involving plugin integration, use `.agents/skills/agora-plugin-integration/SKILL.md` as the corresponding authoring guidance when useful for understanding the intended contract.

## 5. Inspect tests and validation evidence

Check whether the PR supplies the validation required by repository policy and by the behavior it changes.

Verify, where applicable:

- tests exercise the Agora-owned contract rather than merely executing code paths;
- a bug fix has a regression test when the repository's testing expectations require one;
- generated artifacts are regenerated from their canonical source rather than hand-edited;
- documented validation commands have been run or are reproducible;
- tests do not encode behavior owned by an upstream third-party project when the plugin boundary forbids that.

A green CI run does not waive a missing required test, stale generated output, architectural violation, or documentation obligation.

## 6. Inspect documentation and contributor-facing effects

When behavior, supported versions, plugin capabilities, installation, configuration, limitations, or public repository workflow changes, check whether the repository's documentation rules require corresponding updates.

Do not demand unrelated documentation cleanup as a condition of approval.

## 7. Review output

Report findings before general commentary. Order findings by severity and practical impact.

Each blocking finding should contain:

- **Finding** — the concrete defect or policy violation;
- **Rule** — the exact contribution/architecture requirement it conflicts with;
- **Evidence** — the relevant changed file, behavior, or missing artifact;
- **Required change** — the smallest correction needed for compliance.

Separate non-blocking suggestions from compliance findings.

End with one verdict:

- **compliant** — no material violation of applicable repository rules found;
- **changes required** — one or more material violations are demonstrated;
- **unclear** — compliance depends on evidence that is unavailable or cannot be verified from the PR.

Do not use `unclear` merely because exhaustive certainty is impossible. State exactly what evidence is missing.

## Reviewer discipline

Review independently of the author's framing and of previous review comments. Existing comments may supply leads, but verify them against the current diff because later commits may have fixed or invalidated them.

Do not lower the standard because substantial work has already been invested. Do not raise the standard by introducing requirements that are absent from Agora's governing documents.
