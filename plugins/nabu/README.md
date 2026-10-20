# Nabu

Read-only MCP access to a **library you build yourself on your own disk**.

[Nabu](https://github.com/arvicco/nabu) is local-first personal research
infrastructure: a Ruby pipeline plus SQLite databases that ingest the world's
openly licensed digital corpora of antiquity — Greek and Latin, documentary
papyri, cuneiform, the Hebrew Bible with Targums and Peshitta, Sanskrit and
Tamil, classical Chinese and the Buddhist canon, the Islamicate library, Old
English, the Slavic shelves, and many more — into one searchable, citable
catalog. Its site reports, as of 19 October 2026, **2,436,904 documents
comprising 114,182,100 passages in 222 language codes across 216 live
sources**, plus 3,063,044 dictionary entries across 569 reference shelves
(figures from <https://arvicco.github.io/nabu/>; a user's own library holds
whatever subset of sources that user has synced).

**Nothing is hosted and no corpus data is vendored by this plugin.** The MCP
server serves the library on the user's machine, and only the sources the user
has enabled and synced. Installing this plugin without building a library
yields a server with an empty catalog.

## Prerequisites

- Ruby 3.3+ with Bundler, and git.
- Upstream develops and tests on macOS (Apple Silicon); no other platform is
  exercised by upstream, though nothing is known to be Mac-specific outside
  its ops templates.
- Disk space proportional to the sources you sync (the starter shelf is about
  690 MB; a large library runs to hundreds of GB).

## Building your library

Summarized from Nabu's own docs
([quickstart](https://arvicco.github.io/nabu/quickstart/),
[docs/quickstart.md](https://github.com/arvicco/nabu/blob/main/docs/quickstart.md)):

```bash
git clone https://github.com/arvicco/nabu && cd nabu
bundle install
bin/nabu quickstart        # starter shelf: 4 sources, ~690 MB, minutes
```

Grow the library with `bin/nabu enable <source>` and `bin/nabu sync <source>`
(or whole research desks with `enable <axis>`); `bin/nabu list` and
`bin/nabu status` show what is held. Some sources are grant-gated or
non-commercial; Nabu records a license class per document and prompts for
grant acknowledgments where required.

## Launching the server

This plugin launches Nabu's own stdio MCP server, exactly as upstream
documents it ([docs/mcp.md](https://github.com/arvicco/nabu/blob/main/docs/mcp.md)):

```bash
BUNDLE_GEMFILE="$NABU_HOME/Gemfile" bundle exec "$NABU_HOME/bin/nabu" mcp
```

Set the **`NABU_HOME`** environment variable to your Nabu checkout before
starting your client; the generated `mcp.json` expands it so the server is
launched against that checkout regardless of the client's working directory.
The server speaks MCP revision 2025-11-25 over stdio (newline-delimited
JSON-RPC 2.0); stdout carries only protocol messages, diagnostics go to
stderr.

## Tools

Thirteen read-only tools (the server's complete registry):

| Tool | What it does |
|---|---|
| `nabu_search` | Full-text search (lemma, proximity, fuzzy-fragment, date/place/kind filters) |
| `nabu_show` | A passage, document, or citation range by URN, with license and provenance |
| `nabu_concord` | KWIC concordance |
| `nabu_align` | One citation across every registered witness of an aligned work |
| `nabu_define` | Dictionary-shelf lookup with citations resolved into the catalog |
| `nabu_etym` | The reconstruction walk: attested lemma to proto-forms and cognates |
| `nabu_parallels` | Passage-anchored intertext (quotations and echoes) |
| `nabu_cognates` | Verses where aligned witnesses use reflexes of the same root |
| `nabu_links` | The mined cross-reference graph for a URN |
| `nabu_char` | The Han character card (readings, decomposition, diachrony, attestation) |
| `nabu_place` | The place desk: holdings by findspot/provenance |
| `nabu_signs` | Cuneiform sign resolution for ATF transliteration |
| `nabu_status` | Per-source coverage of the local library |

Read-only is structural, not advisory: the catalog and index are opened with
`SQLITE_OPEN_READONLY`, and there are no write tools — a conversation cannot
sync, rebuild, withdraw, or edit anything.

## Licensing

- **Software:** Nabu's code is MIT; this Agora integration is MIT.
- **Data:** per-source. Every ingested text keeps its upstream license,
  recorded per document, and **every MCP result carries its license class**
  (`open` / `attribution` / `nc`), so an agent can quote and cite within each
  text's terms. Upstream reports roughly 94% of documents as public-domain or
  attribution-class; non-commercial shelves are never redistributed by the
  tooling. Per-source terms:
  [docs/02-sources.md](https://github.com/arvicco/nabu/blob/main/docs/02-sources.md)
  and <https://arvicco.github.io/nabu/sources/>.
