# Plan amendment: Pseudepigrapha-TF v0.2.0 promotion (#144)

## Observed implementation-gate failure

The one-shot GREEN helper successfully constructed the intended bounded diff locally, but GitHub rejected its push because the workflow token could not create or update `.github/workflows/materializer-install.yml` without `workflows` permission. The failed push left the temporary `contents: write` helper workflow in the branch and left two established compatibility expectations on the historical `0.1.0` identity.

This is an execution-path failure, not evidence that the intended compatibility changes are wrong. The helper's logged diff provides exact RED/GREEN evidence for the remaining stale assertions.

## Corrective scope

Apply only the already-reviewed bounded compatibility changes directly to the PR branch:

1. in `tests/test_materializer_installation.py`, change the Pseudepigrapha-TF immutable commit fixture from `315439284e765c1d7ea89ffdefdd10f403aa1293` to the verified release commit `317e960e05ca7f36f35a11fcf567285312951095`;
2. in the same test, change the canonical registry version expectation from `0.1.0` to `0.2.0`;
3. in `.github/workflows/materializer-install.yml`, compare the installed `pseudepigrapha-tf` distribution version to `plugin['version']` instead of the obsolete literal `0.1.0`;
4. delete `.github/workflows/agent-pr145-red2.yml` completely.

Do not add workflow write permissions, retain a self-modifying helper, change Agora runtime behavior, patch Pseudepigrapha-TF semantics, or broaden the registry promotion.

## Verification after correction

The repaired exact head must pass the Foundation suite, Registered materializer install smoke, and Materialization sandbox E2E lanes applicable to this PR. The install smoke must demonstrate that Agora resolves/fetches the exact registered commit, installs the `0.2.0` package, validates its manifest/materializer identity, and does not fall back to `0.1.0`.

Before merge, perform a fresh logically independent adversarial review of the exact final tree and current-main merge ref. The review must explicitly confirm that no temporary write-capable helper remains, the registry changes only the intended stable version/ref identity, the exact-release regression remains independent of the registry value it checks, and all live/install/materialization evidence is tied to the final head.