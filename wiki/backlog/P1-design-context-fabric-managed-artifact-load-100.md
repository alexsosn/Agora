# Plan: load verified managed artifacts in Context-Fabric (#100)

## Goal

Let the installed Agora Context-Fabric plugin describe, load, query and unload a #99 managed Text-Fabric artifact through an Agora artifact ID while preserving these boundaries:

- public callers never supply a filesystem path;
- the canonical resource catalog is unchanged;
- the plugin independently verifies the versioned #99 receipt/payload contract before dereferencing data;
- a shared artifact-use lease protects the payload for the entire loaded lifetime;
- Context-Fabric owns only `.cfm/` consumer state and uses an artifact-ID compile lock for it;
- existing cold-load supervision, loader semantics, cancellation and canonical resource behavior are reused rather than forked;
- public provenance is useful but path/private-source safe.

Research: `P1-research-context-fabric-managed-artifact-load-100.md`.

## Preconditions and dependency boundary

1. #99's managed-artifact format/store contract must be merged before #100 production code lands.
2. The normative #99 use-lease amendment is required: shared use lease for active consumers, exclusive use lock for removal, separate artifact-ID compile lock for `.cfm` mutation.
3. #100 does not require any real materializer to be reusable. A synthetic/one-shot #99 artifact is sufficient for the first complete user path.
4. #100 must re-read the final merged #99 receipt schema, payload manifest, ID syntax, store-root convention and lock API before RED1. If those differ from this plan, update the plan before tests.
5. No production/test implementation begins on this research branch. Implementation starts from then-current `main` after the research/design gate is merged.

## Non-goals

- no materializer execution, install, fetch or repair;
- no request-key/cacheability decision;
- no fake canonical `ResourceSpec` or registry resource;
- no arbitrary local-path loading API;
- no automatic feature-module composition onto derived artifacts;
- no new generic package manager/shared PyPI package;
- no change to scholarly Text-Fabric semantics;
- no coupling of managed artifact bytes into canonical GitStore snapshot/overlay quota semantics.

# Slice 1 — packaged artifact consumer verification

## RED 1

Add tests first for a packaged `agora_context_fabric` managed-artifact consumer. Use #99's merged producer/store helper in repository-level test setup to create legally redistributable synthetic objects, but exercise the consumer through the Context-Fabric package import path.

Freeze at least:

### Artifact-ID and store-root trust

- only a syntactically valid #99 artifact ID is accepted;
- empty, separator-containing, traversal, absolute, overlong or otherwise invalid IDs fail before object-path access;
- store root is an internal constructor/configuration input, not part of the public descriptor/tool arguments;
- object/receipt/payload containment is re-established from root + validated ID;
- symlinked store/object/receipt/payload components fail closed according to #99's contract.

### Receipt/version contract

- one valid current #99 receipt is accepted;
- unsupported future/legacy receipt versions fail explicitly;
- unknown extra authority-bearing fields fail if #99's schema says they are forbidden;
- artifact ID, disposition, plugin/ref/version, materializer, output format, required paths, execution identity/cacheability disposition, source identity, payload digest/manifest and redistribution policy must match the object being consumed;
- consumer does not derive/recompute reusable request keys or cacheability authorization.

### Immutable payload

- every non-`.cfm` path/kind/hash required by the receipt/manifest is revalidated;
- missing, added, changed or file↔directory-swapped immutable payload entries fail;
- required output paths are present and contained;
- payload format must be supported Text-Fabric;
- symlinks fail closed;
- `.cfm/` may exist after publication and is excluded only exactly as the #99 contract permits;
- invalid immutable payload still fails when a valid-looking `.cfm/` tree exists.

### Privacy projection

- public descriptor includes artifact ID, creation disposition, producer plugin ID/ref/version, materializer ID, output format, privacy-bounded source identity/digest, execution identity/cacheability attestation/disposition if present, receipt/schema version and redistribution policy;
- conspicuous synthetic store/source absolute paths and user-local basenames are absent;
- internal payload path is never part of the public descriptor.

### Cross-contract drift

- a synthetic object emitted by the current #99 producer validator is accepted by the packaged consumer;
- focused mutations of every authority-bearing receipt/payload field are rejected;
- producer receipt-version change unsupported by the consumer fails until the consumer contract is deliberately updated.

Expected RED: no packaged managed-artifact consumer exists.

## GREEN 1

Add a small packaged module, conceptually `agora_context_fabric.managed_artifacts`, that owns only consumer-side functionality:

- validate artifact ID;
- resolve contained object/receipt/payload under an injected/default managed-artifact root;
- parse/validate supported receipt format;
- verify immutable payload manifest and required output contract;
- project path-safe public descriptor;
- return an internal validated descriptor containing the payload path only to trusted service code.

Do not import repository-level `scripts/`. Do not create/modify/delete artifacts and do not implement lock construction ad hoc if #99 exposes a packaged/runtime-neutral lock convention helper; otherwise consume the documented lock-file derivation exactly and cover it with cross-contract tests.

