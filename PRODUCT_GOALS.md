# Product goals — Agora

## Who the product serves

Philologists and scholars of Biblical, Semitic, Greek, Syriac, and Hittite texts who need to find and use existing scholarly corpora, lexica, and research services from an AI-assisted research environment. Agora is a thin plugin marketplace and integrator, not the scholarly data provider or a replacement for each plugin's native interface.

## Real researcher journeys

1. **Discover:** starting with a question about a language, text or corpus, determine which *existing* Agora plugin/resource supports it; distinguish current availability, client/platform support and known limitations.
2. **First success:** install only the needed plugin in a supported host and complete a representative operation using its public tool interface, without learning internal marketplace architecture.
3. **Corpus research:** locate an actual registered Text-Fabric resource (for example BHSA), inspect its source-specific features, acquire/prepare/load it within documented resource limits, run a real query and recover the source identity.
4. **External-source research:** retrieve an attested passage or lexical/bibliographic record through Perseus, Sefaria, SEDRA or CAL as supported; preserve upstream links, identifiers, uncertainty and provider-specific capabilities rather than silently merging different services' semantics.
5. **Failure and recovery:** understand why installation, client compatibility, source acquisition, resource loading or a query failed; avoid false success, unbounded downloads, data loss and hidden expensive operations.
6. **Reproducibility:** identify the plugin version, source/resource version, required client, actual operation and relevant upstream caveats supporting a research result.

## Minimum useful release and acceptance

A new researcher can go from a real question to a justified plugin choice, a documented supported installation, one independently checked live or real-data operation, source attribution and clear limitations. Test several representative journeys on *actual supported clients*, not only Python internals or generated-manifest equality. Distinguish verified client integration from scholarly suitability and upstream data quality.

The published v1.0 marketplace baseline and prospective v1.1 additions must not be conflated. Claims about CAL or any added resource/plugin must match the actual published registry and client verification. Do not block an otherwise usable release on optional integrations, Rust migrations, generalized package management or perfection of every provider.

## Current product focus

- Correct first-researcher discovery, installation and comprehension (the documented user journeys in #163).
- Honest version/compatibility documentation and source identity, including preventing a recurrence of documented Pseudepigrapha registry/guide drift (#304).
- Successful bounded use of current plugins and real corpus/source-backed smoke tests; repair real broken paths.
- Add new converters, materializers and corpora only after their upstream release/use path is ready. Avoid duplicate providers for equivalent functionality.

## Ownership and non-goals

Agora owns registry/discovery, install/launch, trusted transport/configuration adaptation, compatibility/verification claims, bounded acquisition/resource selection, and marketplace UX. Each upstream plugin owns its domain-specific tools, source parsing, linguistic semantics, query implementation and scholarly interpretations. Fix upstream problems upstream, and adjust Agora's claims or compatible pins rather than shadowing the upstream implementation.

Do not introduce a generic database adapter, another MCP server, source-specific workaround, new resource manager, new certification protocol, or duplicated CI framework unless an observed Agora-owned researcher workflow cannot be made to work using existing facilities.

## Autonomous-development decision rules

Before choosing an issue, read this file, `AGENTS.md`, and `docs/agentic-development-policy.md`. Choose work by actual researcher outcomes, not issue count, ease of writing tests, or theoretical hardening. Prefer completing active PRs and honest releases. Require a specific user blocker and minimal reuse-first fix for internal infrastructure work. Keep research, planning, tests and logically independent adversarial review proportional to actual risk.

If two successive cycles do not advance a researcher journey or remove a reproduced blocker, challenge the approach and stop expanding the backlog. A useful, honestly scoped release is a successful stopping point.
