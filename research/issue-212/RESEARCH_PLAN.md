# Agora #212 — immutable Coptic sparse materializer registry pin

## Research and real evidence (2026-10-10)

- Agora #210 merged `39c18b43ead861e614daf8b2bb8f452a551de7c6`: manifest schema and Git acquisition support explicit immutable `sparse_patterns`. Real GitHub Actions job 114185713348 acquired and verified precisely 565 TT blobs/220,289,125 raw bytes at upstream `CopticScriptorium/corpora@3ac067f1709a0012daf39ea8da2fac79980176a5`, with no missing or unrelated files. Runtime ~15m30s of 20m job.
- CopticScriptorium-TF PR #68 merged `60fec735dd6ef9aefe2cfb9e6459e9f7f15924e7`; its manifest declares the same upstream immutable Git revision and only `/*/*_TT/**`, `/*/*_TT.zip`. Actual Coptic CI run 38046870176/job 114198061253 acquired a real Thomas TT blob via Agora, produced 6,521 native TF word slots under network-denied Bubblewrap and reloaded the resulting native TF. Direct- and ZIP-source fixtures validated separately.
- Agora main registry currently still pins old Coptic `ca0ee11bec734858628b2a237c11acb463a63863` without sparse patterns. The registry's registered synthetic Coptic materialization and Context-Fabric install/prepare/load/query/unload/remove workflow already passed with that **old** pin.

## RED → plan → implementation → test → independent review

1. Change offline immutable registry test expectation to the newly merged Coptic commit and require the **installed manifest** validation assertions for actual upstream Git SHA and sparse patterns in `.github/workflows/materializer-install.yml`. This intentionally fails on unchanged production registry/workflow (RED).
2. Change only the Coptic registry ref, keep the same Python wheel explicit-code-execution approval, version, licenses, sandbox and required output.
3. Validate the actual installed manifest in the existing registered workflow; require pinned upstream SHA and sparse path selection in addition to the old ID, trust, and package checks. Preserve synthetic registered materialization and full Context-Fabric lifecycle.
4. Run all workflows on exact PR head; inspect actual logs, including install receipt and Context-Fabric query, not just status.
5. Independent adversarial code/data review before merge checks mutation surface, stale SHA hazards, source-revision identity, ZIP and directory pattern shape, untrusted user-source override, fail-closed download filter, real source completeness and output integrity.

## Boundaries and next research

This registry-pin PR alone does **not** prove full automatic 565-file source conversion under the registered plugin. Coptic #17 / Agora #205 remain open pending registered remote fetch → full corpus conversion → native TF ↔ Context-Fabric acceptance. Schedule and budgets require explicit investigation (Agora #211); do not weaken sandbox, silently reduce corpus, or relabel staged user-local source as verified Git acquisition.

## Acceptance gates

- [x] Independent upstream / host / Coptic manifest research
- [x] RED-first registry and workflow contract tests added
- [ ] Registry ref and actual installed manifest assertions implemented
- [ ] Exact-head CI success + checked logs
- [ ] Logically independent skeptical review on final head
- [ ] Merge with expected head SHA
