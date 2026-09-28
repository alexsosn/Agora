# Research: trusted parent binding for materializer-produced feature modules (#135)

## Question

A materializer that produces a Text-Fabric **feature module** needs two runtime inputs: the user's licensed source data and the exact parent corpus whose nodes the module annotates. Agora's materializer host currently accepts exactly one input directory, so such a materializer cannot be registered or executed at all. What is the smallest change that gives a materializer a trusted, read-only, identified parent without turning Agora into a general resource manager?

This document records observed current behavior and upstream evidence. It does not choose the implementation; that is `P1-design-materializer-parent-binding-135.md`.

## Current Agora behavior (verified at `689cd69` plus the open `http-archive` work)

### One source, one output

`registry/schema/materializer-plugin.schema.json` declares a materializer as:

- `acquisition` — one or more strategies: `git`, `http-archive`, `user-local`;
- `input` — exactly one object, `{type: directory, required_globs, allow_symlinks}`;
- `execution` — `{type: python-module, module, args, network: "deny"}`;
- `output` — `{format, required_paths, composition?}`.

`executionArgument` permits exactly three placeholders: `{source}`, `{output}`, `{source_revision}`. There is no way to name a second input, and no way to pass a resolved resource identity.

### Output `composition` is descriptive, not executable

The schema already carries `output.composition = {kind: feature-module, parent, compatibility.parent_versions}`, and `materialize()` copies it verbatim into `agora-materialization.json`. Nothing reads it to decide what to acquire or mount. It documents what was produced; it does not bind what the run consumed. #135 is explicit that this separation must be preserved — execution dependencies must be declared inputs, not inferred from output metadata.

### Sandbox exposes exactly three roots

`_build_linux_sandbox` binds `--ro-bind plugin_root /plugin`, `--ro-bind source /input`, `--bind output.parent /agora-output`, with `--unshare-all`. `_build_macos_sandbox` builds an allow-read subpath set (system paths, `sys.prefix`, plugin root, source, output parent, work dir), allows write only under the output parent and work dir, and ends with `(deny network*)`.

The two backends differ in an important way that any new input inherits: **Linux remaps paths** (`{source}` renders as `/input`), while **macOS passes real host paths**. A parent placeholder must be rendered per backend exactly as `{source}` already is.

### The registered path is integrity-bound

`agora_materialize_registered.materialize_registered()` holds the installer runtime lock across final verification and execution, re-checks the managed environment hash, re-validates that the installed bytes still declare exactly the materializers the current registry approves, and only then calls `host.materialize()`. Any parent binding must be established inside that same protected window, otherwise the approved execution identity and the parent it was approved against can drift apart.

### Parent corpora are already resolvable — in a different component

`plugins/context-fabric/src/agora_context_fabric/resolver.py` already does everything a parent binding needs:

- `prepare(resource_id, version=…, source_revision=…)` returns `PreparedCorpus(resource_id, member_id, logical_name, relative_path, path, version, source_revision, modules)`;
- the path is an immutable content snapshot under `snapshots/<repo>/<revision>/corpora/<tf path>`, not a working checkout;
- `GitStore.acquire_cache_lease(path)` pins a cache object against eviction for the duration of active use;
- `_check_parent_base()` already enforces an exact declared parent commit for registered feature modules.

This capability lives in the Context-Fabric plugin, while materializer execution lives in repository-level `scripts/`. Nothing currently connects them. That gap — not a missing algorithm — is the actual blocker.

### The consumer side landed already

`local_feature_module()` (merged with `cuc-burns`) reads a user-materialized module from `<cache>/local-modules/<resource id>/<tf_path>`, copies its bytes into a content-addressed snapshot, and composes it over the prepared parent as a hard-linked overlay. So a produced module has a defined destination; today the user must place it there by hand.

### Nothing links a feature-module resource to its producer

`cuc-burns` declares `acquisition.strategy: local-module` with upstream repository `alexsosn/CTC-TF`, and `registry/materializers.yaml` currently registers no Burns materializer at all — the legacy `ugarit-context-parsing convert` entries were removed. A resource therefore cannot state *which* materializer produces it, and a materializer cannot state *which* registered parent resource it requires.

## Upstream evidence

### Burns / CTC-TF — one parent, exact commit, path-shaped CLI

