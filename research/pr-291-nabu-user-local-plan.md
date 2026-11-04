# PR #291 rework — user-local runtime environments and the Nabu listing

Answers the review of 2026-11-04 at e256bd5. Research preceded this plan:
the findings below are read first-hand from the default branch's
validator, generator, smoke harness and the in-flight CAL-MCP plan
(#268), and each blocking finding maps to a contract test written RED
before the code that turns it green.

## Findings

1. **Validator.** `scripts/validate_runtime_environments.py` enumerates
   environment kinds: `hosted` plus the file-backed `uv-lock` /
   `uv-constraints`. `kind: user-local` (an environment that exists only
   on the user's machine, resolved at launch through a user-supplied
   `${VAR}`) is rejected as unsupported, and `_validate_launch_binding`
   has no semantics for it. The same enumeration appears in
   `scripts/smoke_mcp_plugin.py:_bind_environment_identity`, which would
   also reject it — correctly so for a live harness run, but with a
   message that reads as a registry defect rather than a deliberate
   boundary. `scripts/check_runtime_environment_freshness.py` uses
   explicit project lists and is unaffected.
2. **Generation.** `scripts/generate_marketplaces.py` reads
   `registry/v0.1.yaml` literally; v0.1 is frozen (exactly four plugins,
   37 Context-Fabric resources, both asserted in
   `scripts/validate_registry.py`). Hand-adding `plugins/nabu/*`
   manifests leaves Nabu outside every generated marketplace. The
   in-flight CAL-MCP plan (#268) introduces a prospective
   `registry/v1.1.yaml` and repoints the generator at it.
3. **Resources.** Every record in `registry/resources.yaml` is a real
   Context-Fabric corpus/collection that Agora's prepare/load machinery
   can acquire. A `nabu-library` record with `acquisition.strategy:
   repository` misstates that contract: Agora acquires nothing for it,
   and `repository` describes code provenance, not data acquisition.
4. **Evidence.** The committed checks compare literal JSON to expected
   args; nothing demonstrates that the generated launch starts a real
   server anywhere.

## Plan

1. **Validator semantics for `user-local`** (RED tests first, in
   `tests/test_runtime_dependency_environments.py`): the kind carries no
   repository identity, so it must not declare `path`/`sha256`; the
   launch binding must not borrow the repo-managed Python launchers
   (`uv`/`uvx`), must not be a hosted `url`, and must resolve the
   checkout through at least one user-supplied `${VAR}` placeholder in
   its args or env (client-provided roots such as `CLAUDE_PLUGIN_ROOT`
   do not count). Negative cases pin each refusal.
   `smoke_mcp_plugin.py` refuses user-local environments explicitly: a
   live harness run cannot bind an environment that exists only on an
   operator's machine (fail-closed, with a message that says so).
2. **Prospective scope, composing with #268**: add
   `registry/v1.1.yaml` (the post-1.0 scope name #268 already uses)
   carrying the four v0.1 plugins plus `nabu` and the unchanged 37
   resources. `validate_registry.py` validates EVERY `registry/v*.yaml`
   scope (schema + membership + the rule that a later scope keeps every
   v0.1 plugin) while the frozen v0.1 assertions stay verbatim.
   `generate_marketplaces.py` targets the highest-versioned scope, so
   when CAL's record lands in `v1.1.yaml` the generator carries both
   without either PR overwriting the other; the required-plugin order
   stays the marketplace order, with new plugins appended after the
   frozen four. Marketplace artifacts and every plugin manifest are
   regenerated from the canonical registry (version 1.1.0), and
   `--check` plus `tests/test_generation.py` run scope-aware instead of
   hardcoding four.
3. **Resource honesty**: drop the `nabu-library` resource record
   entirely. What a user's library may hold stays where it already
   lives — the plugin's description, notes and README. A registry
   record returns only when Agora grows explicit external/user-managed
   catalog semantics with a tested discover/prepare boundary.
4. **Launch evidence**: `scripts/smoke_nabu_user_local.py`, a bounded
   startup smoke run on a machine that has a Nabu checkout: it expands
   `${NABU_HOME}` exactly as the generated manifest states, launches
   the server from a foreign working directory through Bundler,
   performs MCP initialize → tools/list → one `nabu_status` call with a
   hard timeout, and separately proves the error path (no NABU_HOME →
   immediate, explained failure; no library → the server's own
   honest answer). `tests/test_nabu_user_local_smoke.py` runs it when
   `NABU_HOME` is set and skips otherwise, so CI stays offline. The
   plugin README's install text points at the smoke as the "it works"
   gate and claims nothing beyond it; verification statuses stay
   `experimental` on both clients.

Out of scope here: any change to the frozen v0.1 artifacts' meaning,
the CAL candidate's record, or Agora acquiring/hosting Nabu data.
