# First success: your own library answering with citations

## Start after installation

Nabu is a **user-local** runtime: before any tool works, you need your own
checkout and library — clone [arvicco/nabu](https://github.com/arvicco/nabu),
run `bundle install`, build a starter library (`bin/nabu quickstart`), and set
**`NABU_HOME`** to the checkout before starting your client. Prove the launch
with the bounded startup smoke
(`NABU_HOME=/path/to/nabu python3 scripts/smoke_nabu_user_local.py`) before
blaming the client: it names the failing step.

## Try this

Ask the agent: "Check what my Nabu library actually holds, then find one
passage mentioning a term in a held source and cite it."

1. Call `nabu_status` first and read the per-source coverage — which sources
   are enabled, how many documents and passages each holds.
2. Run one `nabu_search` for a term in a source the status showed as held
   (for the quickstart shelf, try a Latin word).
3. Report one hit with its **URN** and its **license class** (`open` /
   `attribution` / `nc`) — every result carries both, and the citation is the
   point.

## What success looks like

`nabu_status` returns the library's real coverage, and the search returns
passages with resolvable URNs whose text `nabu_show` can re-fetch verbatim.
An **empty** result set from an unsynced source — or an empty catalog on a
fresh install — is a correct answer about that library, not a server error.

## Interpretation limits

Coverage is per-install: `nabu_status` is the ground truth, never the
upstream site's headline figures. Results carry each document's upstream
license class; quote within those terms and keep the attribution. The server
is read-only by construction — a conversation cannot sync or edit the
library, so anything missing is fetched by the user in the checkout, not by
the agent.

## Next steps

Read the [Nabu plugin page](../plugins/nabu.md) for the full fourteen-tool
table, and upstream's
[MCP documentation](https://github.com/arvicco/nabu/blob/main/docs/mcp.md)
for per-tool parameters. Grow the library in the checkout (`bin/nabu enable`,
`bin/nabu sync`), then ask again — the same questions start answering from
the new sources.
