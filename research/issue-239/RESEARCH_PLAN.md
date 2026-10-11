# Issue #239 — explicit user-facing CLI for already approved CUC feature-module producer

## Research and trust boundary

Agora #135 and #220 expose `materialize_requested_feature_module` internally. It reads `acquisition.materializer` from the bundled Context-Fabric catalog, validates the exact immutable CUC parent/producer compatibility, verifies an already installed registered producer, uses a cache lease/read-only network-denied sandbox, and atomically publishes into the **existing** Context-Fabric local module store. #237/#238 registers the CTC-TF parent-bound Burns producer at `f58b162...`, but researchers need a supported entrypoint; there must not be any hidden producer installation or third-party code approval in corpus preparation.

The existing package installer supports passive `python scripts/agora_install_materializer.py fetch cuc-burns` followed by an **explicit** `python scripts/agora_install_materializer.py install cuc-burns --approve-code-execution`. The CTC source requires a user-controlled directory containing Burns Workbooks CSV grouped by workbook; no Burns PDF/CSV can be checked into Agora or redistributed.

## Plan and gates

1. Add **preserved RED** CLI contracts before the implementation: `python -m scripts.agora_compose_feature_module --module cuc-burns --source <dir>`; optional `--cache-dir`, `--install-root`, `--parent-version`. Reject `--resolver`, `--catalog`, `--parent-path`, `--trusted`, `--plugin`, `--materializer`, `--registry-path`, `--approve-code-execution` and arbitrary output destination. No unapproved package installation.
2. Resolve the plugin ID and materializer ID **only** from the bundled catalog entry for the requested module, then call the already reviewed `materialize_requested_feature_module` without copying any validation/lease/runtime logic. Preserve output receipt and native local module path; reject missing/unbound module before execution.
3. User-facing guide: exact separate fetch/approved-install commands, local licensed source prerequisite, single materialize command, resulting Context-Fabric `cuc+cuc-burns` composition, security/license limitations, no implicit download of Burns source. Do not claim ChatGPT web execution.
4. RED, GREEN and full exact-head tests; actual registered Burns CUC smoke from #238, independent adversarial code/data review, reconcile stack before merge. CLI cannot be marked ready if the CTC producer registration #238 is not itself final.

Out of scope: new CLI authorization model, interactive forms, arbitrary untrusted parent overrides, auto-install, release tracking, remote server or corpus redistributions.
