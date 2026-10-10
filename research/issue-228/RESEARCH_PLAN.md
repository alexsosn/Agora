# Issue #228 — shared parent batching, research and plan (RED4a)

## Current source-grounded behavior

Merged Agora PRs #207/#208/#209/#218/#220 established `resolve_managed_parent`, immutable Context-Fabric snapshot leases, registered sandboxed materializer execution and explicit local-module publication. But `materialize_requested_feature_module` prepares its parent and leases the snapshot independently on each invocation, so two modules requesting the same parent cannot prove a one-preparation transaction. `GitStore.local_feature_module_path` and `ContextFabricResolver.prepare_with_modules` already provide publication and composition; do not add a second store or reinstall parents.

The existing single-module authorization is strict: bundled catalog's `acquisition.materializer` must equal the requested installed producer; immutable `parent-base` must equal pinned canonical parent revision; both manifest `parent_input` and output `composition` must match; publication uses a persistent per-module lock and refuses an existing or symlinked target. A batch must reuse those identical checks, not fork a weaker set.

## Phase RED4a acceptance

1. One explicit internal `materialize_requested_feature_modules(requests, *, cache_dir, install_root, registry_path, requested_versions)`, **no caller resolver, parent path, trusted bit, output root or automatic plugin installation**. Requests are exact mapping `{module_id,plugin_id,materializer_id,source}` or equivalent typed inputs.
2. Complete manifest/catalog/output-target/producer authorization preflight for **every request before any corpus preparation**, conversion or publication. Reject duplicate module IDs, missing producer, mismatched parent-base revision, wrong parent kind, wrong module kind, incompatible producer and no common version.
3. Group by `(parent_resource_id, resolved_parent_version, exact_parent_catalog_commit)`. Version intersection includes declared module compatibility **and** the installed manifest's `parent_input.parent_versions` and `output.composition.compatibility.parent_versions`. Ambiguous intersection must be resolved explicitly, not guessed from different modules' defaults.
4. For each group, invoke `resolve_managed_parent` once, verify version/commit against each catalog binding, hold a single real `GitStore.acquire_cache_lease` across all registered materializer conversions. No output may silently overwrite another; obtain per-module locks in deterministic order and recheck all targets before starting the first producer.
5. If producer 2 fails after producer 1 succeeded, preserve safely published producer 1 and raise a typed `BatchMaterializationError` listing published module IDs/paths and failed module ID, chaining the original error. Never return a misleading complete batch result. Alternative atomic batch staging requires a separate explicit design/approval and is not implied.
6. Return exactly `dict[module_id, Path]` on success. No replacement CUC warp, no implicit module composition/load; consumers continue to use existing Context-Fabric prepare/load.
7. TDD RED with mock resolver verifying exactly one parent preparation/lease for two modules; negative all-or-nothing **preflight** tests and typed partial success test; real tiny Git CUC+two independent nonwarp feature module paths smoke (no Burns data or redistributable corpus).
8. GREEN on a branch, frozen-head unit/platform CI, logically independent skeptical source/code/data review for each merge; do not merge without green. Full CUC+Burns contract blocked by upstream CTC-TF #117.

## Design constraints / non-goals

Prefer factoring an internal publication-plan helper from the existing single-module facade so both single and batch paths reuse precisely the same producer/catalog/output validation. Never accept a fake caller resolver in an externally exposed entrypoint. Sandbox and source acquisition remain the existing `registered.materialize_registered` path. Cache lease is only on an exact verified snapshot; do not create multiple parents for one group. No SAT solver, package manager or speculative network installs.
