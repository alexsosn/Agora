# Research: Perseus CTS/Scaife contract health

Issue: #21

## Problem statement

Issue #21 reported that Agora's Perseus plugin can discover Euripides works and translations that cannot then be resolved through the CTS-oriented resource/navigation tools. The report also observed contradictory range/error behavior. A later audit clarified that some apparently missing works are available through Scaife rather than the legacy CTS inventory.

This research re-evaluates the issue against current Agora `main`, the pinned upstream release, and current upstream source before deciding what belongs in Agora.

## Current Agora integration

Agora launches the upstream package directly:

- repository: `tonyjurg/Perseus-mcp`
- pinned release: `perseus-mcp==1.0.2`
- Agora does not vendor or fork the server
- the current live Codex smoke initializes the packaged server, verifies representative tools, and calls `find_author_names("Homer")`

The plugin remains broadly functional: discovery, CTS passage retrieval, Scaife search/retrieval, and the current live smoke all work. This ticket therefore should not downgrade the whole integration to failed.

## Upstream release state

As of 2026-09-05, v1.0.2 is still the latest published upstream release. Upstream `main` is 13 commits ahead of v1.0.2, but those commits are documentation, CI, dependency-maintenance, and repository-governance changes; no later routing fix for this CTS/Scaife mismatch was identified.

The v1.0.2 release itself intentionally added merged CTS + Scaife author discovery.

## Source-grounded routing behavior

The upstream v1.0.2 source makes the mismatch explicit.

`find_author_names` resolves author entries by gathering both:

1. legacy CTS `GetCapabilities` data; and
2. the Scaife library catalog.

Those inventories are merged by text-group/work URN.

By contrast, `get_author_resources` and `get_work_resources` are implemented from CTS `GetCapabilities` only. They do not resolve Scaife-only works from the merged author-discovery result.

This explains the stable Euripides example from #21:

- `urn:cts:greekLit:tlg0006.tlg020` (Fragmenta) can appear in merged author discovery because it exists in Scaife;
- the CTS-only work-resource resolver can return no match for that work;
- Scaife exposes an edition for it (`...1st1K-grc1`).

Likewise, CTS and Scaife may expose different translation edition URNs. A failed CTS `perseus-eng1` request is not evidence that Scaife's distinct `perseus-eng2` translation is absent, and Agora must not invent an equivalence between them.

## Separate issue #24

Malformed legacy CTS metadata/navigation responses (`get_label`, valid-reference helpers, parsing of HTML/template errors, secondary logging failures) are already isolated in #24.

#21 should not duplicate or absorb that upstream defect. Its remaining concern is the merged-discovery → service-specific-resolution contract and how Agora represents/verifies that limitation.

## Agora-owned UX defect

The bundled `perseus-research` skill currently tells agents to:

1. call `find_author_names`;
2. inspect `get_author_resources` / `get_work_resources`;
3. treat the returned resources as the available editions/translations.

That sequence is incomplete because step 1 can contain Scaife-only works while steps 2–3 are CTS-only. An agent can therefore misreport a discovered work as unavailable instead of switching to Scaife metadata/passage tools.

This guidance is Agora-owned and should be corrected even though the underlying server behavior is upstream-owned.

## Machine-readable health gap

`registry/resources.yaml` already supports structured `verification.known_issues`, including advisory/blocking severity and upstream provenance. `registry/plugins.yaml` has no equivalent plugin-level field.

The #21 mismatch is a plugin/service contract issue, not a single corpus resource issue, so attaching it to an arbitrary resource would be misleading. Free-text `verification.notes` are insufficient for a retirement canary or downstream tooling.

A small generic plugin-level `verification.known_issues` field is therefore within Agora's marketplace/metadata scope.

## Scope boundary

Agora should:

- truthfully describe the upstream CTS/Scaife operation boundary;
- prevent its bundled skill from routing Scaife-only discovery into CTS-only resolution without a fallback;
- record the limitation as structured plugin verification metadata;
- continuously observe one stable live signature so the metadata is revisited if upstream behavior changes.

Agora should not:

- fork or patch `perseus-mcp`;
- rewrite CTS/Scaife responses;
- synthesize a translation mapping between CTS and Scaife edition URNs;
- hide Scaife-only works from discovery;
- implement navigation fallbacks that belong to upstream #24-class behavior.

## Severity

The issue is **advisory**, not blocking:

- the plugin starts and exposes tools;
- CTS-backed resources continue to work;
- Scaife-backed resources are retrievable through Scaife-native tools;
- the defect is incorrect/ambiguous routing between two upstream inventories.

The aggregate Perseus plugin and Codex live check should therefore remain usable/verified while carrying the explicit advisory.

## Proposed live retirement canary

The existing Perseus live smoke should retain its ordinary positive smoke and additionally verify one bounded signature:

1. merged `find_author_names("Euripides", language="greek")` includes `urn:cts:greekLit:tlg0006.tlg020`;
2. CTS-only `get_work_resources` for that exact work currently reports no match;
3. Scaife-native metadata for the same work is available.

The canary is evidence about routing, not a substitute implementation.

If the expected mismatch disappears, CI should fail with an actionable message to retire or revise the canonical known-issue entry and the skill workaround. This deliberately prevents a stale warning from surviving an upstream fix.

The canary should not assert large passage bodies, exact English translations, or fragile counts beyond the minimal routing signature.

## TDD target

Before changing production metadata, skill guidance, or smoke behavior, add regressions that fail on current `main` because:

- plugin verification schema does not accept structured plugin `known_issues`;
- Perseus canonical metadata does not declare the advisory;
- the skill does not explicitly route Scaife-only merged discoveries to Scaife tools;
- the Perseus live smoke has no declared retirement canary for the advisory.

Only after RED is recorded should the implementation be added.

## Expected closure condition for #21

#21 can close when Agora accurately represents and verifies the current upstream contract. The actual upstream routing design may remain unchanged.

A future upstream release that unifies resource provenance/routing should cause the canary to demand removal or revision of the advisory rather than leaving historical workarounds indefinitely.