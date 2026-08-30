---
name: agora-plugin-review
description: "Use this skill when reviewing Agora issues or pull requests that touch third-party plugins, plugin tests, adapters, or skills; detect scope creep, distinguish integration failures from upstream behavior, and keep fixes in the correct repository."
license: MIT
metadata:
  scope: repository-maintenance
  project: Agora
---

# Agora plugin review

Use this skill for independent review of plugin-related Agora work.

The first review question is architectural ownership, not whether the proposed implementation can be made technically correct.

## Review order

### 1. Identify the claimed problem

State the observable failure or requested capability without accepting the PR's framing.

Then ask: **does the same problem exist when the third-party plugin is run directly without Agora?**

If yes, treat an Agora implementation of the fix as presumptive scope creep unless there is an explicit architecture decision adopting that behavior.

### 2. Classify the change

Acceptable Agora categories include:

- marketplace/registry metadata;
- discovery and selection;
- installation/bootstrap;
- client manifest generation;
- process launch;
- transport bridging;
- configuration;
- Agora-owned resource resolution;
- compatibility/version declarations;
- health/smoke verification;
- generic marketplace skills;
- plugin-facilitation skills for existing upstream capabilities.

Flag changes that primarily alter upstream semantics, add domain capability, or maintain a third-party behavioral fork.

### 3. Inspect adapters

A legitimate thin adapter should be:

- necessary for integration;
- semantics-preserving;
- based on public upstream interfaces where possible;
- small and removable;
- visible in documentation/metadata when material.

Treat monkey-patches, private-internal shims, replacement algorithms, and output correction as strong evidence that the change belongs upstream.

### 4. Inspect tests

Agora tests should prove Agora claims.

Appropriate assertions include generated metadata, install/launch wiring, transport compatibility, tool discovery, resource resolution owned by Agora, and a representative published upstream operation reaching a structurally valid result.

Ask whether the test is really checking an upstream algorithm. Search correctness, count exactness, parser correctness, morphology correctness, ranking, or domain-analysis semantics normally belong in the upstream project.

### 5. Inspect skills

For each new or changed skill, classify it as:

- generic marketplace workflow;
- plugin facilitation of an existing upstream capability;
- repository-maintenance guidance;
- substantive plugin/domain capability.

Only the first three belong in Agora. The fourth belongs upstream whenever practical.

A skill is not thin merely because it contains no executable code. If it emulates a missing tool or systematically repairs incorrect upstream results, it has crossed the boundary.

## Review outcomes

### Approve

Approve when the PR solves an Agora-owned integration problem, keeps adapters thin, and limits tests/skills to Agora-owned contracts.

### Request changes

Request changes when a mixed PR contains both legitimate integration work and upstream-owned behavior. Ask the author to separate the upstream fix from the Agora metadata/integration change.

### Redirect/close

Recommend closing or replacing the PR when its central purpose is to fix an upstream bug, add an upstream feature, or create an Agora-specific semantic fork.

The appropriate Agora follow-up may still be useful: link the upstream issue, document the limitation, constrain a version, or downgrade verification status.

## Fast ownership heuristic

> If removing Agora leaves the defect unchanged, fixing the defect is normally not Agora's business.

Do not let implementation effort already invested in a PR change that conclusion.
