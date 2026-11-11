# Issue #294 — collection-index CI scope

## Research (2026-11-11)
- [#246 / PR #272](https://github.com/alexsosn/Agora/issues/246#issuecomment-6125163222): exact-head collection-index run 38252583804 took 19m04s elapsed; the PR registered a normal corpus + optional feature module but did not change the four configured collection resources.
- `.github/workflows/context-fabric-collection-index-generation.yml` uses a four-cell PR matrix triggered by any `registry/resources.yaml` change; no timeout. It can hold PR validation behind unrelated metadata downloads.
- Current `registry/resources.yaml` contains only `corpus` and `collection` kinds; configured collection IDs are `bible`, `patristics`, `greek_literature`, `translatin-manif`.
- Branch protection status requirements are inaccessible through the current GitHub connection (403 on #246). Avoid job-level `if:` that collapses matrix check identities (documented breakage on #265).

## Plan
1. Preserved RED tests against canonical registry plus malformed YAML, reordered/deleted/renamed collections, mode/symlink changes, unsafe mixed diffs, and synthetic GitHub PR merge ancestry.
2. Implement a small fail-closed classifier that compares ordered **complete collection rows** between HEAD^1 and HEAD. Only unchanged collections with corpus-only resource edits and harmless Markdown may skip network index generation; all unknown, mixed executable and malformed inputs => full.
3. In PR scope step, obtain code with `git show HEAD^1:scripts/ci_collection_index_scope.py` from the **trusted base**, falling back to full on initial/new-script PRs. Never execute PR-head classifier for CI selection.
4. Keep four `generate (<resource>)` matrix jobs and success contexts by skipping expensive *steps* rather than jobs. Manual workflow-dispatch always runs full. Bound the matrix with explicit timeout.
5. Independent adversarial review of exact PR head, run relevant tests and inspect real GitHub Actions result before merge; do not claim cost savings from historical wall duration alone.

## Scope limitations
This intentionally does not infer indexer dependency changes from arbitrary scripts or registry edits. Any executable or unrecognized path triggers full. It is conservative and will not eliminate every redundant run such as PR #272 with additional registry/module files. Future optimization needs measured evidence and separate TDD gates.
