# Research amendment: source/parent trust-domain aliasing in #135

## Trigger

A logically independent review after the registered-forwarding GREEN checkpoint (`4cdae18638b5473080299a19422046830a2ae92e`) re-derived the two-input security boundary from the #135 design and inspected the current low-level host path handling.

## Finding

The host validates the trusted parent binding before source acquisition and rejects parent overlap with the writable output. After source acquisition, however, it does not compare `PreparedSource.path` with the validated parent path.

Therefore the source and parent may currently be:

- the same directory;
- parent/child directories in either direction.

This collapses two distinct provenance/trust domains into one filesystem tree. A registered execution could then describe one path as user-local/private source provenance while the same tree (or an enclosing/contained tree) is simultaneously represented as the canonical parent binding. Both sandbox mounts are read-only, so this is not primarily a write-escalation bug; it is an identity/provenance separation failure and creates ambiguous containment semantics.

The original #135 architecture explicitly treats private source and canonical parent as independently trusted inputs and requires separate mounts. The correct boundary is therefore non-overlap, not merely different rendered argument strings.

## Correct validation point

The source path is authoritative only after `acquire_source()` returns `PreparedSource`. Parent/source overlap cannot be rejected reliably in the earlier parent/output preflight.

The smallest correct check is immediately after source acquisition and before staging creation, sandbox construction, or converter launch:

```python
if validated_parent is not None and _paths_overlap(prepared.path, validated_parent.path):
    raise ValueError(...)
```

Existing `finally` cleanup already guarantees an automatically acquired source is released if this check fails.

## Required evidence

Before adding the check, preserve RED cases for all three alias topologies:

1. source equals parent;
2. source is contained by parent;
3. parent is contained by source.

Each must fail before staging/converter execution and must leave no output artifact. A disjoint source/parent pair must remain accepted by the existing parent execution tests.

No schema change, resolver behavior, network behavior, or source acquisition policy is required.
