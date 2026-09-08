# Design Burns Workbooks materializer registration (#87)

## Objective

Make the merged Burns Workbooks CSV/PDF → Text-Fabric converter discoverable and installable through Agora, and prove the registered CSV path with synthetic data where the existing host API permits it, without implementing automatic resource composition.

Research: [`P1-research-burns-workbooks-materializer-87.md`](P1-research-burns-workbooks-materializer-87.md).

## Immutable upstream identity

- repository: `alexsosn/ugarit-context-parsing`
- commit: `e1218b88d9d849c58ee25541339f32b0d8f5a7d3`
- version: `0.2.0`
- manifest: `agora.materializer.json`
- materializers:
  - `burns-workbooks-csv-text-fabric`
  - `burns-workbooks-pdf-text-fabric`

## TDD gates

### RED 1 — canonical registry contract

Before changing `registry/materializers.yaml`, extend `tests/test_materializer_installation.py` with an immutable Burns registration assertion covering:

- repository and exact 40-hex pin;
- version `0.2.0`;
- manifest path;
- both exact materializer IDs in upstream order;
- `package.type=python-project`;
- `install_trust=explicit-code-execution`;
- `release_tracking.mode=disabled` until an upstream stable GitHub release exists.

The test must fail because the canonical registry does not yet contain `ugarit-context-parsing`.

### GREEN 1 — registry entry

Add the smallest schema-valid entry to `registry/materializers.yaml`:

- immutable upstream pin;
- disabled release tracking;
- both materializer IDs;
- digital-philology/Ugaritic-relevant controlled disciplines only;
- software license `NOASSERTION`;
- data boundary describing Burns-derived local-only output;
- initial verification `experimental` until live install/materialization evidence passes.

Run canonical registry validation and focused registry tests.

### RED 2 — registered install/runtime smoke contract

Extend the registered-materializer workflow/assertions so Burns must:

- be discoverable by the installer;
- pass passive source/manifest validation before Python packaging executes;
- require explicit code-execution approval for installation;
- produce an installation receipt bound to the exact commit;
- install `ugarit-context-parsing==0.2.0` and Text-Fabric 13.x;
- expose both upstream materializer IDs from the installed manifest;
- import `ugarit_context_parsing.cli` and the packaged existing Workbook PDF parser from the managed runtime.

Where practical, add this assertion before the workflow implementation so the branch records the contract before the corresponding GREEN change.

### GREEN 2 — live install smoke

Add a dedicated Burns job (or a clear matrix case if it does not obscure converter-specific checks) to `.github/workflows/materializer-install.yml`. Do not weaken the Pseudepigrapha reference smoke.

### RED/GREEN 3 — synthetic sandboxed CSV materialization, if host API supports installed runtime directly

Research the current `agora_materialize.py` CLI/runtime invocation before coding. If an installed third-party runtime can be selected without inventing composition architecture:

1. create a synthetic `Section/Worksheet.csv` fixture during CI;
2. materialize it through the registered CSV materializer under the real Linux sandbox/network denial path;
3. require `otype.tf`, `oslots.tf`, `otext.tf`, `conversion-report.json`, and Agora provenance;
4. load/reopen the result with Text-Fabric from the installed runtime;
5. assert a synthetic headword and canonical `cuc_tablet` value;
6. do not upload the artifact.

If current APIs cannot bind the installed runtime to the materialization host without new architecture, document that exact boundary and stop at install/import smoke; do not smuggle automatic composition into this ticket.

## Test gates before finalization

- focused registry/materializer unit tests;
- `python scripts/validate_registry.py`;
- Foundation workflow;
- registered materializer install smoke;
- relevant materialization sandbox workflow if touched;
- exact-head CI only—no merge based on an earlier head.

## Independent adversarial review

Review the frozen final patch independently of implementation notes for:

- immutable source identity and version binding;
- passive-fetch vs code-execution trust boundary;
- manifest/materializer identity drift;
- runtime dependency/import correctness;
- synthetic-fixture-only licensing behavior;
- no Burns-derived artifact redistribution;
- no automatic composition overclaim;
- no regression to existing Pseudepigrapha materializer behavior;
- release-tracking truthfulness.

Every blocking review finding receives a new regression test first, then the minimal fix, full GREEN, and a fresh exact-head review.
