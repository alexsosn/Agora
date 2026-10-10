# #219 — explicit, safe local feature-module publication (issue #135 RED3e)

## Research (actual source contracts)

Reviewed `GitStore.local_feature_module_path`, `GitStore.local_feature_module` and `ContextFabricResolver._prepare_feature_modules` in bundled `plugins/context-fabric/src`, plus the already merged #207/#208/#209/#218 binding, host, lease and non-injectable facade code. `cuc-burns` in the bundled catalog is a `feature-module` with `parent=cuc`, `parent_versions=["0.2.8"]`, acquisition `local-module`, `tf_path=tf/0.2.8`, and a `parent-base` dependency matching the CUC catalog's immutable ref. The existing store consumes local modules at `<cache>/local-modules/<module-id>/<tf_path>`; during load, it creates a content-hashed immutable feature-module snapshot and composes an overlay without copying or altering parent nodes.

The materializer host already validates output and rejects symlinks and warp files in `feature-module` output; it stages and publishes atomically at the requested output. It requires preinstalled/verified third-party code and a read-only OS sandbox for parent-bound runs. Its `_preflight_output` can accept an *existing empty output directory*, so this publication facade must require an **absent destination** and serialize concurrent writers independently of the installer lock.

## RED3e/plan

Add a private, explicit-by-`module_id` facade, not a new raw-output-path CLI. Validate *before preparing parent or executing code*:

- bundled catalog resource is `feature-module`, acquisition `local-module`, parent is a corpus, its `tf_path` is a contained relative path and the requested version is compatible;
- producer is already installed and its actual manifest's materializer has matching `parent_input.resource`, requested TF version, `output.composition.kind=feature-module`, `output.composition.parent`, and declared parent-version compatibility;
- any `parent-base` immutable dependency agrees exactly with the bundled parent catalog commit (avoid version-only compatibility illusions);
- target is **only** `GitStore.local_feature_module_path(module.id,module.tf_path)`, not a caller-supplied path; any preexisting destination (including an empty directory or symlink) is rejected; no parent/CUC warp is copied;
- reject symlinks in the cache publication directory and all target ancestors, and serialize concurrent requests with a persistent per-module publication lock; hold the lock over the preflight and full materializer call.

Delegate directly to `materialize_managed_feature_module` (bound and leased parent, registered execution, OS sandbox, transactional staging/output, receipt). A successful result becomes discoverable through unchanged `GitStore.local_feature_module` and `ContextFabricResolver.prepare_with_modules`; no second store, local TF duplicate, or manual file placement. An explicit `--output` pathway is separately available via the already merged internal facade and **does not publish automatically**.

## Verify / boundaries

Preserve a failing RED test commit before GREEN. Test exact target selection, mismatched catalog/producer, version/parent revision, nonlocal acquisition, preexisting path refusal, symlinked cache, concurrent locks, no implicit third-party install/approval, and a real local GitStore content-hashed module snapshot (without downloading Burns source). Then exact-head Foundation and platform runs, independent adversarial source review, and only then merge.

No public CLI, no general dependency resolver, no user-provided untrusted parent override. The final real CUC + Burns application path is blocked by CTC-TF#117 producer manifest and remains a separate #135 acceptance gate.
