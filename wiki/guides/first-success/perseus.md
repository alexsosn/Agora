# First success: retrieve Iliad 1.1 with Perseus

## Start after installation

Open the installed **Perseus** plugin. Its live services expose both legacy CTS and Scaife-backed paths; they are related but do **not** share every resource or navigation capability.

## Try this

Ask the agent: “Find Homer's *Iliad* in the service currently exposing it. Retrieve Iliad 1.1 by a discovered edition URN and cite the exact service used.”

1. Use `find_author_names` to discover Homer or the matching text group; do not guess an edition URN from an example.
2. Inspect the discovered work. Use `get_author_resources` and `get_work_resources` only if the CTS inventory actually resolves that work. When a discovery result belongs only to Scaife, use `get_scaife_library_metadata` and its returned edition or translation identifier instead.
3. Retrieve **Iliad 1.1** using the appropriate passage-retrieval tool and the **discovered URN** for that same service. Ask to show the returned passage plus edition/service provenance. Do not infer adjacent passage references.

## What success looks like

The verse/passage text at Iliad 1.1 with the service actually queried, a returned (not invented) edition URN, and a statement about whether CTS or Scaife supplied the result. If an upstream service does not return the expected work or passage, report its actual response rather than fabricating a citation.

## Interpretation limits

Legacy **CTS** metadata and valid-reference navigation can return **malformed** HTML for otherwise retrievable passages. **Do not** treat this as proof the work is unavailable or assume that Scaife and CTS identifiers are interchangeable. Search and morphology are separate capabilities; retrieving one passage does not establish provider-wide navigation support.

## Next steps

Read the [Perseus research skill](../../../plugins/perseus/skills/perseus-research/SKILL.md#cts-and-scaife-are-related-but-not-interchangeable) or try a form-versus-lemma search only after resolving the correct edition. See the [Perseus plugin page](../plugins/perseus.md) for current limits.
