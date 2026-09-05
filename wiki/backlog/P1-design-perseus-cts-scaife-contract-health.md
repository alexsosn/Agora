# Design: Perseus CTS/Scaife contract health

Issue: #21
Research: `wiki/backlog/P1-research-perseus-cts-scaife-contract-health.md`

## Goal

Make Agora accurately represent and continuously verify the current upstream Perseus contract without forking, wrapping, or repairing upstream CTS/Scaife behavior.

The implementation has three independent responsibilities:

1. **canonical metadata** — record the known routing limitation as structured plugin verification state;
2. **agent UX** — teach the bundled Perseus skill how to react when merged discovery returns a Scaife-only work;
3. **retirement evidence** — make the existing live smoke observe one bounded signature so a later upstream fix forces the advisory/workaround to be revisited.

## Non-goals

This change will not:

- modify or vendor `perseus-mcp`;
- proxy or normalize its tool results;
- implement CTS/Scaife routing inside Agora;
- invent equivalence between CTS and Scaife translation URNs;
- address malformed CTS metadata/navigation behavior tracked in #24;
- downgrade Perseus wholesale while its principal operations remain usable.

## 1. Generic plugin known-issue metadata

### Schema

Extend `registry/schema/plugins.schema.json` so `verification` may contain `known_issues`.

Each item uses the same compact semantic shape already established for resources:

```yaml
- id: perseus/cts-scaife-inventory-routing
  severity: advisory
  signature: <short machine-readable/grep-friendly description>
  summary: <human-readable description>
  upstream:
    - repository: tonyjurg/Perseus-mcp
```

Required fields:

- `id`: stable `namespace/name` identifier;
- `severity`: `advisory` or `blocking`;
- `signature`: concise observable contract signature;
- `summary`: human-readable impact.

Optional upstream provenance may contain repository plus issue/URL when an upstream tracker exists. #21 currently has no matching upstream issue, so repository provenance alone is sufficient.

### Perseus canonical entry

Add one advisory under `registry/plugins.yaml` describing:

- merged author discovery may contain Scaife-only works;
- CTS `get_author_resources` / `get_work_resources` can therefore return no match for a work that is still retrievable through Scaife-native tools.

Keep plugin/client verification statuses unchanged. This is a partial routing limitation, not evidence that the launch or all advertised capabilities fail.

### Registry documentation

Document plugin-level known issues in `registry/README.md` next to executable verification evidence/status semantics. Distinguish them from resource-level known issues.

## 2. Agent-facing Perseus routing guidance

Update `plugins/perseus/skills/perseus-research/SKILL.md`.

The skill must state explicitly:

- `find_author_names` merges CTS and Scaife inventory information;
- `get_author_resources` and `get_work_resources` are CTS-oriented and may not resolve Scaife-only works from merged discovery;
- a zero CTS resource match after positive merged discovery is not proof that the work is unavailable;
- use `get_scaife_library_metadata` and Scaife passage tools for the discovered work when the work is Scaife-only;
- keep CTS and Scaife edition/translation URNs distinct and do not map `eng1` ↔ `eng2` or similar identifiers by guesswork.

The normal happy path remains concise: CTS-backed discovery can continue through CTS resource/passage helpers.

## 3. Live retirement canary

### Configuration

Extend `SmokeCase` with a tuple of stable known-issue canary IDs. Perseus declares:

```text
perseus/cts-scaife-inventory-routing
```

Other plugins default to no known-issue canaries.

The canary ID must correspond to a canonical `verification.known_issues` entry for that plugin. A smoke case must not silently execute an undeclared warning.

### Result decoding

Add a small helper for JSON-valued MCP tool results that accepts either:

- structured MCP result content; or
- text content containing one JSON document.

Reject missing, error, ambiguous, or non-JSON payloads with concise diagnostics. The helper exists only in the verification harness; it does not change plugin behavior.

### Perseus canary sequence

Use the same already-initialized MCP session and a single stable Euripides work:

`urn:cts:greekLit:tlg0006.tlg020`

1. `find_author_names(query="Euripides", language="greek", limit=20)`
   - require the target work URN to appear in merged discovery;
2. `get_work_resources(urn_or_title=<target>, language="greek")`
   - require current `match_count == 0`;
3. `get_scaife_library_metadata(urn=<target>)`
   - require a successful non-empty payload.

This is the minimal evidence for the advisory: merged discovery sees the work, CTS-only resolution does not, Scaife still can.

### Retirement behavior

If step 2 begins returning a CTS resource match, or the target no longer exhibits the declared signature, fail the smoke with a message that the known issue may have been fixed and the canonical advisory/skill workaround must be reviewed.

An upstream/service outage is not interpreted as advisory retirement; ordinary tool-call failures still fail the live smoke as operational failures.

### Evidence artifact

Add a `known_issue_canaries` array to the JSON smoke report. For each observed canary record:

- `id`;
- `status: observed`;
- compact evidence such as target URN and CTS match count.

This keeps the run evidence inspectable without embedding large upstream bodies.

## TDD sequence

### RED1 → GREEN1: canonical metadata

RED1 adds one registry test requiring the Perseus structured advisory.

Expected current failure: the advisory is absent.

GREEN1:

- extends plugin schema;
- adds the canonical Perseus advisory;
- documents plugin known issues in `registry/README.md`.

Existing `test_current_registry_is_valid` ensures the schema and canonical data are mutually valid.

### RED2 → GREEN2: skill routing

RED2 adds a skill invariant requiring explicit merged-discovery/CTS-only/Scaife fallback guidance and prohibition on guessed cross-service URN mapping.

Expected current failure: the skill lacks that explicit routing contract.

GREEN2 updates only the Perseus skill.

### RED3 → GREEN3: retirement canary

RED3 extends smoke-harness tests to require the Perseus canary declaration and deterministic canary behavior with fake MCP results:

- observed mismatch passes and returns compact evidence;
- a CTS match triggers the retirement failure;
- an undeclared canary is rejected.

Expected current failure: `SmokeCase` has no canary support.

GREEN3 implements the generic canary plumbing plus the Perseus-specific observer in `scripts/smoke_mcp_plugin.py`.

## Verification gates

Before review:

- full Foundation suite green;
- registry validation green;
- generated marketplace freshness unchanged/green;
- all existing cross-platform cache/materializer-lock jobs green;
- live MCP matrix green on the exact final SHA;
- Perseus live artifact contains `perseus/cts-scaife-inventory-routing` with `status: observed`;
- all other live integrations remain green.

## Review gate

Independent skeptical review must verify at least:

- the canary observes upstream behavior rather than implementing a fallback;
- the advisory does not incorrectly downgrade unrelated Perseus capabilities;
- result parsing cannot treat arbitrary error text as valid JSON evidence;
- the canary is tied to canonical metadata and cannot silently remain after the declaration is removed;
- the skill does not claim that CTS and Scaife URNs are interchangeable.

Any blocker enters its own RED → GREEN → exact-head CI → re-review loop before merge.

## Closure

Merge should close #21 because Agora will then truthfully represent, route around, and continuously observe the upstream limitation. Upstream server redesign remains upstream work, and malformed CTS navigation remains #24.