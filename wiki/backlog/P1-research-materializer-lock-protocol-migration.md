# Research: materializer lock protocol migration safety

Issue: #63

Checked: 2026-09-06

## Question

How can materializer installation remain mutually exclusive when Agora checkouts sharing one install root may use the pre-#62 sentinel protocol, the #62 advisory-only protocol, or the current implementation?

This is Agora-owned installation behavior, so the fix belongs in Agora.

## Protocols already in the field

### Pre-#62

The original `_lock` acquired ownership by creating the visible lock path with `O_CREAT|O_EXCL`, kept the file descriptor open, and unlinked the path on normal release. It took no advisory lock and wrote no owner metadata.

Consequences:

- another pre-#62 process is excluded by pathname existence;
- an advisory-lock process is not excluded by a live pre-#62 holder on POSIX;
- process death can leave an empty sentinel indefinitely.

### #62

PR #62 replaced sentinel ownership with `portalocker.Lock(path, mode="a", EXCLUSIVE|NONBLOCKING)`. The OS releases ownership on process death, while the pathname remains.

Consequences:

- #62 processes coordinate correctly with each other;
- a live pre-#62 holder does not exclude a #62 process because the old holder takes no advisory lock;
- an empty #62 lock file permanently excludes a later pre-#62 `O_EXCL` client.

Portalocker documents the relevant platform behavior:

- POSIX locking is advisory: https://portalocker.readthedocs.io/en/latest/platforms.html
- Windows exclusive locking is mandatory and uses `msvcrt` by default: https://portalocker.readthedocs.io/en/latest/platforms.html
- `Lock` releases/closes its handle but leaves the file in place: https://portalocker.readthedocs.io/en/latest/lock-types.html#lock

## Irreducible ambiguity

An empty, unlocked historical path can mean any of:

- a live pre-#62 holder;
- stale pre-#62 crash residue;
- stale #62 residue.

The live pre-#62 process writes no PID/owner record and takes no advisory lock. Portable filesystem/advisory-lock observations therefore cannot distinguish those states. Automatically deleting an empty unlocked file can delete a live old holder's sentinel and admit concurrent mutation.

## Review of the first bridge design

The first implementation attempted transparent three-generation interoperability:

1. lock a new current-only sidecar;
2. create the historical pathname with `O_EXCL` to exclude pre-#62;
3. advisory-lock the historical pathname to exclude #62;
4. remove the historical pathname on current clean release so pre-#62 could run again later.

Independent adversarial review found two protocol defects.

First, sidecar + sentinel alone did not exclude #62; current code also had to advisory-lock the historical path.

Second, adding that advisory lock made clean unlink unsafe. On POSIX a #62 waiter can already have the old inode open while waiting for the lock. If current code unlinks the pathname before releasing, the #62 waiter may later acquire the now-unlinked inode while pre-#62 creates a new pathname and enters concurrently. On Windows, deleting an open/locked file is additionally not a portable assumption.

There is no cooperative operation by which current code can know that no #62 waiter has already opened the historical inode. Transparent three-generation handoff is therefore not safely implementable with these historical protocols.

## Selected direction: one-way migration boundary

The safe protocol is intentionally asymmetric.

### Before the boundary

If the historical path is absent, current code creates it with `O_CREAT|O_EXCL` and writes the fixed ASCII byte marker:

```text
agora-materializer-lock-v3
```

The marker deliberately contains no newline. It is written with `os.write` rather than a text stream so its byte representation and byte length are identical on POSIX and Windows; text newline translation must not change the protocol discriminator.

The create race coordinates with pre-#62: whichever creates the pathname first keeps the other generation out. If current code encounters an empty or unrecognized existing path, it waits for a live pre-#62 holder to remove it and otherwise fails closed with manual-recovery guidance. It never guesses that an empty unlocked file is stale.

### After the boundary

The marked historical path is persistent. Current code never removes it automatically.

Current code and #62 both acquire the OS advisory lock on that same historical path, so they are mutually exclusive in either arrival order. A current crash needs no sentinel cleanup: the kernel releases the advisory lock while the marker remains ready for reuse.

