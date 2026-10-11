# Issue #211 — cumulative source Git deadline (second independent slice)

## Research evidence, 2026-10-11
- Production `acquire_git_source` executes Git init, add origin, sparse setup, blob:none fetch, sparse-checkout, checkout, revision resolution, then validates required source files. Existing `GIT_TIMEOUT_SECONDS=120` applies independently to *each* subprocess, so total sequential wall time may approach ~8 × 120s even if each command meets its timeout. No absolute deadline is propagated across subprocesses.
- Pinned upstream Coptic real run `38136814878` acquired all 565/220,289,125-B TT files in **19.206s** (fetch .208s, checkout 18.968s), with ~280,557,423 B post-state scratch. Its former ~15m slow check was unrelated verifier-induced excluded hydration, fixed in merged #249/#250. Ordinary legacy full fetch and explicit local `--source` should not be penalized by a Coptic-specific workaround.
- A conservatively wide **600-second cumulative Git command budget** exceeds observed Coptic elapsed by >30× and is below the sum of individual 120-second upper limits. It is not a peak-disk or converter runtime bound, and is not a reason to weaken immutable commit or `blob:none` checks. Maintain 120s per-command maximum inside remaining total.

## Research → RED → GREEN → test
1. RED: `_run_git` should accept an absolute monotonic deadline and pass `min(120, remaining)` as subprocess timeout for all branches (check_output, capture_output run, normal run), reject expired budget without spawning Git, and distinguish cumulative timeout from per-command timeout. Measure with fake clock, no sleep.
2. RED: `acquire_git_source` must propagate **one shared deadline** across every invocation, reject cumulative expiry after source validation, and clean the whole transaction root on any expired phase. Legacy full-source and explicit user-local override remain valid.
3. GREEN: constant `GIT_MAX_TOTAL_SECONDS=600`, monotonically derived once per Git acquisition, check before each child and post-validation. No external environment override, no host Git config/trace forwarding, no modification to trust, source pin or sparse order. Phase timer opt-in remains reporting-only and never an enforcement mechanism.
4. Focused timeout/cleanup tests and real local Git partial-clone fixture, then triggered Foundation, pinned Coptic inventory, full registered Coptic E2E (or explicitly document blocked external evidence), adversarial review of the exact head and merge gate.

Remaining #211 work: peak scratch disk/capacity, transferred-byte throughput, user-selectable bounded limits for deliberately massive source types, and comparing multiple real upstream runs; this slice alone must not close issue.
