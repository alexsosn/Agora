# Issue #300: supervised standalone collection-index source acquisition

## Research: observed failure and exact code paths

- Original full CI for #295 ([run 43102936299](https://github.com/alexsosn/Agora/actions/runs/43102936299)) cancelled `generate (greek_literature)` after 25 minutes. The log showed the generator's Git acquisition without intervening output; runner cleanup terminated child `git` and `git-remote-https` processes.
- A single targeted retry **succeeded** at the same head; another previous success ([43102885087](https://github.com/alexsosn/Agora/actions/runs/43102885087)) took 16m20s in generation. Network duration is variable, so applying the existing 15-minute runtime default unchanged would be incorrect.
- `scripts/generate_context_fabric_collection_indexes.py` instantiates `agora_context_fabric.gitstore.GitStore`. `gitstore/_core.py::_run` calls `subprocess.run` without a timeout; `ensure_metadata` clones or fetches. `gitstore_long_ops.GitStore` already overrides Git process invocation to use an operation deadline, isolated process group and cleanup, and `operation.py` supplies `OperationControl` and `operation_scope`.
- The generator handles source metadata/TF-header reads, **not** the user-facing long compiler. Keep the default runtime acquisition semantics unchanged. Its workflow outer timeout is 25 minutes; use a generator-specific positive acquisition budget below this limit, allowing observed >22-minute successful Greek fetches plus completion/cleanup. Log resource and stage to differentiate metadata timeouts from canonical index mismatches.

## Plan and TDD / evidence gates

1. RED before code: exercise a fake resource/catalog/store and verify `generate_documents` gives each resource its own finite operation deadline and restores prior context on success/error. Fake stalled Git process must terminate through the *existing* `gitstore_long_ops` tree cleanup; no remote network in tests. Wrong/negative/nonfinite timeout fail before acquisition. Positive path still yields canonical document strings.
2. GREEN: use the existing supervised `GitStore` + `OperationControl` inside per-resource generation. Default generator-specific budget 24 minutes; expose small CLI override for testability, not mutate process-wide env or user-facing runtime. Reuse established source policy and cache. Do not replace Git code or add another process watchdog.
3. Run focused fake-subprocess tests, committed-index tests, Foundation CI, and full live index CI on immutable source revisions; verify canonical index equivalence, runner cleanup and report actual duration. Do not claim live success from mocked subprocess tests.
4. Perform logically-independent adversarial review of the entire diff, including budget interactions with the 25-minute job timeout, cancellation behavior, multiple resource iterations, invalid override values, and traceback/progress diagnostics.
5. Do not merge until exact-head full CI; apply further scoped fixes if tests reveal a real regression. If the live source exceeds 24 minutes but makes real progress, reconsider budget based on observed data rather than silently raising global runtime timeouts.

## Non-goals
No broad process runner rewrite, upstream Rust migration, cache format change, Git credentials or source revision selection changes.
