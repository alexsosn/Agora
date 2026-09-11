# Repository governance and protected-main policy

This document defines the repository-level merge policy expected for Agora `main`. It is a normative maintenance rule; GitHub branch protection or an equivalent ruleset is the enforcement mechanism.

## Normal development path

Changes to `main` should land through pull requests. Normal development must not rely on direct pushes or administrator bypasses to skip release-critical validation.

Before a pull request is merged into `main`:

1. the pull request head must be the revision that was reviewed;
2. the GitHub Actions check named **`Repository foundation, registry, and manifests`** from the **Foundation** workflow must complete successfully for that head;
3. a failing or pending required Foundation check blocks merge;
4. any head change after final review invalidates the review/evidence and requires the relevant checks and independent review to be repeated.

The repository may run additional live or platform-specific checks for changes whose contract requires them. Those checks remain required by the relevant development/release process even when they are not configured as a universal branch-protection context.

## Required GitHub protection

`main` must be covered by branch protection or an equivalent repository ruleset that:

- requires the Foundation check **`Repository foundation, registry, and manifests`** before merge;
- prevents normal direct pushes that bypass the pull-request/required-check path;
- prevents merging while the required check is failing or pending;
- does not provide a routine bypass path for ordinary development.

An administrator bypass, if the repository configuration retains one for emergency recovery, is for exceptional repository recovery only—not for feature, metadata, documentation, or release work. Any emergency bypass should be documented in the relevant issue/PR and followed immediately by Foundation verification of the landed `main` revision.

## Release gate

Agora 1.0 and later releases must not be declared ready while the repository API reports `main` as unprotected and no equivalent ruleset targets it. Release work should verify the effective GitHub configuration rather than assuming this document enforces it by itself.

Issue #9 tracks the initial activation and API verification of this policy. The documentation can be merged before the repository-level setting is enabled, but #9 remains open until GitHub itself reports the intended protection.