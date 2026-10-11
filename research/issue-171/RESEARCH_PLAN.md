# Issue #171 — decision-first compatibility documentation

## Research (2026-10-11)
- Current `wiki/guides/compatibility.md` starts with evidence taxonomy, then generated Claude/Codex paths, then platform startup and provider caveats. The first question of whether a path is supported requires reading methodological detail.
- Canonical `registry/plugins.yaml`: exactly Context-Fabric, Perseus, Sefaria, and SEDRA each declare `verification.clients.claude.status=verified` and `verification.clients.codex.status=verified`. Claude and Codex Context-Fabric/Perseus/SEDRA paths are stdio; Sefaria Claude is direct SSE, Codex is stdio-via-SSE-proxy. `registry/verification-checks.yaml` contains representative-operation generated-path checks. These DO NOT launch the Claude Code or Codex application executable itself.
- Installation guide: GitHub-imported MCP plugins in managed ChatGPT/Codex can be Desktop-only. A Desktop-only plugin cannot run in ChatGPT web; workspace plan/role/rollout matters. Do not equate Codex transport evidence with ChatGPT web support.
- Platform startup evidence is limited to Agora-owned Context-Fabric and SEDRA on Linux x86_64, Intel macOS x86_64, and Windows x86_64, **startup-only**, no Apple Silicon and no untested architecture assertions. Perseus and Sefaria are not covered by Agora-owned startup testing.
- Canonical `verification.known_issues`: Sefaria duplicate search-version hits; Context-Fabric 10,000 count cap and CUC `sign/usign` format discovery; Perseus malformed legacy CTS navigation. Existing notes are correct and should remain below the decision layer rather than losing technical details.
- Provider health, generated-path/client integration status, individual corpus/member acquisition, and scholarly suitability are distinct statuses; preserve the exact evidence/check IDs.

## Plan / gates
1. RED: deterministic test enforcing a user decision section before taxonomy; validate table entries against canonical registry client status/transport for all four plugins, bound platform and ChatGPT limits, plus preserved known issue IDs and explicit evidence caveats. Preserve test in history.
2. GREEN: prepend a compact table with verified **generated MCP paths** for Claude Code and Codex plus one-line caveat per plugin; add ChatGPT web/Desktop and measured platform bounds above evidence taxonomy. Keep the original detailed evidence, transport/check IDs, resource caution and upstream advisories intact.
3. Run focused tests, registry checks and Foundation CI on exact head. Independent skeptical review compares every decision claim against real registry and installation guide; correct blockers before merge.

No provider-specific implementation changes, platform-support expansion, marketing status badges, or unsupported guarantees.
