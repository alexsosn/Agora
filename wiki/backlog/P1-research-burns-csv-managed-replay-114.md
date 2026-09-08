# Research: exact managed replay evidence for Burns CSV cacheability (#114)

## Question

What exact upstream commit and Agora managed execution identity should be replayed before `burns-workbooks-csv-text-fabric` may receive a `reusable` cacheability attestation, and what evidence must be produced without redistributing Burns-derived data?

## Baseline inspected

- Agora `main`: `c875cc388984774ae015784f4fc49b6127c129b3`.
- #103 trusted cacheability authorization is still in implementation/review and is a prerequisite for promotion.
- Current canonical registration:
  - plugin: `ugarit-context-parsing`;
  - repository: `alexsosn/ugarit-context-parsing`;
  - ref: `e1218b88d9d849c58ee25541339f32b0d8f5a7d3`;
  - version: `0.2.0`;
  - release tracking: disabled;
  - materializers: Burns CSV and Burns PDF.
- Current registered-install smoke:
  - Ubuntu hosted runner;
  - Python 3.12;
  - explicit managed installation through Agora;
  - receipt contains `execution_identity_sha256`;
  - real bubblewrap sandbox;
  - one synthetic CSV materialization and semantic spot checks;
  - no second execution and no whole-artifact semantic replay comparison.

## Upstream evidence comparison

Compared current Agora pin `e1218b88…` with upstream `f0c4e666fa9783b455ef3cc1b86238f41bb6e8b6`.

The newer commit is exactly two commits ahead. The diff changes:

- upstream CI evidence recording;
- research/plan/review documentation;
- repeated semantic-determinism tests;
- `src/ugarit_context_parsing/_semantic_compare.py`, a private packaged semantic comparator.

It does **not** modify the converter core modules (`cli.py`, `source.py`, `pdf_source.py`, `graph.py`, `report.py`, `writer.py`, identifier logic, or the materializer manifest). The scholarly conversion behavior therefore has no production-code delta across this compare, but the source tree and installed runtime identities are still different and must not be treated as interchangeable for cache authorization.

## Why the newer commit is the better replay target

Repin the evidence candidate to `f0c4e666fa9783b455ef3cc1b86238f41bb6e8b6` rather than attesting the older `e1218b88…` registration.

Reasons:

1. **Exact evidence lives with the exact plugin commit.** The managed runtime will contain the same private semantic comparator that upstream tests exercise.
2. **No cross-commit equivalence exception is needed.** Even though the converter core is unchanged, #103 intentionally requires exact commit identity. Replaying `e1218b88…` and citing tests from a descendant would weaken that rule.
3. **The comparator is packaged, not an Agora reimplementation.** Agora can invoke the upstream comparator from the installed managed runtime after two executions, reducing the chance that Agora silently defines a different scholarly equality contract.
4. **The execution identity correctly changes.** Adding the comparator changes the installed environment tree, so a new `execution_identity_sha256` is expected and should be the identity reviewed.
5. **The registry remains immutable/ref-bound.** A deliberate one-time repin is easier to audit than claiming semantic equivalence between distinct refs.

The repin itself is not cacheability evidence. It must be reviewed and exercised through the normal passive-fetch, explicit-install, sandbox, and replay gates before a reusable attestation is committed.

## Comparator semantics at `f0c4e666…`

`ugarit_context_parsing._semantic_compare.compare_text_fabric_artifacts(left, right)` fails closed over:

- required `otype.tf`, `oslots.tf`, `otext.tf`, and `conversion-report.json`;
- the complete generated top-level `.tf` filename set;
- exact UTF-8 `.tf` content after removing only the generated `@dateWritten=` line, requiring exactly one such line per TF file;
- complete parsed `conversion-report.json` equality;
- independent real Text-Fabric loads of both artifacts;
- max slot/node bounds and complete node-type sequence;
- complete node-feature inventory and every node-feature value;
- complete edge-feature inventory and every edge target/value;
- section navigation for every structural node.

The upstream comparator does not ignore arbitrary paths, feature metadata, report fields, unknown future `.tf` files, whitespace, or scholarly values. Upstream tests include a scholarly negative control so a comparator that only checks file/count shape cannot satisfy the evidence.

Agora's `agora-materialization.json` is deliberately outside that upstream comparator. It contains run-specific Agora provenance and must not be mistaken for converter semantic output. Replay evidence should separately validate that both provenance documents bind the same plugin/materializer/source content/execution identity while permitting only explicitly identified run-instance fields to differ.

## Managed execution identity boundary

Agora installation receipt schema v2 computes `execution_identity_sha256` from:

- exact fetched source tree hash;
- exact managed environment tree hash;
- current Python/runtime/platform identity.

Environment integrity additionally binds distributions, pip report, source/execution manifest hashes, environment marker and runtime descriptor. Therefore the replay attestation is valid only for the exact identity produced by the candidate installation. Dependency resolution, Python patch/runtime, architecture, OS/platform, source ref, or installed tree drift yields a different identity and must disable reuse until separately replayed/reviewed.

The first promotion should attest only the Ubuntu/Python-3.12 managed identity actually replayed by CI. Other platforms/runtimes remain executable but non-memoized until they receive their own evidence.

## Evidence workflow requirements

A promotion workflow/test must:

