# Independent Architecture and Code Review — 2026-08-29

Reviewed against `main` at commit `79242f0e56f9b886904e814231ecff8cbbda8173`.

This review is intentionally independent and skeptical. It is grounded in the implementation currently present in the repository rather than the intended architecture described in planning documents.

## Overall assessment

The basic architecture is sound: canonical scholarly metadata → generated client manifests → provider-specific runtimes, while third-party MCP servers remain upstream rather than being unnecessarily vendored. The Context-Fabric provider/resource distinction is also the right direction; large corpus families should not become thousands of top-level marketplace plugins.

Agora is not release-ready as v0.1 yet. The main blockers are that the trust model described in the documentation is not propagated through the runtime, collection handling is partly indexed and partly ad hoc, verification claims are broader than the evidence produced by CI, and the current `main` branch does not pass its own test suite.

## Findings

### 1. Critical — `main` currently fails its own tests, and the latest commit is incomplete

The latest commit adds `tests/test_context_fabric_load_smoke.py`, which imports:

```python
from scripts.smoke_context_fabric_resources import (
    LOAD_CASES,
    summarize_loaded_corpus,
    select_collection_member,
)
```

but `scripts/smoke_context_fabric_resources.py` is not present in the repository. The Foundation workflow therefore fails during test discovery with:

```text
ModuleNotFoundError: No module named 'scripts.smoke_context_fabric_resources'
```

The immediately preceding commit passed the Foundation workflow.

This also exposes a repository-governance problem: `main` is currently unprotected and has no required status checks, so commits that break CI can land directly.

**Recommendation:** fix or revert the incomplete commit first, then require the Foundation workflow before changes can land on `main`.

### 2. High — the most important scholarly trust metadata disappears before it reaches MCP clients

The canonical resource registry contains fields such as:

- resource verification status;
- licensing and redistribution status;
- known issues;
- provenance/source snapshot;
- descriptions and period metadata;
- pinned upstream `ref` / `tf_path` where applicable.

TLHdig-TF, for example, is explicitly Experimental and records warnings that the pinned data predates later converter fixes.

However, `scripts/generate_context_fabric_catalog.py` projects only a small subset of the canonical resource record. `ResourceSpec` in `catalog.py` consequently contains only identity, repository, language/discipline, collection index, ref, and TF path. `ContextFabricService._resource_dict()` reduces it further to:

```python
{
    "id": resource.id,
    "name": resource.name,
    "kind": resource.kind,
    "repository": resource.repository,
    "languages": list(resource.languages),
    "disciplines": list(resource.disciplines),
    "member_index": resource.member_index,
}
```

As a result, an agent calling `describe_available_corpus("TLHdig-TF")` cannot discover from the tool response that the corpus is Experimental or that known data-quality warnings exist.

This undermines Agora's stated separation between plugin operational status and resource scholarly quality at exactly the point where a downstream model needs that information.

**Recommendation:** carry verification, licenses, known issues, provenance, description, and resolved source revision into the runtime catalog and expose them through `describe_available_corpus` and load/prepare responses.

### 3. High — unpinned Context-Fabric resources silently freeze at the version first cloned on a machine

`GitStore.ensure_metadata()` clones a repository once. On subsequent calls, `_select()` only fetches from upstream when a `ref` is explicitly configured:

```python
if ref:
    git fetch ... ref
    selected = FETCH_HEAD
else:
    selected = rev-parse HEAD
```

For ordinary unpinned resources, the cached clone's existing `HEAD` is reused indefinitely. No fetch of the current default branch occurs.

This means two machines can resolve the same Agora resource to different commits depending on when their caches were first created. It also means a user can believe they are loading the current upstream corpus while actually using an old cached snapshot.

The test `test_unpinned_metadata_uses_current_default_branch` only validates the initial clone. It does not test the important sequence:

1. clone upstream;
2. upstream advances;
3. call `ensure_metadata()` again;
4. verify whether the selected source updates.

**Recommendation:** define explicit source semantics. Either pin release resources to commits for reproducibility, or fetch/update floating resources according to a documented refresh policy. In both cases, expose the resolved Git SHA in prepare/load results.

### 4. High — the canonical registry is not actually the source of truth for plugin launch integration

`scripts/generate_marketplaces.py` contains hard-coded integration constants and per-plugin branches, including:

- `perseus-mcp==1.0.2`;
- the Sefaria SSE endpoint;
- `mcp-proxy==0.12.0`;
- the MCP SDK compatibility constraint;
- explicit `if plugin_id == ...` launch definitions for Context-Fabric, Perseus, Sefaria, and SEDRA.

