# Local Codex development and testing

This is for contributors and researchers testing a local Agora checkout. For ordinary plugin installation use the [researcher installation guide](installation.md); host-specific commands remain controlled by the host.

Codex supports repo/team marketplaces at `<repo-root>/.agents/plugins/marketplace.json`. A local Agora clone therefore already has the expected marketplace layout.

Clone Agora:

```bash
git clone https://github.com/alexsosn/Agora.git
cd Agora
```

For a non-default local marketplace, current Codex tooling supports adding the marketplace root and then installing a plugin from its marketplace name:

```bash
codex plugin marketplace add /absolute/path/to/Agora
codex plugin add context-fabric@agora
```

Repeat the `codex plugin add ...@agora` command for `perseus`, `sefaria`, or `sedra` as needed.

After reinstalling or updating a local plugin, start a new Codex thread when necessary so the updated skill/MCP package is picked up cleanly.

For user-wide local plugin development, Codex also supports the default personal marketplace at `~/.agents/plugins/marketplace.json`; a marketplace entry's `source.path` is resolved relative to that marketplace root. Agora does not overwrite or manage a user's personal marketplace file automatically.