The upstream `module` subcommand is invoked as:

```
ugarit-context-parsing module <source> --input-format csv --cuc <cuc>/tf/0.2.8 --output <out>
```

The parent is passed as a **filesystem path to the TF dataset directory**, which is exactly `PreparedCorpus.path`. Upstream verifies the required CUC files by size and SHA-256 itself and records a structural fingerprint (146017 `sign`, 27770 `word`, 7616 `line`, 334 `column`, 279 `tablet`) in every emitted feature header. Agora does not need to understand any of that — it needs to hand over the right directory and the resolved identity.

### CATSS-TF — three artifacts, at most one parent each

CATSS-TF#40 restructures that repository to emit:

| artifact | kind | parent |
|---|---|---|
| `catss` | standalone corpus | none |
| `catss-bhsa` | feature module | ETCBC/bhsa 2021 |
| `catss-lxx` | feature module | CenterBLC/LXX 1935, validated against release `v1.0.1` / commit `f32a98eddf7eb239aa73ab863d70381e416d5076` |

**This settles the open question in #135 about input arity.** Neither driving case needs two parents in one run. A single optional parent input satisfies Burns and both CATSS modules; a named input map would be speculative generality. The schema shape should nevertheless be chosen so a named map remains an additive change.

CATSS also demonstrates the second requirement: `catss-lxx` validates a *stricter* identity than Agora's catalog expresses. Agora knows a logical TF version (`1935`); the producer requires a specific upstream release commit. Agora must therefore pass the resolved parent's **immutable revision**, not merely the compatibility label, and let the producer fail closed. Passing only `parent_versions` would let Agora imply a compatibility it never verified.

### A package mixes standalone and parent-dependent materializers

CATSS-TF publishes all three from one plugin. So parent resolution must be **per materializer**, not per plugin: installing the package once must still let `catss` run with no parent resolution at all.

## Constraints that the design must not weaken

1. **Execution stays offline.** Acquisition (including the new `http-archive` download) happens before the sandbox; `network: deny` during execution is unchanged. Parent preparation is acquisition-phase work and must also complete before the sandbox starts.
2. **Four distinct trust domains.** Materializer code (read-only), user source (read-only), prepared parent (read-only), output (writable). The parent must never be writable and must never be merged into the source tree — #135 requires it be a separate mount, and the module must not copy parent warp files into its output.
3. **Immutability of the parent snapshot.** The resolver already returns content snapshots; a lease must be held so eviction cannot delete the parent mid-run.
4. **No silent parent substitution.** #135 requires that a materializer cannot receive an arbitrary local directory as a "parent" without an explicit trust/override path. Managed resolution must be the default; a raw path must be a visibly explicit, provenance-recorded override.
5. **Backward compatibility.** Existing single-source materializers must keep validating and running unchanged, with no manifest migration.
6. **Boundary.** Agora owns resolution, trusted binding, execution constraints, provenance and composition orchestration. Parent *semantic* validation stays upstream — Agora must not re-implement a producer's fingerprint check.

## Tension with a recorded non-goal

`wiki/architecture/ref-local-materialization.md` lists "automatic consumer hand-off" among the things deliberately unresolved. #135's user outcome 6 requires that after materialization the parent plus module load through the ordinary Context-Fabric path. These are reconcilable only if hand-off is **explicit and user-initiated** rather than automatic: a materializer run may publish into the local-modules store because the user asked for that module, but nothing may install or compose a module merely because a resource references one. The design must state this narrowing rather than silently overturning the non-goal.

## Open questions for the design

1. Placeholder syntax for the parent path and identity — plain `{parent}` / `{parent_revision}` versus an indexed form that anticipates a future input map.
2. Where the orchestration layer lives, given that resolution is in a plugin package and execution is in repository scripts. Importing a plugin from `scripts/` is a new dependency direction and needs an explicit decision.
3. How a feature-module resource declares its producer, so `cuc-burns` can be materialized by id rather than by the user knowing which CLI to run.
4. Whether v1 publishes into the local-modules store automatically or leaves publication a separate explicit step.
5. Whether the parent may itself be a collection member, and if not, how that fails.
6. What provenance must record so a produced artifact can be re-derived: resource id, selected TF version, immutable source revision, snapshot digest.
