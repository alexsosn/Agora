# Context-Fabric immutable snapshot materialization

## Status

Normative architecture reference for issue #6 and PR #29.

## Ownership boundary

Agora owns selection and materialization of registered corpus resources. The bytes handed to a loader must therefore correspond to the exact Git revision Agora reports as provenance.

This mechanism does not modify Context-Fabric search, parsing, morphology, or other upstream domain behavior.

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

Extraction occurs under `tmp/`. The completed subtree is validated before publication and moved atomically to its revision-addressed destination. The existing per-repository materialization lock serializes publication for one resource cache key.

Different revisions have distinct destinations. Concurrent requests for revisions A and B may serialize while exporting, but neither can alter the path already returned for the other revision.

The current lock is still the crash-stale sentinel tracked by issue #10. Replacing that lock is independent of snapshot identity and belongs in the follow-up locking work.

## Feature modules and overlays

Feature modules introduced by #41 use the same immutable raw-source mechanism. `materialize_feature_module()` validates the direct `.tf` feature set at the selected revision and publishes it under the `feature-modules` namespace without requiring `otype.tf`.

`ContextFabricResolver.prepare_with_modules()` continues to build the existing derived overlay from immutable parent and module inputs. Overlay identity includes the parent revision and each module revision, so an upstream revision change yields a different derived overlay. The overlay is an Agora-derived cache artifact and is not represented as upstream source provenance.

## Retention

PR #29 is retention-only. It does not delete snapshots or expose pruning APIs. Cross-process-safe eviction and LRU policy remain tracked by #30/#31 and must not weaken revision-addressed immutability.

`AGORA_CORPUS_MIN_FREE_GB` remains a materialization guardrail. It is checked before and during streamed extraction; it is not a cache quota or eviction policy.
