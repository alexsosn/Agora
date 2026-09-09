# Plan: managed local materialization artifact cache (#99)

## Goal

Add an Agora-owned private managed-artifact store that can:

- publish every approved registered materializer execution transactionally under a path-safe artifact ID;
- reuse an existing artifact by deterministic request identity **only** when the final #103 trusted cacheability authorization permits it;
- keep unknown/non-reusable materializers directly executable while publishing distinct one-shot artifacts;
- validate converter/host payload exactly while permitting only Context-Fabric's later `.cfm/` consumer state;
- expose a stable artifact-ID lock/descriptor seam for #100 without accepting arbitrary filesystem paths.

Research: `P1-research-managed-artifact-cache-99.md` plus the merged #97 composition design/amendments.

## Preconditions

- #95 registered runner is merged.
- #103 must be merged before production implementation starts. Tests may be drafted only after re-reading the final merged #103 contract.
- Existing explicit registered execution remains authoritative and must not gain implicit fetch/install/repair behavior.
- All CI materialization fixtures are synthetic; managed artifacts are local-only and never uploaded.

## Non-goals

- no Context-Fabric/cfabric-mcp loading in this ticket (#100);
- no canonical resource/catalog mutation;
- no widening `GitStore._managed_path()`;
- no generic claim that registered converters are deterministic;
- no automatic cross-cache LRU policy or counting managed artifacts inside Context-Fabric snapshot/overlay `cache_bytes`;
- no Burns/PDF cacheability promotion (#114 and upstream PDF evidence are separate).

## Slice 1 — pure identity and disposition contract

### RED 1

Add tests-only contracts for a small managed-artifact identity module/store model.

Freeze:

1. **Reusable request identity**
   - same canonical plugin registration, materializer, verified execution identity, #103 attestation, privacy-bounded source identity, manifest/materializer contract, output format, sandbox policy, options and host/key schema -> same request key;
   - source tree/resolved revision change -> different key;
   - plugin ref/repository/materializer/execution identity/attestation/manifest/options/output-format change -> different key;
   - cache root, absolute source path, local basename, output path and timestamps do not change key;
   - canonical mapping/list ordering is deterministic.

2. **Unknown/non-reusable disposition**
   - absent/unknown policy produces `reuse_allowed == false` and no reusable request-key lookup;
   - `non-reusable` likewise produces no lookup;
   - two identical one-shot requests receive different opaque artifact instance IDs;
   - byte equality is never promoted into a reusable disposition.

3. **Privacy**
   - seed conspicuous synthetic absolute paths/basenames and prove they are absent from the canonical request document and public descriptor fields.

4. **ID/path safety**
   - only store-generated/validated artifact IDs are accepted;
   - separators, traversal, absolute paths, empty/overlong IDs fail before filesystem access.

Expected RED: no managed-artifact identity/store module exists.

### GREEN 1

Implement pure/versioned identity helpers only. Suggested conceptual types:

- `SourceIdentity(type, tree_sha256, resolved_commit?)`;
- `CacheDisposition(mode, reuse_allowed, attestation_sha256?)` consuming #103 output;
- `ReusableRequestIdentity` canonical JSON + SHA-256;
- opaque `artifact_id` generator for one-shot artifacts;
- version constants for key/receipt/host contract.

Do not create directories, execute materializers or look up cache objects yet.

### Gate 1

- focused unit tests;
- Foundation;
- independent patch review of identity completeness, hidden environment inputs, privacy and accidental unknown reuse.

A blocker adds a focused RED before continuing.

## Slice 2 — private object layout, receipt and payload validation

### RED 2

Freeze a synthetic completed-object contract without converter execution.

#### Layout/modes

- store root/object/payload/staging are contained under the configured managed-artifact root;
- POSIX object/staging/payload directories are private; receipt files are private;
- store/object/payload/receipt symlinks and path escapes fail closed;
- receipt lives outside payload.

#### Payload manifest

At publication scan:

- materializer-produced top-level `.cfm` is rejected;
- every non-`.cfm` relative path is represented exactly once with normalized relative path and kind;
- files have SHA-256; directories are represented so unknown empty directories cannot appear silently;
- any symlink is rejected;
- required output paths must exist and be contained;
- `agora-materialization.json` is included in published integrity even though it is host-owned provenance.

Validate completed artifact:

- missing/modified manifested file fails;
- file<->directory kind change fails;
- unknown non-`.cfm` file or directory fails;
- required-path disappearance fails;
- top-level `.cfm/` may appear only after publication and all its descendants must remain contained/non-symlink;
- adding/removing/rebuilding `.cfm` leaves the canonical payload digest unchanged;
- payload tamper still fails when `.cfm` is present.

#### Receipt

Require receipt to bind:

- artifact ID and `reusable` vs `one-shot` creation disposition;
- request key only for reusable artifact;
- plugin id/repository/ref/version;
- materializer ID;
- actual verified execution identity;
- cacheability mode/attestation (or explicit fail-closed disposition);
- source identity without basename/path;
- manifest/materializer contract digest;
- output format + required paths;
- payload manifest/digest;
- required sandbox policy/backend observation;
- key/receipt/host schema versions;
- host `local-only` redistribution policy;
- optional created timestamp as non-identity observation.

Malformed/extra authority-bearing fields fail schema/semantic validation.

Expected RED: no store/receipt/payload validator exists.

### GREEN 2

Implement private filesystem store primitives:

- build canonical payload manifest;
- validate existing object by artifact ID;
- construct/validate immutable receipt;
- resolve internal payload path only after receipt/ID validation;
- public descriptor returns artifact/provenance identity without local paths/basenames;
- explicit remove-by-artifact-ID helper under an artifact mutation lock may be added now if needed by tests; no automatic pruning.

No materializer execution/reuse yet.

### Gate 2

Foundation + POSIX security tests + portable Windows path semantics where applicable. Adversarial review focuses symlink races, `.cfm` smuggling, unknown extra files and receipt/payload authority boundaries.

## Slice 3 — stable cross-process artifact lock namespace

This slice establishes both publication and later #100 compile-lock identity before execution orchestration.

### RED 3

Freeze:

- reusable publication lock key derives only from canonical request key;
- managed compile lock key derives only from validated artifact ID, never absolute payload path;
- same ID blocks across processes and process death releases lock;
- different IDs do not block one another;
- finite timeout produces actionable bounded failure;
- caller path spelling/cache-root relocation cannot choose/change compile lock identity;
- compile lock API refuses unvalidated artifact IDs;
- lock namespace is separate from installer lock and canonical Context-Fabric `GitStore.compile_lock`.

Also freeze ordering documentation/assertions: publication/validation finishes before #100 compile locking; no API holds a publication lock while waiting for a long compile lock.

Expected RED: no managed-artifact lock helper exists.

### GREEN 3

Use the repository's existing OS-backed lock dependency/conventions. Create small lock helpers scoped to the managed-artifact store. Do not modify canonical GitStore lock authority.

### Gate 3

Linux/macOS/Windows cross-process tests where the existing lock library supports them; process-death regression; independent lock-order review.

## Slice 4 — source-stability and registered execution consistency seam

### RED 4

Before cache/build orchestration, freeze the two TOCTOU boundaries discovered in research.

#### Source TOCTOU

- canonical user source identity computed before run;
- synthetic converter test mutates the host source while execution is active;
- post-run identity mismatch causes failure and no final artifact;
- unchanged source succeeds;
- resolved source revision is included when present/semantically observable;
- basename/path never becomes identity.

#### Authorization/execution TOCTOU

For a reusable cache miss:

- request key is derived from #103-authorized execution identity/attestation A;
- before converter execution the registered runner, while holding its existing runtime lock, re-verifies current installation/registry binding and actual receipt identity;
- if actual identity or effective attestation is B, execution/publish under key A is refused;
- registry/materializer removal/change while waiting fails closed;
- caller cannot supply an arbitrary identity to *authorize* reuse;
- direct unknown/non-reusable execution remains allowed;
- no fetch/install/repair is called.

The registered runner programmatic seam should expose/check only the minimum necessary consistency fields. A possible shape is an internal execution helper that accepts `expected_execution_identity` and `expected_attestation_sha256` strictly as equality assertions against freshly verified current state, then returns the actual values it used. These parameters are not a public authorization source or CLI surface.

Expected RED: existing registered runner has no cache-build consistency seam and source is not rehashed by a managed wrapper.

### GREEN 4

Extract/extend the minimum programmatic registered-runner seam. Preserve current CLI/direct function behavior. Do not rewrite sandbox construction or installation.

Add a canonical source-identity helper shared with managed orchestration so pre/post hashing semantics are identical.

### Gate 4

Foundation + registered install smoke + materialization sandbox E2E. Independent review tries explicit repair/pin/source races and confirms all mismatches fail before publication.

## Slice 5 — transactional one-shot managed publication

Implement non-reusable/unknown first so the core composition user path does not depend on reusable evidence.

### RED 5

Freeze end-to-end synthetic managed build where #103 returns unknown/non-reusable:

- execution really occurs on each identical request;
- each successful run gets a distinct artifact ID;
- artifact lives only in dedicated managed namespace;
- source stable before/after;
- required output/payload manifest/receipt valid;
- final publication is one same-filesystem atomic object-directory replace/rename from private staging;
- converter failure, source drift, reserved `.cfm`, invalid output, receipt failure leaves no final object;
- partial/staging directory is never returned as artifact;
- no implicit fetch/install/repair;
- public descriptor contains no absolute source/cache path or local basename;
- returned artifact can be re-opened/validated by ID without converter installation (explicit artifact load is distinct from request-key reuse authority).

Expected RED: no managed build orchestrator.

### GREEN 5

Wrap existing registered execution and host publication semantics rather than reimplementing converter/sandbox code. The managed store owns only outer object staging/receipt/publication.

For abandoned staging after crash: no final artifact is visible. Provide bounded explicit cleanup metadata/helper if necessary; do not perform recursive constructor/startup cleanup.

### Gate 5

Foundation + sandbox E2E + synthetic one-shot integration + filesystem failure tests + independent review.

At this point #100 can already load managed one-shot artifacts by ID once it is implemented; no reusable registration is required.

## Slice 6 — reusable lookup and concurrent build collapse

### RED 6

Use a synthetic registry/materializer with a test-only valid #103 reusable attestation/verified installation.

Freeze:

- current authorization is resolved before request-key lookup;
- absent/uninstalled/currently-unreviewed environment cannot reuse an old object by request key;
- same authorized request returns existing object only after receipt/payload validation;
- attestation/ref/execution/source/options/manifest drift changes key or denies reuse;
- malformed/tampered existing final object fails closed and is not silently deleted/repaired;
- concurrent equivalent cache misses acquire one request-key publish lock, execute once, publish one final object, and loser validates/returns winner;
- authorization and source identity are rechecked after waiting for publish lock;
- stale key after waiting is abandoned rather than used;
- winner failure exposes no final object and later caller may build cleanly;
- output byte equality alone never enables reuse for an unknown/non-reusable converter.

Expected RED: only one-shot managed build exists.

### GREEN 6

Implement deterministic reusable request lookup/build orchestration on top of previous slices.

Important order:

1. derive source identity;
2. get trusted #103 authorization;
3. if reusable derive key and acquire publish lock;
4. re-resolve authorization/source after lock;
5. validate/reuse existing winner, or execute with expected identity/attestation consistency checks;
6. rehash source;
7. construct payload manifest/receipt;
8. atomically publish;
9. release publication lock before any future #100 compile/load work.

No managed-artifact compile occurs in this ticket.

### Gate 6

Cross-process concurrency test + Foundation + registered install + sandbox E2E. Independent review focuses cache poisoning, lock order, policy drift, TOCTOU and accidental one-shot collapse.

## Slice 7 — store lifecycle/read APIs and documentation

### RED 7

Freeze internal/public programmatic surfaces needed by #100/#101:

- `describe/validate artifact_id` returns privacy-bounded descriptor and no filesystem path publicly;
- internal trusted resolver can return payload path only after receipt/payload validation;
- explicit remove-by-ID refuses active/busy lock state and cannot escape store;
- store status reports object count/bytes with truthful completeness without changing existing Context-Fabric `cache_bytes` semantics;
- access/created/size observations do not affect artifact identity;
- no automatic upload/redistribution path exists.

If a broad LRU/prune policy is desired, create a separate follow-up rather than adding unreviewed coupling to Context-Fabric's cache lifecycle here.

### GREEN 7

Implement only the minimal lifecycle/read seam and document:

- reusable vs one-shot semantics;
- exact #103 evidence requirement;
- local-only policy;
- `.cfm` ownership boundary;
- artifact ID vs filesystem path trust boundary;
- no implicit install/repair;
- how #100 should consume internal validated artifact resolver + compile lock helper.

## Final integration gate

Before finalization:

1. integrate current `main` and rerun exact-head gates;
2. Foundation full suite;
3. registered materializer install smoke;
4. real materialization sandbox E2E;
5. Linux/macOS/Windows lock/security lanes relevant to new store;
6. synthetic one-shot build + synthetic reusable concurrent build;
7. reserved `.cfm` and post-compile-style `.cfm` validation regressions;
8. source/runtime/registry TOCTOU regressions;
9. no workflow uploads managed payload/source fixtures;
10. fresh logically independent patch-only adversarial review anchored to the final SHA.

Final review must explicitly challenge:

- omitted request identity inputs / hidden time-random-environment dependencies;
- caller-controlled cacheability/execution identity;
- source mutation while converter runs;
- runtime repair/registry change between keying and execution;
- output-tree equality being mistaken for determinism evidence;
- unknown/non-reusable request collapse;
- receipt or payload symlink/path traversal;
- materializer-produced `.cfm` smuggling and generic hidden-file exemptions;
- unknown unmanifested additions after publication;
- publication/installer/compile lock cycles;
- invalid object silently repaired/replaced;
- basename/absolute path privacy leakage;
- Burns-derived bytes escaping through workflow artifacts/logs;
- accidental coupling to canonical Context-Fabric Git cache/catalog semantics.

Any blocker starts a focused RED→GREEN sub-loop before merge.

## Definition of done

#99 is done when Agora can return a validated, privacy-bounded artifact ID for every approved local materialization, transactionally and without implicit installation; unknown/non-reusable converters always produce distinct one-shot objects; only an exact #103-authorized request may hit a deterministic reusable key; payload integrity excludes only later `.cfm` consumer state; source/runtime/registry races fail before publication; and #100 receives a stable validated artifact-ID/path resolver plus artifact-ID compile-lock namespace without any canonical catalog/GitStore authority change.