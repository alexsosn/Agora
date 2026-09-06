# Research: materializer lock protocol migration safety

Issue: #63

Checked: 2026-09-06

## Question

How can the materializer installer remain safe when Agora checkouts sharing one install root use any of the lock protocols that existed around #62?

The installer must preserve three properties:

1. a current installer must not enter while a pre-#62 sentinel-file installer is live;
2. a current installer must not enter beside the advisory-only implementation introduced by #62, and that #62 implementation must not enter beside a current installer;
3. current clean runs must not recreate #62's permanent visible lock-file residue, because pre-#62 code treats file existence itself as ownership.

This is Agora-owned installation behavior, so the fix belongs here rather than upstream.

## Protocols in the field

### Pre-#62

The old `_lock` won an `O_CREAT|O_EXCL` create race on the visible lock path, kept the file descriptor open for the critical section, and unlinked the file on normal release. It did not take an OS advisory lock.

Consequences:

- another pre-#62 process is excluded by file existence;
- an advisory-lock-only process is **not** excluded by the old holder on POSIX, because advisory locks only coordinate participants that also lock;
- process death can leave an empty sentinel behind indefinitely.

### #62

The replacement uses `portalocker.Lock(path, mode="a", EXCLUSIVE|NON_BLOCKING)`. The OS lock is released on process death, but `portalocker.Lock` leaves the visible file on disk.

Portalocker 4.3 documents both relevant semantics:

- POSIX locking is advisory, so a process that merely creates/opens a file without taking the advisory lock is not excluded: https://portalocker.readthedocs.io/en/latest/platforms.html
- `Lock` releases the OS lock but leaves the lock file in place: https://portalocker.readthedocs.io/en/latest/lock-types.html#lock

This creates two interoperability hazards: pre-#62 holders do not exclude #62 arrivals, and #62 residue permanently wedges later pre-#62 arrivals.

## State analysis

For the historical visible path:

| Visible path | Advisory lock on that path | Possible meaning |
|---|---|---|
| absent | no | idle |
| present, empty | no | live pre-#62 holder **or** stale pre-#62 crash **or** stale #62 residue |
| present, empty | yes | live #62 holder, possibly alongside a pre-#62 holder because those protocols do not coordinate |
| present, current marker | no | current-protocol crash residue, unless a #62 client is racing to acquire it |
| present, current marker | yes | live current holder **or** a #62 client attached to current crash residue |

An empty, unlocked historical path is the irreducible migration ambiguity. A stale #62 file and a live pre-#62 holder are indistinguishable using portable filesystem and advisory-lock observations. The pre-#62 process writes no owner metadata and takes no advisory lock. A current process therefore cannot safely auto-delete an empty, unlocked legacy path.

Taking only a new sidecar plus an `O_EXCL` sentinel is also insufficient. That excludes pre-#62 clients, but a #62 checkout ignores file existence and can advisory-lock the visible sentinel unless current code also holds the historical-path advisory lock. Conversely, a marked current crash residue cannot be reused merely because the current sidecar is free: a #62 process may have opened that residue and be holding its advisory lock.

## Viable choices

### A. Transparent deletion of unlocked legacy files

Reject. It makes stale #62 residue convenient to migrate but can delete the sentinel of a live pre-#62 installer.

### B. Revert completely to sentinel locking

Reject. It restores pre-#62 compatibility but neither excludes #62 advisory-only clients nor preserves process-death release.

### C. One-way conservative migration with a three-part bridge

Selected.

A current installer should:

1. serialize current versions on a separate OS-backed sidecar advisory lock;
2. while holding that sidecar, create the **historical visible path** with `O_EXCL` so pre-#62 arrivals stay out;
3. put a current-protocol marker in that visible sentinel;
4. acquire and hold an OS advisory lock on that **same visible path** before entering the critical section, so #62 arrivals stay out;
5. if the visible path already contains the current marker, treat it as potentially recoverable current crash residue but acquire the visible-path advisory lock before reusing it; this prevents recovery through a live #62 holder;
6. on clean release, unlink the owned visible sentinel while still holding both advisory locks, then release the visible-path advisory lock and finally the sidecar;
7. if the visible sentinel is empty/unrecognized, wait for it to disappear and fail closed with actionable migration guidance if it persists.

The three mechanisms cover distinct generations: visible existence excludes pre-#62, the historical-path advisory lock excludes #62, and the sidecar serializes current versions while giving current crash residue an OS-owned liveness channel independent of the historical path.

There is a safe race if #62 opens the newly created current sentinel before current code acquires the historical advisory lock: current waits for #62 to release that lock and does not enter until it owns it. Because current already created the visible sentinel, pre-#62 arrivals remain excluded during that wait.

A current process killed after writing its marker leaves a distinguishable sentinel; later current code may reuse it only after acquiring both the sidecar and historical-path advisory lock. The tiny create-before-marker-write interval remains conservative ambiguous state if killed exactly there and therefore fails closed.

## Downgrade/migration rule

An empty/unrecognized historical lock file may be a live pre-#62 holder, so Agora must not delete it automatically even when its advisory lock is free. A stale #62 file therefore may require one-time manual removal. The user must first confirm that no older materializer operation is running.

After one successful current-protocol operation, clean release removes the historical visible path. Ordinary later use of pre-#62 code is therefore not permanently wedged by current-version residue.

## Required regression evidence

The implementation should prove:

- a simulated pre-#62 holder blocks current code, and current waits successfully when a brief pre-#62 holder unlinks its sentinel;
- a current holder excludes a simulated pre-#62 `O_EXCL` client;
- a simulated #62 advisory-only holder blocks current code;
- a current holder excludes a simulated #62 advisory-only client;
- a marked current crash sentinel is not reused through a live #62 advisory holder, but is recoverable after that holder releases;
- current clean release removes the historical visible sentinel;
- current process death releases OS ownership and a later current operation recovers marked residue;
- an empty/unrecognized preexisting sentinel is never auto-deleted and produces actionable failure;
- all current-current, pre-#62/current, and #62/current process tests pass on Linux, macOS, and Windows.

## Review correction

The first implementation draft used only the current sidecar plus the historical `O_EXCL` sentinel. Independent adversarial review rejected it because a #62 advisory-only checkout could still lock the historical path and enter concurrently. The corrected protocol therefore holds the historical-path advisory lock as an explicit third bridge and tests both directions.

## Conclusion

No portable observation can safely distinguish stale empty #62 residue from a live pre-#62 holder. Safe migration consequently requires fail-closed handling for ambiguous empty state and simultaneous cooperation with both historical exclusion mechanisms while current code is active. This deliberately accepts one-time manual recovery of ambiguous old residue in exchange for the core invariant: two materializer mutations must never run concurrently against the same install root.