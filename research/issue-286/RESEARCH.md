# #286 Research — released CTC-TF Burns producer for Agora

## Verified immutable identities (2026-10-12)

- CTC-TF released public stable `v0.3.0` at 2026-10-12T12:19:33Z, Git ref `refs/tags/v0.3.0` is a **direct commit** `ed6c7059803ff1adee057f5bd94d3ca661aac187` and the non-draft, non-prerelease GitHub Release independently reports the same target. Zero release attachments.
- Agora currently registers `cuc-burns`, `cuc-burns-csv`, Python-project installer requiring `explicit-code-execution`, user-local Workbooks CSV input, network-denied sandbox, CUC parent 0.2.8, at pre-release `f58b162197ad8f113b7cd6fc0088ae5dd39a096d`, `version: 0.3.0`, `release_tracking: {mode: disabled}`.
- Compared old and released upstream `agora.materializer.json` blobs: **identical blob SHA `e454c495d7d664ef1b7975f7d59c36a46b6a3a9d`** (same `plugin.id/name/repository/version`, same single `cuc-burns-csv`, same user-local acquisition, `{parent}` separate input, `network: deny`, feature-module output with CUC 0.2.8). This is not permission to skip runtime-change review: CTC-TF difference includes reviewed CI/release controls and real Agora parent provenance checks.
- Read Agora `registry/materializer-release-tracking.md`: `mode: github-releases`, `channel: stable`, `tag_prefix: v` passively discovers strict stable SemVer and only proposes immutable pinned commits via a **review PR**. It neither installs nor auto-approves third-party code.
- Existing real user-facing reusable workflow `.github/workflows/ctc-burns-registered-e2e.yml` checks out old exact CTC revision twice; `tests/test_ctc_burns_registered_237.py` and `tests/test_ctc_burns_registered_smoke_237.py` hard-code that same pin. These must move together with the registry to avoid false green and ensure actual pinned source is used.

## Scope, validation and risks

Make a narrow release identity update, not a new dependency manager: registry SHA/stable tracking, two CI checkout assertions and tests. Preserve licensed Burns data runner-local, CUC read-only parent, network-denied OS sandbox, explicit third-party installation approval, composition on existing CUC nodes. Verify Python/registry/generator gates and existing real 45-Workbook Agora→Text-Fabric→Context-Fabric MCP user-facing smoke at final PR head. Source-level TDD RED must be preserved before the GREEN change. An upstream stable tag is mutable metadata, but runtime pin remains immutable SHA and updater verifies its identity before proposing future changes.
