# Plan: trusted parent binding for materializer-produced feature modules (#135)

Companion to `P1-research-materializer-parent-binding-135.md`. That document records the evidence; this one chooses the implementation and the TDD sequence.

## Goal

A user can ask Agora for a registered feature module such as `cuc-burns`, and Agora resolves the declared parent corpus once, runs the registered materializer with the user source and the parent as **two distinct read-only inputs**, records the resolved parent identity in provenance, and leaves the module where the ordinary Context-Fabric composition path can load it with its parent.

## Scope boundary

In scope: manifest input declaration, execution placeholders, sandbox mounts, parent resolution/lease, trust rules, provenance, a thin orchestration entry point, and publication into the existing local-modules store.

Out of scope for v1: more than one parent per materializer, dependency solving, lockfiles, artifact reuse caches keyed across runs, automatic installation of materializer plugins, automatic composition of modules a user did not ask for, and Windows sandboxing (unchanged from today).

## Decisions

### D1 — exactly one optional parent input, declared explicitly

Both driving cases need at most one parent (`catss` none, `catss-bhsa` BHSA, `catss-lxx` LXX, `cuc-burns` CUC). v1 adds one optional sibling of `input`:

```json
"parent_input": {
  "resource": "cuc",
  "parent_versions": ["0.2.8"],
  "required_paths": ["otype.tf", "oslots.tf", "otext.tf"]
}
```

`resource` is an Agora resource id — the same namespace `output.composition.parent` already uses. `required_paths` is a cheap structural sanity check that the mounted directory really is a Text-Fabric dataset; it is not a semantic compatibility check, which stays upstream.

A named multi-input map remains a purely additive future change; nothing in v1 forecloses it.

### D2 — `output.composition` stays descriptive

Execution binding comes only from `parent_input`. When both are present, validation requires that `composition.parent` and `parent_input.resource` agree, and that `composition.compatibility.parent_versions` is a superset of `parent_input.parent_versions`. Contradiction fails validation instead of picking one silently.

### D3 — placeholders mirror the existing source pair

`executionArgument` gains `{parent}`, `{parent_revision}` and `{parent_version}`. A manifest that uses any of them without declaring `parent_input` fails manifest validation; a manifest that declares `parent_input` but never references `{parent}` also fails, since Agora would then mount a parent the producer cannot see.

Rendering follows `{source}` exactly: on Linux `{parent}` becomes the remapped `/parent`; on macOS it becomes the real host path.

### D4 — the host stays plugin-agnostic; a thin orchestrator resolves

`scripts/agora_materialize.py` is the sandbox- and provenance-critical component and must not learn about resource registries. It gains one narrow typed parameter:

```python
@dataclass(frozen=True)
class ParentBinding:
    path: Path                 # prepared, immutable, read-only
    resource_id: str | None    # None only for an explicit override
    version: str | None
    source_revision: str | None
    trusted: bool              # False for an explicit user-path override
```

Resource resolution lives in a new `scripts/agora_compose_feature_module.py`, which imports the Context-Fabric resolver, prepares the parent, holds a cache lease, and calls `materialize_registered(..., parent=binding)`. This is the only new dependency direction, it is one-way, and it is confined to the orchestrator.

### D5 — managed resolution is the default; overrides are explicit and marked

Without flags, the parent is resolved from the registry. `--parent-path <dir>` is accepted only together with `--untrusted-parent`, is refused when the directory is not a Text-Fabric dataset, and is recorded in provenance as `{"trusted": false, "resource_id": null}`. An artifact produced that way is never published into the local-modules store by default.

### D6 — the parent is leased, mounted read-only, never copied

The orchestrator holds `GitStore.acquire_cache_lease()` on the prepared parent across the whole run so eviction cannot remove it mid-execution. The sandbox binds it read-only at `/parent` (Linux) or adds it to the readable subpath set without any write rule (macOS). After execution, output validation additionally asserts that the produced module contains none of `otype.tf`, `oslots.tf`, `otext.tf` when `output.composition.kind == "feature-module"`, so a module can never smuggle the parent warp into its own artifact.

### D7 — a feature-module resource names its producer

New acquisition strategy value `materializer` for feature-module resources:

```yaml
acquisition:
  strategy: materializer
  lazy: true
  materializer: {plugin: ugarit-context-parsing, id: burns-cuc-module}
```

`local-module` keeps its current meaning: produced by the user with upstream tooling, Agora only reads the result. `materializer` means Agora can produce it on request. Registry validation requires that the named plugin and materializer id exist in `registry/materializers.yaml`, that the materializer declares `parent_input.resource` equal to the resource's `parent`, and that the declared parent versions intersect.

