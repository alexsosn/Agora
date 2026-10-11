# First success: Genesis 1:1 with Sefaria

## Start after installation

Open the installed **Sefaria** plugin. It queries the hosted Sefaria service; no local copy of the text library is installed.

## Try this

Ask the agent: “Retrieve Genesis 1:1 in Hebrew and English, then show one classical commentary linked to this verse if the service supplies it. Cite the versions and reference.”

1. Call `get_text` for **Genesis 1:1** in the Hebrew source layer and again for English, choosing `version_language` intentionally rather than treating a default translation as uniquely authoritative.
2. Use `get_links_between_texts` (or the service's linked-text workflow) for this reference. Inspect any returned relation and select at most one actual commentary link. If no link is returned, say so without inventing one.
3. Retrieve or inspect the selected commentary only if the service actually exposes it. Clearly label source text, translation and commentary as distinct textual layers.

## What success looks like

Genesis 1:1 with its exact reference, identified source/English versions where returned, and a service-backed linked commentary (or an explicit absence/unavailability statement). The commentary is another source, not proof of the primary text's meaning.

## Interpretation limits

Sefaria's search can return **duplicate** rows for the same textual reference indexed in different versions, sometimes without version IDs. Do **not** use raw search-result row counts as exact occurrence frequencies. Verify source-language and translation claims by retrieving the passage and preserving the version scope.

## Next steps

Follow the [Sefaria workflow guidance](../../../plugins/sefaria/skills/sefaria-research/SKILL.md#reproducible-reporting) or inspect related commentaries for another passage. See the [Sefaria plugin page](../plugins/sefaria.md) for service boundaries.
