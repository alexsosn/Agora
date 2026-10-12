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


## Validating documentation changes

A pull request that changes only approved researcher documentation and the
explicitly reviewed documentation generators or contract tests uses Agora's
bounded documentation checks. Those checks still validate generated guides,
registry consistency, Python syntax, links, and first-contact instructions.

Changes to plugin implementations, MCP manifests, release acquisition, corpus
registries, cache or installer logic, dependencies, CI workflows, or unknown
files always require the full validation matrix, even when documentation is
changed in the same pull request. The complete runtime suite also runs after
changes merge to `main`. CI's change-scope report describes the selected
gate; it is not permission to skip required checks manually.

The Ubuntu, macOS, and Windows cache/installation matrix jobs retain their
usual check identities on a documentation-only pull request. They run an
explanatory step while skipping runtime setup, dependency installation, and
cross-OS regression tests. The ordinary full-scope matrix is still required
for all runtime or mixed changes.
