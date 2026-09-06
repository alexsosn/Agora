# Design: mixed-version-safe materializer installation locking

Issue: #63

Research: [`P1-research-materializer-lock-protocol-migration.md`](P1-research-materializer-lock-protocol-migration.md)

## Goals

- Preserve mutual exclusion when first crossing from pre-#62 sentinel locking into the current protocol.
- Preserve mutual exclusion with the #62 advisory-only implementation in both arrival orders.
- Preserve OS-backed process-death release for modern code.
- Avoid unlink/recreate races on the historical lock pathname.
- Fail closed for ambiguous empty/unrecognized historical files.
- Document the migration as intentionally one-way until an explicit quiescent downgrade step is performed.

## Non-goals

- Transparent concurrent interoperability among all three generations after migration.
- Automatically deciding that an empty legacy file is stale.
- Making pre-#62 and #62 safe when run directly together; those released protocols do not coordinate.
- Coordinating machines that do not share one filesystem.
- Changing materializer execution, source integrity, packaging, or registry semantics.

## Protocol

For a historical path such as `.source.lock`:

1. Ensure the parent directory exists.
2. If the path is absent, create it with `O_CREAT|O_EXCL` and write the fixed marker `agora-materializer-lock-v3\n`.
3. If the path exists with the exact marker, reuse it as the permanent modern lock object.
4. If the path exists empty or with unrecognized contents, do not delete or rewrite it. Poll until it disappears or the timeout expires. A persistent state raises actionable migration guidance.
5. Acquire `portalocker.Lock` on the historical path itself using only the remaining timeout budget.
6. Re-read the marker after advisory acquisition. If it is no longer the exact v3 marker, release and fail closed.
7. Enter the critical section.
8. On normal release or exception, release only the OS advisory lock. Do **not** unlink the historical path.

There is no current-only sidecar and no automatic sentinel cleanup.

## Compatibility properties

### Pre-#62 → current

If pre-#62 owns the pathname first, current sees an empty/unrecognized file and waits. If the old holder releases and unlinks it, current can create the v3 marker. If current wins the `O_EXCL` creation race, later pre-#62 callers remain excluded by file existence.

### #62 ↔ current

Both protocols advisory-lock the same historical pathname. Once the marker has been established, they exclude each other correctly. #62 opens the file in append mode and does not need the file to be empty, so the marker remains compatible with its locking behavior.

### Current ↔ current

All current processes advisory-lock the same persistent historical file. Process death releases the OS lock; no cleanup is required.

### Downgrade to pre-#62

Pre-#62 cannot run while the v3 marker exists. This is deliberate. A user who intentionally downgrades must first confirm that no #62/current operation is active, then remove the marker manually. That manual quiescent transition is the only safe way to cross back over the boundary.

## Timeout semantics

The caller's `timeout` is one monotonic budget covering:

- waiting for a pre-v3 ambiguous pathname to disappear; and
- advisory-lock acquisition on the persistent historical path.

No phase receives a second full timeout window.

## Marker initialization

The marker is a protocol discriminator, not an owner record. If the process crashes while creating/writing the marker, a partial or empty file may remain. That state is treated conservatively as ambiguous and requires the same manual recovery as historical stale state.

Do not unlink a partially initialized path automatically: a #62 process may already have opened that inode.

## TDD sequence

### Existing RED/GREEN history

Earlier slices established:

- pre-#62/current incompatibility on main;
- #62/current incompatibility in the first bridge draft;
- the unsafe unlink/waiter race in the second bridge draft.

Those findings remain documented in the PR review history.

### RED 4 — one-way persistence

Revise/add regressions before simplifying production code:

- clean current release leaves the exact v3 marker in place;
- a pre-#62 `O_EXCL` client remains blocked after current release;
- a second current operation reuses the same persistent marker;
- a current crash leaves the marker and later current code reuses it without deleting it;
- a #62 acquire/release against an established marker preserves the marker;
- empty/unrecognized legacy state still fails closed.

These tests must fail against the current three-part bridge because it deletes the historical path after each current operation.

### GREEN 4

Simplify `_lock` to one persistent historical pathname plus advisory ownership. Remove the sidecar and all clean-release unlink logic. Keep public call sites unchanged.

### Documentation

Update the architecture reference and installer guidance to say:

- the marked lock file is permanent modern protocol state, not stale residue;
- empty/unrecognized pre-v3 files require one-time manual cleanup only after confirming no older operation is running;
- deliberate downgrade to pre-#62 requires manual marker removal only after confirming no #62/current operation is running.

## Verification gate

Run at minimum:

```bash
python -m unittest discover -s tests -p 'test_materializer_install*.py' -v
python scripts/validate_registry.py
python scripts/generate_marketplaces.py --check
python scripts/generate_context_fabric_catalog.py --check
```

The Foundation `materializer-install-locks` matrix must pass on Ubuntu, macOS, and Windows at the exact PR head.

## Independent adversarial review checklist

Review without relying on the implementation rationale and try to falsify:

- Can current enter while a live pre-#62 holder still owns an empty sentinel?
- Can pre-#62 enter after current has established the persistent marker?
- Can current and #62 ever hold the critical section concurrently?
- Can two current processes enter concurrently after a crash?
- Can any code path unlink or replace a pathname while a #62 waiter may already have it open?
- Does partial marker initialization fail closed rather than being guessed stale?
- Is the timeout still one budget?
- Are backend lock failures still distinguished from ordinary contention?
- Does the protocol rely on POSIX-only unlink semantics or fail on Windows?

Any blocker starts another fix → retest → fresh independent review loop before the PR is finalized.