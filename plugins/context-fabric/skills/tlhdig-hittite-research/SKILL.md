---
name: tlhdig-hittite-research
description: "Use this skill when loading TLHdig-TF through Agora Context-Fabric: select the registered resource, capture its resolved source revision, and consult the matching upstream documentation for corpus semantics and research suitability."
license: MIT
compatibility: "Requires the Agora Context-Fabric MCP plugin and the registered alexsosn/TLHdig-TF resource."
metadata:
  provider: context-fabric
  resource: TLHdig-TF
  version: "0.1.0"
---

# TLHdig-TF integration workflow

TLHdig-TF converts TLHdig, the Thesaurus Linguarum Hethaeorum digitalis corpus, to Text-Fabric.

Agora owns discovery, acquisition, and loading for this registered resource. The upstream repository and corpus documentation own corpus semantics, data-quality statements, limitations, and research-suitability guidance. Do not treat this skill as a substitute for those upstream sources.

## Load the registered resource

Use `load_corpus` with the registered `TLHdig-TF` resource.

Agora tracks the upstream default branch and selects `tf/0.1.0` explicitly. The returned `source_revision` identifies the exact upstream commit that was loaded and can change when upstream republishes.

## Use upstream documentation as the authority

Before interpreting or querying the corpus, read the README, schema/feature documentation, validation material, and any current limitation or suitability guidance in the [upstream TLHdig-TF repository](https://github.com/alexsosn/TLHdig-TF) at the resolved revision. Inspect the loaded Text-Fabric schema rather than relying on copied feature or annotation conventions in Agora.

If upstream documentation and the loaded data disagree, report the discrepancy upstream. Agora should not maintain a parallel interpretation or data-quality assessment.

## Reproducibility

For any reported experiment, record:

- Agora resource ID `TLHdig-TF`;
- TF version `0.1.0` and the resolved source commit when exposed;
- the upstream documentation revision consulted;
- node types and features used from that revision's schema;
- query logic and any researcher-supplied interpretation choices.