1. use only synthetic Burns CSV input already legal for CI;
2. passively fetch and explicitly install the exact candidate ref through Agora's normal installer;
3. record the verified receipt `execution_identity_sha256` in the job log/evidence output;
4. create the synthetic source once and execute the registered CSV materializer twice into two fresh output directories under the same managed runtime and real bubblewrap sandbox;
5. invoke the comparator from the installed `ugarit-context-parsing` runtime, not from Agora source;
6. require semantic equality of the two converter outputs;
7. perform a negative control on a disposable copy by changing one scholarly feature and require comparator inequality;
8. validate Agora provenance separately, allowing only explicitly run-specific fields to differ;
9. never upload the source or generated TF artifacts as workflow artifacts;
10. expose only compact non-restricted evidence: exact plugin ref, execution identity, comparator target/version identity, pass/fail, and hashes/metadata that do not contain Burns-derived content.

## Two-stage promotion is necessary

The reviewed execution identity is not known until the exact candidate is installed under the target CI runtime. The registry reusable entry, however, must contain that exact identity. Avoid hard-coding a guessed digest.

Use two immutable stages:

### Stage A — candidate repin + replay evidence

- RED contract requires the canonical Burns ref to become the reviewed candidate and the workflow to run two sandboxed executions with negative-tested semantic comparison.
- GREEN repins to `f0c4e666…` and adds the replay evidence lane, **without** a `reusable` cacheability entry.
- Exact-head CI records the actual managed `execution_identity_sha256`.
- Independent review verifies the repin and evidence semantics.

At this stage direct execution remains allowed and reuse remains denied because cacheability metadata is absent.

### Stage B — exact identity attestation

- RED test freezes the exact identity observed in Stage A and requires CSV `reusable` metadata bound to `f0c4e666…`, that identity, and the stable replay evidence target.
- GREEN adds only the registry attestation/evidence metadata.
- Registry validation, install smoke, replay, and trusted #103 authorization must all pass on the exact head.
- A negative policy test must prove another identity/ref is denied.

This avoids circularly needing a registry attestation before the managed identity can be measured.

## PDF and Pseudepigrapha boundaries

- Burns PDF is not promoted here. Upstream tracks real-parser PDF determinism independently; absent equivalent exact managed replay it remains unknown/reuse denied.
- Pseudepigrapha is not promoted by analogy. It remains executable with absent/unknown cacheability until its own evidence exists.

## License/privacy

Burns source and derived TF remain local-only under the registered CC BY-NC-ND 2.5 boundary. CI uses synthetic data only. Replay directories live under runner temporary storage and are never uploaded. Evidence artifacts/logs must not contain local user paths/basenames or actual Burns-derived content.

## Risks to challenge in plan/review

- upstream comparator accidentally imported from repository checkout instead of the installed managed runtime;
- `@dateWritten` or Agora run provenance exclusions widening into a generic ignore list;
- comparing only selected features rather than the complete persisted/loaded scholarly surface;
- a negative control that mutates an unobserved field and therefore proves nothing;
- replay executions using different runtime/installations rather than one verified execution identity;
- registry attestation digest copied from a different run/platform;
- repin changing materializer IDs/version/manifest semantics unnoticed;
- workflow artifact upload leaking source or generated TF;
- PDF accidentally inheriting CSV evidence;
- a dependency change after evidence silently retaining reuse authority.

## Post-review correction: #111 is a prerequisite for attested identity

A later independent review found that the schema-v2 execution identity described above is not yet proven reproducible across two equivalent clean installations. Agora installs local projects through a randomly named `agora-materializer-build-*` source directory, while pip is expected to preserve local-origin path metadata inside the managed runtime. Because schema v2 hashes the raw runtime tree into `execution_identity_sha256`, a digest observed in one ephemeral CI installation may be a one-off installation identity rather than a reproducible execution-environment identity.

That changes the dependency graph for #114:

- the **semantic** decision to use `ugarit-context-parsing@f0c4e666…` and its packaged comparator remains valid;
- no schema-v2 digest may be promoted into `cacheability.reviewed_environments` merely because one replay run printed it;
- #111 must first land a reviewed receipt/execution-identity contract that proves equivalent clean installations on one runtime/platform produce the same canonical execution identity while retaining raw full-tree tamper detection;
- Burns Stage A must then install the exact candidate under that new contract and demonstrate the canonical identity is reproducible across at least two fresh equivalent managed installs in the target Ubuntu/Python cell, not only stable across two executions from one installation;
- only one of those verified installations needs to perform the expensive two-run scholarly replay, provided both fresh installs are shown to share the same canonical identity and exact source/dependency/runtime closure;
- Stage B may freeze only the new reproducible identity. Historical v2 identities are evidence/debug data, not reusable authority.

The exact receipt schema number is intentionally not hard-coded here; #111 owns that migration decision. #114 consumes whatever reviewed reproducible identity contract #111 lands.

## Revised conclusion

The correct semantic replay target remains `ugarit-context-parsing@f0c4e666fa9783b455ef3cc1b86238f41bb6e8b6`, and promotion remains two-stage. However, #114 is now blocked on **both #103 and #111** before any managed identity can be attested. Stage A must use the post-#111 reproducible identity contract, prove equivalent fresh installs reproduce that identity, and then produce exact negative-tested semantic replay evidence. Only a later immutable Stage B commit may bind that canonical identity into `reusable` registry metadata.