Pre-#62 `O_EXCL` clients cannot run after the marker has been established. That is deliberate. A downgrade across the boundary requires manual removal of the marker only after confirming that no #62/current materializer operation is running.

## Windows verification constraint

The first one-way implementation still read the v3 marker through a fresh file handle **before** calling `portalocker.Lock.acquire()`. That is harmless on ordinary POSIX filesystems because the lock is advisory, but it is wrong on Windows: portalocker's exclusive Windows lock is mandatory, so a separate read of a byte range owned by a live modern holder can block before Agora's timeout/retry machinery runs.

Exact-head Windows CI exposed both consequences of the first one-way implementation: lock tests spent repeated full timeout windows misclassifying the current marker, and live holder processes could not enter reliably. The newline-bearing text marker also introduced an avoidable platform-specific representation risk. A bounded lock API cannot perform any potentially mandatory read before it has acquired ownership, and the protocol marker must have one byte representation on every supported OS.

The safe acquisition order on a migrated root is therefore:

1. use pathname metadata that does not read the locked bytes (specifically regular-file size) to distinguish the known empty legacy state from a candidate v3 marker object;
2. for a candidate marker-sized file, acquire the advisory lock on that historical path using the remaining timeout budget and a readable binary handle;
3. verify the exact marker through the **already acquired lock handle**, not a second handle;
4. compare the locked handle's filesystem identity with the current pathname before entering, so a replacement while waiting cannot silently split ownership across two inodes.

A zero-length or other non-candidate legacy file remains in the pre-migration waiting/fail-closed path and is never advisory-locked by current code; that matters on Windows because locking such a live pre-#62 file could prevent the old holder from unlinking it on normal release.

## Race analysis

### Pre-#62 wins creation first

Current sees an empty/unrecognized path and waits. If the old holder releases normally and unlinks it, current may then create the v3 marker. If the path persists, current fails closed.

### Current wins creation first

The marker exists before current enters the critical section, so pre-#62 arrivals fail `O_EXCL`. Current then advisory-locks that same path. A #62 process may acquire the advisory lock first in the small interval between marker creation and current locking; that is safe because current has not entered yet and waits for #62 to release.

### #62 creates an empty path first

Current cannot distinguish a live/stale #62 file from pre-#62 state, so it fails closed rather than converting it automatically. The user may remove the empty file once no old operation is active, after which current establishes the persistent marker.

### Current or #62 crashes after migration

The persistent marker remains. OS advisory ownership is released by process death, so another #62/current process can acquire the same path safely. No pathname deletion or inode replacement is needed.

## Migration and downgrade rules

1. **Empty/unrecognized historical file:** never auto-delete. Confirm no older operation is running, then remove it once to migrate.
2. **Marked v3 file:** normal persistent state, not stale garbage. Do not remove it during ordinary current/#62 use.
3. **Deliberate downgrade to pre-#62:** first ensure no #62/current operation is running, then remove the marked file manually. Running pre-#62 concurrently with modern code is unsupported after this boundary.

## Required regression evidence

The implementation should prove:

- a live pre-#62 holder blocks current code;
- current can wait for a brief pre-#62 holder, then establish the persistent marker;
- once the marker exists, a pre-#62 `O_EXCL` client remains excluded even after current releases;
- a live #62 advisory holder blocks current code;
- a live current holder blocks a #62 advisory client;
- a short current timeout remains short on Windows rather than blocking in marker inspection;
- a current waiter succeeds after a live holder releases within its timeout;
- current clean release leaves the exact v3 marker in place;
- a current crash leaves the same marker and a later current operation reuses it without deleting/replacing it;
- a #62 acquire/release against an established marker leaves the marker intact;
- empty/unrecognized historical state remains fail-closed and is never automatically deleted;
- the cross-process suite passes on Linux, macOS, and Windows.

## Conclusion

A safe transparent bridge back to pre-#62 after modern code has used the root is impossible because queued #62 advisory waiters cannot be observed before pathname deletion. The robust policy is a one-way migration: establish a persistent self-identifying historical path, serialize #62/current processes with its advisory lock, deliberately exclude pre-#62 clients until an explicit quiescent downgrade, and perform marker verification only through the acquired lock handle so Windows mandatory locking cannot bypass the timeout contract.
