---
name: perseus-research
description: Use this skill for research with Agora's Perseus plugin: discover authors, works, and edition URNs before passage retrieval; distinguish Perseus CTS from Scaife search resources; and use form or lemma search without inventing identifiers.
license: MIT
compatibility: Requires the Agora Perseus MCP plugin and network access to the live Perseus/Scaife services used by upstream Perseus-mcp.
metadata:
  provider: perseus
  version: "0.1.0"
---

# Perseus research workflow

Agora exposes the upstream Perseus-MCP service. Treat discovery as part of the scholarly workflow rather than hard-coding identifiers from memory.

## Core rule

**Do not invent URNs.** Discover the author, work, edition, and available service representation before constructing passage or search requests.

Perseus CTS and Scaife may expose different edition/resource URNs. A URN that works for one operation is not automatically valid for the other.

## Recommended workflow

### 1. Discover the author or text group

Use `find_author_names` when the author/text-group identifier is uncertain.

For broader browsing, use the provider's text-group listing tools and language filters rather than assuming a CTS namespace from an English name.

If multiple authors match, resolve the ambiguity before proceeding.

### 2. Inspect the author's resources

Use the author-resource tool to see works, editions, and translations actually advertised by the live service.

Then use `get_work_resources` for the specific work when edition choice matters.

Prefer an edition returned by discovery over an edition URN copied from an unrelated example or a previous session.

### 3. Retrieve passages with a discovered CTS URN

Choose the passage tool according to the task:

- use plaintext retrieval when you need readable primary text;
- use the richer passage helper when contextual metadata matters;
- use raw CTS XML only when XML structure itself is relevant.

For navigation, use valid-reference and neighboring-reference tools instead of generating citation suffixes arithmetically.

Always retain the exact CTS URN used in notes or reported results.

### 4. Search deliberately

Use `search_perseus` for Scaife-backed search.

Important parameters:

- `language` controls query normalization;
- `query_format` can distinguish Unicode Greek from Beta Code;
- `search_kind="form"` searches inflected forms;
- `search_kind="lemma"` searches dictionary lemmas;
- `preserve_operators=True` is appropriate when quoted phrases or Boolean-style operators must survive normalization.

Unicode Greek is normally preferable when you already have the correctly accented form. Beta Code is useful when the input is intentionally Beta Code.

Lemma search is **not** the same thing as receiving a full morphological analysis. Do not describe a lemma hit as proof that Perseus-MCP supplied case, number, tense, mood, or other morphology unless the returned tool output actually contains that annotation.

### 5. Narrow searches only with resolved identifiers

When searching within a text, use a text/edition URN returned by discovery.

When filtering by author or work, verify the filter maps uniquely to the intended CTS/Scaife resource. If an author name is ambiguous, resolve it before interpreting absence of results.

### 6. Check the underlying passage

For a research claim based on search:

1. inspect representative search hits;
2. retrieve the relevant passage text;
3. distinguish surface-form matching from lemma matching;
4. record the edition/resource URN;
5. state any filter or operator used.

Do not interpret raw hit counts before checking what the search endpoint counts as a hit/result instance.

## CTS and Scaife are related but not interchangeable

Perseus-MCP uses both the legacy Perseus CTS services and Scaife APIs.

Use CTS-oriented tools for passage addressing and citation navigation when the discovered edition is available there.

Use Scaife-oriented tools for search and Scaife library/passages when the requested operation is backed by Scaife.

If a work appears in one inventory but an edition fails in another service, rediscover the available resources instead of silently substituting a guessed URN.

## Greek search cautions

Short ASCII strings can be ambiguous between Beta Code and ordinary text. Specify `query_format` when automatic detection would be risky.

For phrase/operator queries, preserve operators explicitly. Otherwise normalization intended for Beta Code may alter the query semantics.

For philological comparison, distinguish:

- exact surface-form search;
- lemma search;
- phrase search;
- search constrained to a work/edition;
- post-search filtering done locally by the server.

These are not equivalent datasets for frequency interpretation.

## Upstream behavior

The live Perseus services can rate-limit repeated CTS requests. If a workflow receives HTTP 429 responses, reduce request rate/concurrency rather than treating the missing response as textual evidence.

Some Perseus navigation endpoints have historically returned malformed HTML. Upstream Perseus-MCP includes fallbacks for navigation, but a robust workflow should still prefer advertised valid references and inspect failures rather than inventing neighbors.

## Reproducible reporting

For a substantive result, record:

- author/work resolved by discovery;
- exact edition or text URN;
- whether the operation used CTS or Scaife;
- search kind (`form` or `lemma`) when applicable;
- query normalization/format and operators;
- passage URNs inspected to validate the interpretation.

If the live inventory changes, describe what the service advertised at the time rather than claiming that Agora ships a fixed Perseus corpus snapshot.
