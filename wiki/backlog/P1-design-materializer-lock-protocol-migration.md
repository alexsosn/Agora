# Design: mixed-version-safe materializer installation locking

Issue: #63

Research: [`P1-research-materializer-lock-protocol-migration.md`](P1-research-materializer-lock-protocol-migration.md)

## Goals

- Preserve mutual exclusion when first crossing from pre-#62 sentinel locking into the current protocol.
- Preserve mutual exclusion with the #62 advisory-only implementation in both arrival orders.
- Preserve OS-backed process-death release for modern code.
- Avoid unlink/recreate races on the historical lock pathname.
- Preserve the caller's bounded timeout on Windows as well as POSIX.
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

1. Ensure the parent directory exists and record one monotonic deadline.
2. Inspect the pathname with `stat`, without reading file contents.
3. If the path is absent, create it with `O_CREAT|O_EXCL` and write the fixed ASCII marker bytes `agora-materializer-lock-v3` with `os.write`. The marker contains no newline, so its byte length is invariant across platforms.
4. If the file is not the marker's exact byte length, treat it as ambiguous pre-v3 state. Do not delete, rewrite, or advisory-lock it. Poll until it disappears or the deadline expires.
5. If the file has the marker's byte length, treat it only as a **candidate** modern lock object; do not read it yet.
6. Acquire an exclusive `portalocker.Lock` on that historical path using the remaining timeout. Open the lock handle in readable binary append mode.
7. Through the already acquired handle, read and verify the exact marker bytes. Compare the locked handle's filesystem identity (`fstat`) with both the pre-acquire candidate identity and the pathname's current identity (`stat`). If content or identity differs, release and fail closed.
8. Enter the critical section.
9. On normal release or exception, release only the OS advisory lock. Do **not** unlink the historical path.

There is no current-only sidecar and no automatic sentinel cleanup.

## Compatibility properties

### Pre-#62 → current

A pre-#62 sentinel is empty. Current code classifies its zero length without opening/locking its bytes and waits. If the old holder releases and unlinks it, current can create the v3 marker. If current wins the `O_EXCL` creation race, later pre-#62 callers remain excluded by file existence.

Avoiding an advisory lock on the live empty sentinel is important on Windows: current code must not hold an open mandatory lock that prevents the pre-#62 holder from unlinking its own sentinel during normal release.

### #62 ↔ current

Both protocols advisory-lock the same historical pathname after the v3 marker exists. Once current sees the marker-sized candidate, it lets portalocker perform bounded contention handling before reading the bytes. #62 opens the file in append mode and does not alter existing marker contents, so the persistent marker remains compatible with its locking behavior.

### Current ↔ current

All current processes advisory-lock the same persistent historical file. Process death releases the OS lock; no cleanup is required. A contender does not separately read locked bytes before acquisition, so Windows mandatory locking cannot bypass the configured timeout.

### Downgrade to pre-#62

Pre-#62 cannot run while the v3 marker exists. This is deliberate. A user who intentionally downgrades must first confirm that no #62/current operation is active, then remove the marker manually. That manual quiescent transition is the only safe way to cross back over the boundary.

## Timeout semantics

The caller's `timeout` is one monotonic budget covering:

- waiting for a pre-v3 ambiguous pathname to disappear; and
- advisory-lock acquisition on a candidate persistent historical path.

Metadata classification and post-acquire verification do not create a second wait budget. No potentially mandatory byte read occurs before portalocker owns the candidate file.

## Marker initialization

The marker is a protocol discriminator, not an owner record. It is written as fixed ASCII bytes with no line terminator. This avoids text-mode newline translation and makes the candidate-length test portable.

If the process crashes while creating/writing the marker, a partial or empty file may remain. Its size is then non-candidate (unless a failure happens after writing exactly the expected byte count), so ordinary current code treats it conservatively as ambiguous and requires the same manual recovery as historical stale state.

Do not unlink a partially initialized path automatically: a #62 process may already have opened that inode.

If a file has the expected marker length but wrong bytes, current code may acquire its advisory lock, but exact post-acquire verification fails before entering the protected section. The locked-handle/path identity checks additionally reject a pathname replacement that occurred while waiting.

## TDD sequence

### Existing RED/GREEN history

Earlier slices established:

- pre-#62/current incompatibility on main;
- #62/current incompatibility in the first bridge draft;
- the unsafe unlink/waiter race in the second bridge draft;
- one-way persistence semantics in RED/GREEN 4.

Those findings remain documented in the PR review history.

### RED 5 — Windows mandatory-read timeout

The first one-way implementation called `_lock_marker(path)` before advisory acquisition. Exact-head Windows CI showed the installation-lock step remaining active far beyond Linux/macOS because a separate read can block under Windows mandatory locking. The same run also misclassified the newline-bearing marker repeatedly, demonstrating that the protocol discriminator should not depend on text line-ending behavior.

A regression holds a marked current lock in one process while a second calls `_lock(timeout=short)`. The contender must return or raise within a bounded margin substantially below the holder's emergency wait. Retain the existing live-holder release test to prove a waiter still succeeds when the holder releases within the caller's budget.

### GREEN 5

- use a newline-free ASCII byte marker written with `os.write`;
- classify missing/legacy/candidate state using `stat` only;
- use a readable binary portalocker handle for candidate files;
- verify marker bytes through that acquired handle;
- verify pre-acquire candidate, locked-handle, and current-path identity before entering;
- preserve the persistent pathname and all fail-closed migration rules.

### Documentation

The architecture reference and installer guidance must state:

- the marked lock file is permanent modern protocol state, not stale residue;
- empty/unrecognized pre-v3 files require one-time manual cleanup only after confirming no older operation is running;
- deliberate downgrade to pre-#62 requires manual marker removal only after confirming no #62/current operation is running;
- modern lock liveness is OS advisory ownership, and marker inspection after migration occurs only after lock acquisition where Windows requires it.

## Verification gate

Run at minimum:

```bash
python -m unittest discover -s tests -p 'test_materializer_installation.py' -v
python -m unittest discover -s tests -p 'test_materializer_lock_migration.py' -v
python scripts/validate_registry.py
python scripts/generate_marketplaces.py --check
python scripts/generate_context_fabric_catalog.py --check
```

The Foundation `materializer-install-locks` matrix must explicitly run both materializer lock test files and pass on Ubuntu, macOS, and Windows at the exact PR head.

## Independent adversarial review checklist

Review without relying on the implementation rationale and try to falsify:

- Can current enter while a live pre-#62 holder still owns an empty sentinel?
- Can pre-#62 enter after current has established the persistent marker?
- Can current and #62 ever hold the critical section concurrently?
- Can two current processes enter concurrently after a crash?
- Can any code path unlink or replace a pathname while a #62 waiter may already have it open?
- Can Windows block in marker inspection before the timeout machinery is active?
- Does the locked handle actually verify the exact marker and current pathname identity before entry?
- Does marker byte representation remain identical across supported platforms?
- Does partial marker initialization fail closed rather than being guessed stale?
- Is the timeout still one budget?
- Are backend lock failures still distinguished from ordinary contention?
- Does the protocol rely on POSIX-only unlink semantics or fail on Windows?

Any blocker starts another fix → retest → fresh independent review loop before the PR is finalized.