### D8 — publication is explicit by construction

`agora_compose_feature_module.py --module cuc-burns` writes into that resource's local-modules slot, because naming the module *is* the user's explicit request. `--output <dir>` overrides and publishes nothing. This narrows, and does not overturn, the recorded "no automatic consumer hand-off" non-goal: nothing composes or installs a module the user did not name.

### D9 — parent must be a corpus

A collection member cannot be a parent in v1. The orchestrator fails closed before installation or execution with an explicit error, mirroring the existing `_prepare_feature_modules` rule.

### D10 — provenance records resolved identity, not the request

`agora-materialization.json` gains:

```json
"parent": {
  "resource_id": "cuc",
  "version": "0.2.8",
  "relative_path": "tf/0.2.8",
  "source_revision": "0408967b…",
  "trusted": true
}
```

The resolved revision is what the producer was actually given, so `catss-lxx`-style stricter validation is reproducible from the receipt.

## TDD sequence

Each RED lands before its GREEN and is preserved.

### RED 1 — manifest contract and backward compatibility
1. an existing single-source manifest validates and runs byte-identically;
2. a well-formed `parent_input` validates; unknown members are rejected;
3. `{parent}` used without `parent_input` fails manifest validation;
4. `parent_input` declared but `{parent}` never referenced fails manifest validation;
5. `composition.parent` contradicting `parent_input.resource` fails validation;
6. `parent_versions` not covered by `composition.compatibility` fails validation.

### RED 2 — sandbox and rendering
1. Linux binds the parent read-only at `/parent` and renders `{parent}` as `/parent`;
2. macOS grants read on the parent subpath and no write rule for it;
3. a materializer that writes into the parent fails;
4. no `parent_input` produces no parent mount and an unchanged command line;
5. `{parent_revision}` / `{parent_version}` render the resolved values, empty only for an untrusted override.

### RED 3 — resolution and identity
1. the orchestrator prepares the declared parent at a compatible version and passes its snapshot path;
2. an incompatible requested version fails before installation, execution, or any output mutation;
3. a stricter producer rejection after Agora's resolution surfaces as a materializer failure, and nothing is published;
4. a collection-member parent is refused;
5. resolved identity, not the requested constraint, is what reaches provenance.

### RED 4 — trust
1. `--parent-path` without `--untrusted-parent` is refused;
2. an untrusted override is recorded as `trusted: false` and is not published into the store;
3. a non-Text-Fabric directory is refused as a parent in both trusted and override modes.

### RED 5 — orchestration, sharing, publication
1. two modules declaring the same parent/version prepare that parent once and reuse the lease;
2. a standalone materializer in the same installed plugin runs with no parent resolution at all;
3. a produced feature module contains no parent warp file;
4. the artifact lands in `<cache>/local-modules/<resource id>/<tf_path>` and then composes with its parent through the ordinary Context-Fabric load path;
5. the installer runtime lock still spans final verification through completion when a parent is bound.

## Validation gates before merge

- `scripts/validate_registry.py` and both generated-catalog `--check` runs;
- the full `test_materialization*` and `test_materializer_*` suites, plus `test_context_fabric_runtime` and `test_feature_module_review_regressions`;
- a real sandboxed end-to-end run on Linux and macOS producing a feature module against a prepared parent;
- exact-head Foundation.

## Independent review focus

1. Can a materializer reach the parent with write access on either backend?
2. Can an untrusted directory become a trusted parent through any path, including symlinks in `--parent-path`?
3. Can a produced module contain parent warp files or a copied parent?
4. Does provenance ever record a compatibility claim Agora did not resolve?
5. Does a single-source materializer change behavior in any observable way?
6. Is the plugin import confined to the orchestrator, leaving the host independently testable?

## Definition of done

#135 is complete when a user can run one documented command that produces `cuc-burns` from the user's Burns source and the registered CUC parent, the receipt names the resolved parent commit, and `load_corpus("cuc", modules=["cuc-burns"])` then works without any manual file placement — with the preserved RED contracts above green and an independent adversarial review of the frozen head.

## Sequencing note

D7 registers a producing materializer for `cuc-burns`. That entry cannot be written until the upstream CTC-TF manifest declares the `module` materializer with `parent_input` and an `http-archive` acquisition for the Burns deposit. Agora work (D1–D6, D8–D10) does not block on it; the registry entry (D7) does.
