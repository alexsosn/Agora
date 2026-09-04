# Context-Fabric revision snapshot materialization

## Status

Normative architecture reference for issue #6 and PR #29. Cache residency, locking, and reclamation after #29 are defined by `ref-context-fabric-cache-lifecycle.md`.

## Ownership boundary

Agora owns selection and materialization of registered corpus resources. The bytes handed to a loader must therefore correspond to the exact Git revision Agora reports as provenance.

This mechanism does not modify Context-Fabric search, parsing, morphology, or other upstream domain behavior.

## Snapshot guarantee

A revision snapshot is a **source/provenance snapshot**. The guarantee is that Agora does not mutate or repurpose a published snapshot, and that selecting another upstream revision cannot change the path or bytes associated with an earlier revision.

This is not a claim that Text-Fabric datasets are inherently read-only or that the snapshot directory is protected against every possible writer at the filesystem level. Text-Fabric itself exposes supported write paths, including `Fabric.save()` for feature data and `tf.dataset.modify()` for transformed datasets.

Consequently, code that intentionally mutates Text-Fabric data must not treat a source snapshot as its writable output location. If writable mutation support is added to Agora or to an integrated plugin in the future, the result must be represented as a derived dataset or module with its own identity and provenance rather than silently changing bytes whose provenance still names an upstream Git SHA.

## Metadata repository

`GitStore.ensure_metadata()` maintains a partial, no-checkout Git repository under `repositories/<resource-key>`. It is used for source discovery and revision resolution only. Published corpus bytes are never served from this mutable repository working tree.

## Snapshot identity

Raw source materializations live under:

```text
snapshots/<resource-key>/<commit-sha>/corpora/<repository-relative-path>
snapshots/<resource-key>/<commit-sha>/feature-modules/<repository-relative-path>
```

A root-level resource uses `__root__` for the final path component.

The exact resolved commit SHA is part of the identity. Re-materializing the same revision and path reuses the existing snapshot. Selecting a different revision cannot mutate the earlier path.

Corpus and feature-module namespaces are deliberately separate because a feature module has a different validity contract: it contains direct non-warp `.tf` feature files and must not contain the parent corpus warp files `otype.tf`, `oslots.tf`, or `otext.tf`.

## Exact tracked bytes

Materialization creates a disposable partial Git repository, fetches the selected commit, and streams `git archive` directly into a temporary extraction directory.

Committed `.gitattributes` can normally make `git archive` omit tracked files via `export-ignore` or rewrite their bytes via `export-subst`. The disposable export repository therefore installs the higher-precedence rule:

```text
* -export-ignore -export-subst
```

before archiving. Published snapshot files consequently come from the selected Git tree rather than archive-specific transformations.

No Agora marker or metadata file is written inside a published snapshot.

## Publication and concurrency

Extraction occurs under `tmp/`. The completed subtree is validated before publication and moved atomically to its revision-addressed destination.

Different revisions have distinct destinations. Concurrent requests for revisions A and B may serialize while exporting, but neither can alter the path already returned for the other revision.

Repository mutation and publication are coordinated with the OS-backed lock protocol defined in `ref-context-fabric-cache-lifecycle.md`. The old create/delete lock sentinel tracked by #10 is not part of the current lifecycle design; process death releases OS lock ownership automatically.

## Feature modules and overlays

Feature modules introduced by #41 use the same revision-addressed raw-source mechanism. `materialize_feature_module()` validates the direct `.tf` feature set at the selected revision and publishes it under the `feature-modules` namespace without requiring `otype.tf`.

`ContextFabricResolver.prepare_with_modules()` builds a derived overlay from parent and module source snapshots. Overlay identity includes the parent revision and each module revision, so an upstream revision change yields a different derived overlay. The overlay is an Agora-derived cache artifact and is not represented as upstream source provenance.

Overlay residency and active-load protection belong to the generic cache-object lifecycle rather than to the source-snapshot identity contract. See `ref-context-fabric-cache-lifecycle.md`.

## Future writable and derived datasets

Text-Fabric supports legitimate dataset mutation and generation workflows. Future Agora integrations must preserve a strict distinction between upstream source provenance and writable derived state.

A writable transformation should conceptually produce a new object:

```text
upstream Git revision
        |
        v
revision-addressed source snapshot
        |
        +--> runtime/generated caches
        |
        +--> derived dataset or feature module
                - base resource
                - base revision
                - transformation or mutation operation
                - derived object identity
```

The source snapshot remains the provenance anchor. A derived object may be writable, but its metadata must identify the source resource/revision from which it was produced and the transformation that produced it. It must not continue to present itself as the unmodified upstream revision.

Runtime-generated Text-Fabric caches are a separate concern from scholarly/source-data mutation. A future writable-runtime design should therefore decide explicitly where such caches live rather than conflating cache writes with derived corpus data.

This section is an architectural constraint for future work, not implementation scope for #29.

## Retention and reclamation

PR #29 established revision-addressed source identity without deletion. PR #31 adds bounded local residency and safe reclamation under the cross-process cache lifecycle described in `ref-context-fabric-cache-lifecycle.md`.

Reclamation may delete an unused local snapshot and later reconstruct it, but it must never rewrite a source snapshot in place or change the meaning of its revision-addressed identity. Access timestamps, leases, and cache-management metadata live outside source snapshot trees.

`AGORA_CORPUS_MIN_FREE_GB` remains a materialization/free-space guardrail. `AGORA_CORPUS_CACHE_MAX_GB` is a soft logical cache target; neither changes provenance semantics.