This means adding plugin #5 necessarily requires modifying the central generator. The registry's runtime fields are descriptive rather than executable.

That conflicts with the intended marketplace contribution model where a straightforward third-party integration should mostly consist of canonical metadata, a launch adapter, scholarly guidance, and tests.

**Recommendation:** define a validated canonical launch/adapter model. Claude and Codex generators should transform that model rather than encode knowledge that “Perseus means this exact `uvx` invocation” or “Sefaria requires this particular proxy.”

The fixed assertions for exactly four plugins and 36 v0.1 resources are reasonable as a release-scope check, but should remain scoped to the release contract rather than become a permanent architectural limit.

### 5. High — collection member `author` and `title` metadata is incorrect for real Greek repository paths

`ContextFabricResolver._collection_members_from_roots()` derives metadata using path position:

```python
parts = PurePosixPath(identity).parts
author = parts[0] if len(parts) > 1 else None
title = parts[-1] if parts else identity
```

The newly added Iliad smoke-test path is:

```text
canonical-greekLit/tlg0012/tlg001/perseus-grc2/1/tf/1.0
```

After removing the `/tf/...` suffix, the current heuristic yields roughly:

```text
author = canonical-greekLit
title  = 1
```

Those values are exposed to MCP clients as actual author/title metadata and are included in collection search.

The unit tests hide this problem by using synthetic paths such as `Homer/Iliad/tf/2.0`.

**Recommendation:** do not infer semantic metadata from arbitrary path positions. For PTHU/Perseus collections, derive work identity from CTS/catalog metadata or a generated enriched member index. Until such enrichment exists, return neutral path-derived fields instead of calling them `author` and `title`.

### 6. High/Medium — collection indexes are declared but not used as the runtime discovery layer

Collection resources declare:

```yaml
collection:
  discovery: indexed
  member_index: registry/collections/...
```

but the committed indexes for `bible`, `patristics`, `greek_literature`, and `translatin-manif` are still `pending` and contain empty `members` arrays.

The runtime does not consult those member indexes. `list_members()` scans the Git tree dynamically using `dataset_roots()`, and `prepare()` reconstructs the member mapping again.

For `greek_literature`, this means repeatedly working over a repository containing around 1,779 Text-Fabric roots.

This is acceptable for proving the concept, but the architecture currently claims an indexed collection model without actually using one.

**Recommendation:** choose one model. A strong option is to generate collection indexes tied to a resolved upstream commit SHA, enrich them with real work/author identifiers, and refresh them only when the selected upstream revision changes.

### 7. Medium — “Verified” conflates different clients/transports, and canonical status documents contradict each other

`registry/plugins.yaml` marks all four plugins `verified`.

`registry/providers.yaml`, however, marks all four providers `experimental`, and the Context-Fabric provider still says:

```text
Provider runtime has not yet been implemented in Agora.
```

The registry validator accepts this because it validates each status value independently but does not enforce cross-document consistency.

There is a second issue: the live smoke harness reads only each plugin's `.codex-plugin/mcp.json`. It therefore validates the Codex stdio integration path, not the Claude path.

For Sefaria those are materially different:

- Claude connects directly to the hosted SSE endpoint;
- Codex starts a local `mcp-proxy` bridge and talks stdio.

One plugin-level `verified` bit therefore covers multiple integration paths for which the evidence is not equivalent.

**Recommendation:** model verification as evidence records such as:

```text
plugin × client × transport × test × source revision × last-success
```

and derive aggregate labels from those records. Also remove stale provider-status text or make provider/plugin semantics explicit enough that the apparently contradictory statuses are intentional and machine-checkable.

### 8. Medium — Git cache operations assume serialized access, but MCP requests may be concurrent

Each resource uses one mutable cached clone. `ensure_metadata()` mutates `refs/agora/selected`, and `materialize()` performs a path checkout into the same working tree.

There is no file/process/thread locking around these mutations.

Parallel calls can therefore contend on the Git index/working tree or change the selected ref while another operation is using it.

**Recommendation:** minimally add a per-repository filesystem lock. A cleaner long-term approach would use an object/bare repository cache plus immutable worktrees/materializations addressed by commit + dataset path.

### 9. Medium — dependency pinning is insufficient for reproducible “Verified” installations

Context-Fabric pins `cfabric-mcp==0.1.7`, while its remaining environment is still dynamically resolved. SEDRA permits any `fastmcp>=2.12,<3`. Perseus pins the top-level package but still depends on the transitive environment resolved by `uvx` at execution time.

