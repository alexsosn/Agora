# Plan: diagnose Perseus generated stdio initialization failure (#159)

Research: [`P0-research-perseus-init-159.md`](P0-research-perseus-init-159.md).

## Contract

Resolve #159 without hiding the failure behind retries and without changing upstream scholarly behavior. The diagnostic path must make the exact failing phase and nested exception visible before any runtime/version change is proposed.

## Slice 1 — diagnostic RED/GREEN

### RED

Add a focused unit regression requiring `build_error_report()` to preserve a nested `ExceptionGroup` as structured data while keeping the existing top-level `error` string for compatibility. The regression must prove the leaf exception type/message survive serialization.

Add a focused phase contract around MCP session exercise so failures can be attributed at least to `initialize`, `list_tools`, representative `call_tool`, or known-issue canary execution rather than reported as an undifferentiated session failure.

Preserve the tests-only commit and confirm the failures are isolated to the missing diagnostic behavior.

### GREEN

Implement only the diagnostic surface:

- recursively serialize exception groups with bounded, JSON-safe `type`, `message`, and child exceptions;
- preserve explicit cause/context when useful without serializing tracebacks, local paths, or arbitrary object state;
- annotate session-operation failures with the current smoke phase while preserving their original exception as the cause;
- keep successful smoke output unchanged except for fields that are explicitly part of the new diagnostic contract.

Run focused smoke tests and Foundation.

## Slice 2 — exact live reproduction and classification

Re-run both generated Perseus client paths using the canonical Python 3.13 harness and exact constraint/lock identities. Capture the structured nested error and phase.

Then vary **one factor at a time** only if evidence requires it:

1. same generated command with startup/tool enumeration only;
2. MCP client/runtime version within an explicitly recorded temporary diagnostic environment;
3. FastMCP/runtime constraint;
4. Python minor runtime;
5. launch cwd/environment.

Do not alter multiple variables in one diagnostic experiment.

## Slice 3 — release disposition

Depending on evidence:

- **Agora-owned launch/harness defect:** add a focused RED, implement the smallest fix, and run both generated paths.
- **Pinned runtime incompatibility:** pin the evidenced compatible runtime in canonical constraints, update bound hashes/metadata, and verify both generated paths.
- **Upstream server defect without a safe released fix:** downgrade the affected 1.0 client/support claim and document the limitation instead of monkey-patching upstream.
- **External transient provider failure:** only classify it as such if initialization succeeds and the failure is demonstrably at a provider operation; retries remain out of scope unless an upstream contract explicitly makes retry safe and necessary.

## Final gates

- research and frozen plan committed before implementation;
- preserved diagnostic RED;
- focused GREEN plus Foundation;
- exact generated Codex and Claude Perseus paths tested on Python 3.13;
- #150 release matrix updated with truthful disposition;
- logically independent adversarial review of the frozen final head before merge.
