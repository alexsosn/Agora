# #292 researcher recovery for blocked Greek members — research and plan

## Research (2026-11-18)

Pinned `pthu/greek_literature@77d85bf71fc6f689f7faedc255666a2609ffe590` contains 59 collection members flagged `context-fabric/duplicate-structure-levels`. Agora `registry/resources.yaml` declares this issue `severity: blocking` at member scope; resolver `prepare` rejects flagged members before acquisition. Exact-head #302 reproduced that Argonautica's Greek words can load in Context-Fabric 0.5.8 while 94 card nodes lack the declared card parent level. Successful direct `loadAll` does not justify unblocking it. The 59 members span ten distinct source metadata signatures, documented on #292.

Current researcher-facing troubleshooting lists general cold loads and provider quirks, but no recovery path for this intentional safety rejection. A researcher encountering this error may interpret it as a network/installation failure and retry or delete caches, although neither fixes malformed structure.

Perseus/Scaife is an existing independently registered plugin for *passage retrieval and search*, with its own service/edition and legacy CTS navigation limitations. It does not supply equivalent Text-Fabric structured queries. A recovery page must preserve this distinction and refrain from asserting a particular Greek work/edition is exposed there without discovery.

## Plan and TDD gates

1. RED: add contract tests that require a symptom-to-recovery link, explicit fail-closed status, and a qualified non-equivalent Perseus alternative. Tie the example to actual registry `greek_literature` severity and source-derived member flag, rather than hard-coded prose-only assumptions.
2. GREEN: add one concise symptom section to `wiki/guides/troubleshooting.md`, link it from the Context-Fabric plugin page, and preserve the blocking guard and canonical registries unchanged.
3. Run focused tests locally or via exact PR CI. Review markdown links and semantic claims against live registry and `#292`/#302 evidence; require independent adversarial review before merge.
4. This is a bounded interim UX recovery, not resolution of #292. Full per-schema real-data navigation audit and selective unblocking remain open.

## Non-goals

No new adapter, no new corpus/provider, no ignored blocking error, no fabricated CTS references, no global severity downgrade, no claims of host-level E2E.