There are no committed lockfiles for the Agora-owned plugin projects.

The Sefaria integration has already demonstrated the failure mode: an unbounded transitive MCP SDK update broke `mcp-proxy`, requiring an explicit compatibility constraint.

**Recommendation:** lock dependency environments for Agora-owned local runtimes and record the dependency set used for verification. For third-party `uvx` integrations, consider lock/constraint support or at minimum record the resolved environment in verification evidence.

### 10. Medium — manually enabled Context-Fabric HTTP/SSE transports bind to all interfaces by default

`server.py` uses:

```python
--host 0.0.0.0
```

as the default for SSE/HTTP modes.

The generated marketplace configurations use stdio, so normal installs are not exposed. But a user manually starting `--http` or `--sse` receives a network-visible service unless they explicitly change the host.

There is no Agora authentication layer around those transports.

**Recommendation:** default to `127.0.0.1`; require an explicit host override for external exposure.

### 11. Medium — CI is useful, but narrower than the README's verification language suggests

The Foundation workflow does several good things:

- schema validation;
- deterministic generated-artifact freshness checks;
- registry/runtime-catalog consistency checks;
- unit tests.

The scheduled live smoke workflow also starts all four Codex integrations and performs representative operations.

However:

- current local runtime CI is Ubuntu/Python 3.13 only;
- Claude launch configurations are not live-tested;
- the normal Context-Fabric MCP smoke only performs catalog discovery, not corpus acquisition/load;
- the newly attempted representative Context-Fabric load suite is currently incomplete and breaks `main`;
- there is no Windows/macOS integration matrix despite the cross-platform positioning.

**Recommendation:** phrase verification claims at the actual evidence granularity and add platform/client matrices where stronger claims are desired.

## Unfinished work

There is substantial unfinished work beyond the accidentally missing smoke-test script.

The project plan itself still identifies the following resource/member verification work:

- real corpus acquisition/materialization;
- actual Context-Fabric loadability;
- representative text and feature access;
- source-specific feature expectations;
- license/provenance completeness;
- known-issue enforcement;
- member-level verification for large collections;
- machine-readable mapping between verification claims and the checks that justify them.

Other unfinished areas visible in the repository include:

- collection member indexes are still pending/empty;
- many resource data licenses remain `unknown`;
- optional profiles are still placeholders;
- broader corpus-specific scholarly skills are ongoing;
- Antigravity support is intentionally deferred;
- documentation has drifted relative to implementation.

Examples of documentation drift:

- `wiki/plan.md` still describes Phase 5 as the next major implementation phase although several skills are already implemented;
- `wiki/v0.1-scope.md` says TLHdig-TF's TF path/version was not pinned in Phase 1, while the current registry now pins commit `5d5e9af248566222738f8ac65ab8f9bb1b6aed3c` and `tf/0.1.0`.

## Architectural choices worth preserving

### Provider/resource separation

Keeping Context-Fabric as one provider plugin with many resources is the correct abstraction. Large PTHU repositories should remain collection resources, with individual works discoverable/loadable beneath them rather than becoming thousands of marketplace plugins.

### Upstream-first integration

Perseus and Sefaria are integrated without unnecessary forks or vendoring. That reduces maintenance burden and keeps ownership boundaries clear.

### Lazy Git-backed materialization

The partial-clone / metadata-first / materialize-on-demand strategy is a good basis for large corpora. The problems are refresh semantics, concurrent mutation, collection indexing, and provenance of the selected source revision rather than the underlying decision to use Git metadata.

### Separating plugin health from scholarly-data quality

The conceptual distinction is correct and should remain. The implementation needs to carry resource quality/status metadata all the way into runtime responses and derive verification claims from explicit evidence.

## Recommended priority order

1. Repair the red `main` branch and require CI before merge/push.
2. Expose verification, licensing, known issues, and provenance through the Context-Fabric runtime.
3. Fix unpinned Git refresh semantics and expose resolved source SHAs.
4. Replace Greek collection path heuristics with real indexed scholarly metadata.
5. Make plugin launch adapters declarative rather than hard-coded in the marketplace generator.
6. Derive verification from client/transport-specific evidence rather than one manually maintained plugin bit.
7. Add Git-cache locking/concurrency tests and lock Agora-owned runtime dependencies.
8. Expand representative corpus materialization/load tests and cross-platform/client verification.
9. Finish member indexes, license metadata, profiles, and remaining source-specific scholarly guidance.

After the first six items, the architecture would be considerably more defensible as a marketplace foundation rather than a strong prototype with several trust-layer shortcuts.
