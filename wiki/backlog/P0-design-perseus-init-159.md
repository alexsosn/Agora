# Plan: diagnose Perseus generated stdio initialization failure (#159)

Research: [`P0-research-perseus-init-159.md`](P0-research-perseus-init-159.md).

## Contract

Resolve #159 without hiding failures behind retries and without changing upstream scholarly behavior. The smoke must distinguish supported-client first-success verification from a best-effort advisory-retirement canary.

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

Observed on run `34628176807`:

- startup, MCP initialize, tool discovery, and the representative operation all succeed on both generated paths;
- Claude becomes inconclusive because merged discovery no longer contains the old canary specimen;
- Codex becomes inconclusive later because the Scaife metadata provider call returns an MCP error backed by `httpx.ReadError`;
- no runtime/version change is justified.

The failure is therefore Agora verification coupling, not a demonstrated Perseus launch/runtime incompatibility.

## Slice 3 — canary RED2/GREEN2

### RED2

Add focused regressions proving:

1. a changed discovery signature returns structured `inconclusive` canary evidence instead of failing the supported-client smoke;
2. a provider/MCP error during the canary returns structured `inconclusive` evidence naming the operation;
3. positive evidence that CTS now resolves the old mismatch still raises the existing “may have been fixed” retirement failure;
4. tools required by the documented workaround (`get_work_resources` and `get_scaife_library_metadata`) are still required during tool discovery, so capability removal is not silently downgraded to an inconclusive canary.

Preserve the RED2 commit before production changes.

### GREEN2

Implement the smallest conservative canary behavior:

- do not retry provider operations;
- do not rewrite or reinterpret Perseus results;
- return compact `status: inconclusive` evidence for changed specimen signatures or provider-operation failures;
- retain `status: observed` for the reproduced advisory;
- retain a hard retirement failure only when the canary positively demonstrates the previously missing CTS resolution while Scaife still identifies the target;
- keep representative-operation failures, missing expected tools, startup failures, and session failures as hard smoke failures.

## Final gates

- research and frozen plan committed before each implementation slice;
- preserved diagnostic RED and canary RED2;
- focused GREEN plus Foundation;
- exact generated Codex and Claude Perseus paths tested on Python 3.13;
- both paths complete the representative smoke on the final exact head, with any canary uncertainty preserved explicitly as evidence;
- #150 release matrix updated with truthful disposition;
- logically independent adversarial review of the frozen final head before merge.