## Gate 1

- focused consumer tests;
- Foundation;
- plugin packaging/install/import test from outside Agora checkout;
- generated marketplace freshness if packaging metadata changes;
- independent adversarial review for path traversal, unsupported versions, privacy leaks, `.cfm` over-broad ignores and producer/consumer contract drift.

# Slice 2 — use lease and managed prepared-load descriptor

## RED 2

Freeze lifecycle before invoking Context-Fabric:

1. final authoritative validation occurs **after** acquiring a shared #99 artifact-use lease;
2. a destructive remover that wins before shared lease acquisition makes load fail/re-resolve rather than dereference a deleted object;
3. once shared use is held, exclusive removal cannot proceed until release;
4. validation failure after lease acquisition releases the new lease;
5. process death releases the OS-backed use lease;
6. two warm consumers may hold shared use leases concurrently;
7. logical name is deterministic from artifact ID and in a reserved namespace that cannot collide with canonical resource logical names;
8. managed descriptor does not pretend to have canonical `resource_id`, `member_id`, Git source revision or feature modules when those concepts do not apply;
9. catalog contents and resolver state are byte/semantically unchanged by describe/prepare/load of a managed artifact.

Expected RED: service has no managed-artifact handle/lifecycle path.

## GREEN 2

Introduce the smallest internal managed load descriptor/handle needed to share existing load machinery. Prefer an explicit sibling type over stuffing false values into `PreparedCorpus` if `PreparedCorpus`'s canonical-resource fields would become misleading.

A managed load handle should bind:

- validated artifact ID;
- reserved logical name;
- internal payload path;
- privacy-bounded provenance/descriptor;
- held shared use lease;
- output/receipt schema identity needed for status/error reporting.

No loader/cold compile call yet.

## Gate 2

Focused lifecycle tests + cross-process use-lease tests on supported platforms + Foundation. Independent review attacks validate→lease races, lease leaks and logical-name collisions.

# Slice 3 — common cold/warm load lifecycle

## RED 3

Use a small real synthetic Text-Fabric artifact compatible with `cfabric-mcp==0.1.7` and freeze:

### Warm load

- verified managed artifact passes `features` unchanged to `CorpusManager.load`;
- loader sees only the trusted internal payload path and reserved logical name;
- public result exposes artifact provenance but not internal path;
- shared use lease remains held after successful load;
- unload releases it only after loader unload completes according to tested failure semantics.

### Cold compile

- source TF byte budget uses immutable payload files, not unrelated store metadata;
- managed artifact uses #99 artifact-ID compile lock, never canonical `GitStore.compile_lock(path)`;
- shared use lease is already held while compile lock is acquired;
- a second compile for the same artifact is excluded while independent warm readers remain possible;
- after compile-lock acquisition, warm marker is rechecked before spawning worker;
- existing contained cold compiler, disk/time/free-space guardrails, current `.cfm` version marker, cancellation and cleanup rules are reused;
- `.cfm/` mutation does not alter #99 immutable payload identity;
- malformed/tampered immutable payload is rejected before compile even when `.cfm` exists.

### Failure/replacement lifecycle

- compile failure/timeout/budget/observation failure releases newly acquired use lease and leaves no newly installed loaded handle;
- loader failure releases new lease;
- reloading the same logical managed artifact acquires/validates a new lease, completes the replacement load, then releases the previous lease;
- failed replacement keeps previous loaded corpus and previous lease intact;
- repeated unload is idempotent;
- canonical resource load/reload/unload behavior remains unchanged.

### Modules

- managed artifact API does not accept/apply canonical `modules` in v1;
- no resolver/catalog feature-module path is entered during managed load.

Expected RED: existing load path only knows canonical prepared resources/leases and canonical compile lock provider.

## GREEN 3

Refactor the mature service lifecycle only enough to parameterize the object-specific pieces:

- prepared/load descriptor;
- lease provider;
- compile-lock provider;
- provenance/result projection.

Keep one common implementation for:

- cold/warm decision;
- compile budgets/timeouts;
- active load reservation/status/cancellation;
- contained compiler invocation;
- marker/cleanup validation;
- `loader.load`/replacement semantics;
- `unload`.

Avoid copying the full `load()` body into a managed variant. Canonical resource behavior remains the compatibility baseline.

## Gate 3

- focused managed lifecycle tests;
- real synthetic Text-Fabric load/query smoke;
- existing canonical Context-Fabric unit suite;
- representative canonical load smoke;
- Linux/macOS/Windows cache/lock lifecycle lanes relevant to the refactor;
- independent adversarial review of lease/compile ordering, cancellation and failed replacement.

# Slice 4 — public service/MCP surface

## RED 4

Freeze a separate, unambiguous public surface. Preferred names unless current conventions force an equivalent:

- `describe_managed_artifact(artifact_id)`;
- `load_managed_artifact(artifact_id, features=None, max_compile_gb=None, max_compile_minutes=None)`.

