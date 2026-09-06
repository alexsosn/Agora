# Research: materializer lock protocol migration safety

Issue: #63

Checked: 2026-09-06

## Question

How can the materializer installer remain safe when two Agora checkouts sharing the default install root straddle the lock change merged in #62?

The installer must preserve two properties that pull in opposite directions:

1. a current installer must not enter while a pre-#62 sentinel-file installer is live;
2. a current installer must not recreate #62's permanent lock-file residue, because an older installer treats file existence itself as ownership.

This is Agora-owned installation behavior, so the fix belongs here rather than upstream.

## Protocols in the field

### Pre-#62

The old `_lock` won an `O_CREAT|O_EXCL` create race on the visible lock path, kept the file descriptor open for the critical section, and unlinked the file on normal release. It did not take an OS advisory lock.

Consequences:

- another old process is excluded by file existence;
- a current advisory-lock-only process is **not** excluded by the old holder on POSIX, because advisory locks only coordinate participants that also lock;
- process death can leave an empty sentinel behind indefinitely.

### #62 / current `main` before this ticket

The replacement uses `portalocker.Lock(path, mode="a", EXCLUSIVE|NON_BLOCKING)`. The OS lock is released on process death, but `portalocker.Lock` deliberately leaves the file on disk.

Portalocker 4.3 documents both relevant semantics:

- POSIX locking is advisory, so a process that merely creates/opens a file without taking the advisory lock is not excluded: https://portalocker.readthedocs.io/en/latest/platforms.html
- `Lock` releases the OS lock but leaves the lock file in place: https://portalocker.readthedocs.io/en/latest/lock-types.html#lock

That explains both #63 failures directly.

## State analysis

For the visible legacy path, there are four important states:

| Visible path | Advisory lock on that path | Possible meaning |
|---|---|---|
| absent | no | idle |
| present, empty | no | live pre-#62 holder **or** stale pre-#62 crash **or** stale #62 residue |
| present, empty | yes | live #62 holder |
| present, current-protocol marker | sidecar lock decides | current-protocol live/crashed holder |

The second row is the migration boundary. A stale #62 file and a live pre-#62 holder are indistinguishable using only portable filesystem and advisory-lock observations. The live pre-#62 process takes no advisory lock and writes no owner metadata. Therefore a current process cannot safely auto-delete an empty, unlocked legacy path: doing so may delete the live old holder's sentinel and admit concurrent installers.

This is not fixed by checking PID liveness unless the old protocol had written a PID, which it did not. It is not fixed by locking the same path: a current process can successfully take an advisory lock on a file owned by a live pre-#62 sentinel holder on POSIX. It is not fixed by leaving a current advisory lock file in place: that is exactly what wedges older arrivals after #62.

## Viable choices

### A. Transparent deletion of unlocked legacy files

Reject. It makes #62 residue convenient to migrate but can violate mutual exclusion with a live pre-#62 installer.

### B. Revert completely to sentinel locking

Reject. It restores mixed-version exclusion but also restores the process-death stale-file wedge that #62 intentionally fixed.

### C. One-way conservative migration with a hybrid protocol

Selected.

A current installer should:

1. serialize current versions on a separate OS-backed sidecar advisory lock;
2. while holding that sidecar, create the **legacy visible path** with `O_EXCL` so pre-#62 arrivals stay out;
3. put a current-protocol marker in that visible sentinel;
4. remove the visible sentinel on normal release before releasing the sidecar;
5. when the visible sentinel contains the current marker but the sidecar lock is free, treat it as crash residue from the current protocol and remove it safely;
6. when the visible sentinel is empty/unrecognized, wait for it to disappear and then fail closed with an actionable migration error if it persists.

The sidecar preserves #62's important property for current-version crashes: the OS releases ownership automatically. The marker makes current-protocol crash residue distinguishable from old ambiguous state. Clean release removes the legacy-visible path, so normal current use does not wedge an older checkout later.

A process killed after creating the current marker can be recovered automatically by a later current installer. The tiny create-before-marker-write interval remains a conservative ambiguous state if the process is killed at exactly that point; it fails closed rather than risking overlap. That is preferable to unsafe recovery.

## Downgrade/migration rule

An empty/unrecognized legacy lock file may be a live pre-#62 holder, so Agora must not delete it automatically. If a user knows no old installer is running, removing that file is the one-time recovery from stale pre-#62/#62 state. The error and installation documentation should say this explicitly.

After one successful current-protocol operation, clean releases do not leave the legacy path behind, so ordinary later use of a pre-#62 checkout is no longer permanently wedged by current-version residue.

## Required regression evidence

The implementation should prove:

- a simulated pre-#62 holder blocks a current `_lock` and a current waiter enters only after the old holder unlinks the sentinel;
- while a current `_lock` is held, a simulated pre-#62 `O_EXCL` acquire fails;
- current clean release removes the visible sentinel;
- current process death releases the sidecar lock, and a subsequent current `_lock` recovers its marked stale sentinel;
- an empty/unrecognized preexisting sentinel is never auto-deleted and produces an actionable failure after the configured timeout;
- existing current-current contention/wait behavior remains intact on Linux, macOS, and Windows.

## Conclusion

There is no portable, safe automatic way to distinguish a stale #62 empty lock file from a live pre-#62 sentinel holder. The correct migration policy is fail-closed for ambiguous old state and self-identifying cleanup for the new hybrid protocol. This trades one-time manual recovery of ambiguous legacy residue for preservation of the installer's primary safety invariant: never run two materializer mutations concurrently against the same install root.
