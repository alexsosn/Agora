# Design amendment: preserve source/parent trust-domain separation in #135

Research: `wiki/backlog/P1-research-materializer-parent-input-135-trust-domain-amendment.md`.

## RED

Add one focused test module using synthetic local materializer fixtures. Require all overlapping source/parent topologies to fail:

- equal paths;
- source nested inside parent;
- parent nested inside source.

The assertion must prove failure occurs after source acquisition but before staging/converter execution. Patch `_create_staging_output` to raise if reached; verify it is never called and the requested output remains absent.

Keep a disjoint control to ensure the existing accepted two-input path is not over-restricted.

Expected RED on the reviewed checkpoint: `_create_staging_output` is reached for overlapping paths because the host has no source/parent overlap check.

Preserve the exact failing head/run before production changes.

## GREEN

In `scripts/agora_materialize.py`, immediately after `prepared = acquire_source(...)`:

```python
if validated_parent is not None and _paths_overlap(prepared.path, validated_parent.path):
    raise ValueError("materializer source path overlaps the trusted parent resource boundary")
```

Do not move source acquisition earlier or alter the existing parent/output preflight. Do not add new path normalization semantics; reuse `_paths_overlap` and already-resolved `PreparedSource.path` / `ParentResourceBinding.path`.

The existing `finally` path must clean any automatically acquired source on failure.

## Regression

Run focused trust-boundary tests, existing parent input/sandbox tests, Foundation, sandbox E2E and registered materializer smoke. Re-review path containment after the later lease-lifetime slice is green.