Existing `unload_corpus(logical_name)` remains the common unload path if the reserved managed logical-name contract is safe.

Require:

1. MCP registers the two new tools deliberately; existing exact-tool-set test is updated rather than bypassed;
2. neither tool accepts filesystem path, plugin root, source path, materializer install option or registry override;
3. descriptor/load result contains path-safe artifact provenance and stable logical name;
4. `features` and compile-limit arguments delegate unchanged;
5. invalid/tampered artifact fails before loader call;
6. existing `load_corpus(resource_id=...)` keeps exact canonical semantics and does not reinterpret artifact-looking IDs;
7. canonical `list_available_corpora`/catalog output does not include local managed artifacts;
8. cache/status reports loaded managed artifact identity without internal payload/store path;
9. no tool triggers materializer execution/fetch/install/repair.

Expected RED: service/MCP has no managed-artifact methods/tools.

## GREEN 4

Add service methods and MCP tools with concise docs. Update exported package surface only as needed. Keep artifact discovery local and explicit; do not blend it into canonical resource discovery.

## Gate 4

- Foundation;
- exact MCP tool registration tests;
- generated Claude/Codex manifests freshness;
- packaged startup checks on Linux/macOS/Windows if package/runtime surface changed;
- generic MCP smoke for tool discovery plus bounded managed-artifact operation where synthetic fixture setup is feasible;
- canonical client/plugin verification regressions.

# Slice 5 — documentation and operator lifecycle

## RED 5

Documentation contract tests, if existing repo style supports them, should require the user guide/reference to state:

- managed artifacts are local derived objects identified by Agora artifact ID, not canonical catalog resources;
- `describe/load_managed_artifact` never accepts arbitrary paths;
- immutable producer payload is receipt/hash verified while `.cfm/` is Context-Fabric-owned mutable consumer state;
- load holds a shared artifact-use lease; explicit removal refuses active artifacts;
- unload releases the lease;
- unknown/tampered artifacts are not silently repaired/deleted;
- no implicit materializer install/repair occurs;
- redistribution remains local-only where the receipt says so;
- current v1 does not auto-compose catalog feature modules onto managed artifacts.

## GREEN 5

Update Context-Fabric/managed-materialization docs and cross-link #99 lifecycle docs. Do not claim reusable cache hits for real converters unless separate #111/#114 evidence has actually landed.

# Final integration gate

Before finalizing #100:

1. integrate then-current `main`;
2. Foundation full suite;
3. #99 producer→packaged-consumer cross-contract tests;
4. real synthetic Text-Fabric managed artifact load/query/unload;
5. representative canonical Context-Fabric load smoke;
6. Linux/macOS/Windows use/compile-lock and plugin startup lanes affected by the change;
7. MCP exact-tool-set and generic launch/smoke tests;
8. tampered receipt/payload, symlink/path traversal and unsupported receipt-version regressions;
9. removal-during-load and compile/removal ordering regressions;
10. failed replacement-load lease regression;
11. prove catalog/runtime catalogs are unchanged except deliberate MCP capability/tool metadata if required;
12. prove no workflow uploads synthetic/local managed payloads unnecessarily and never uploads restricted Burns-derived data;
13. fresh logically independent adversarial review anchored to frozen exact head.

# Independent adversarial review checklist

Challenge the final patch for:

- public arbitrary-path or store-root injection;
- checkout-only import of repository `scripts/`;
- duplicate producer authority/request-key/cacheability logic inside the plugin;
- producer/consumer receipt-version drift accepted silently;
- validation completed before, rather than under, the shared use lease;
- removal between validation and load;
- loaded-but-not-compiling artifact lacking lease protection;
- use-lock/compile-lock/removal deadlock cycles;
- failed replacement releasing the old lease too early;
- new lease leaking on compile/loader failure or cancellation;
- process death producing permanent false in-use state;
- canonical resource logical-name collision;
- managed artifacts polluting `Catalog`/resource registry or canonical GitStore path authority;
- canonical feature modules silently applied to derived artifacts;
- `.cfm` being included in immutable artifact identity or, conversely, immutable payload being hidden under an over-broad `.cfm` exemption;
- internal store/source paths or basenames leaking through descriptor/status/errors;
- unsupported output/receipt formats being guessed rather than rejected;
- implicit plugin install/fetch/repair/materializer execution;
- canonical resource load/cold-compile semantics regressing during lifecycle refactor.

Every blocker gets a focused RED before correction.

# Definition of done

#100 is complete when a caller can name a valid Agora artifact ID, have the packaged Context-Fabric plugin independently verify the published #99 receipt and immutable Text-Fabric payload under a shared artifact-use lease, safely compile/load/query it with the existing supervised lifecycle and an artifact-ID compile lock, unload it cleanly, and receive useful path-safe provenance—without arbitrary-path trust, canonical catalog mutation, implicit materializer execution, or duplicated cacheability authority.
