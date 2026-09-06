# Design: mixed-version-safe materializer installation locking

Issue: #63

Research: [`P1-research-materializer-lock-protocol-migration.md`](P1-research-materializer-lock-protocol-migration.md)

## Goals

- Preserve mutual exclusion with pre-#62 sentinel-file installers.
- Preserve OS-backed current-current exclusion and process-death release.
- Stop current clean runs from leaving the legacy-visible lock path behind.
- Recover crash residue created by this new protocol without guessing about legacy state.
- Fail closed, with an actionable message, for ambiguous empty/unrecognized legacy lock files.

## Non-goals

- Automatically deleting every stale pre-#62/#62 lock file. That cannot be made safe when a live pre-#62 holder produces the same observable state.
- Coordinating different users or machines that do not share the same filesystem.
- Changing materializer execution, source integrity, packaging, or registry semantics.

## Protocol

For a requested visible path such as `.source.lock`:

1. Current versions first acquire an OS-backed advisory lock on a stable sidecar path such as `.source.lock.current`.
2. While holding the sidecar, they attempt to create the original visible path using `O_CREAT|O_EXCL`.
3. On successful creation they write a fixed current-protocol marker and enter the critical section.
4. On clean release they unlink the visible path, then release the sidecar advisory lock.
5. If the visible path already exists:
   - if its contents are exactly the current-protocol marker, the sidecar proves no current holder is alive (we already own it), so the sentinel is recoverable current crash residue: unlink and retry;
   - if its contents are empty or unrecognized, do not delete it. Poll until it disappears or the remaining timeout expires.
6. A persistent ambiguous sentinel raises `MaterializerInstallError` explaining that it may belong to a pre-migration installer and may only be removed after confirming no older materializer operation is running.

The existing portalocker error split remains: ordinary sidecar contention reports another materializer operation; backend lock failures remain distinct.

## Timeout semantics

Treat the caller's `timeout` as one budget for both phases. Record a monotonic deadline before acquiring the sidecar; after the sidecar is obtained, only the remaining budget may be spent waiting for a legacy sentinel to disappear.

This avoids surprising waits of roughly `2 * timeout` during a transition from a current holder to a legacy holder.

## Marker

Use a fixed short ASCII marker, for example:

```text
agora-materializer-lock-v3\n
```

It is an internal protocol discriminator, not an ownership claim or PID record. A current holder's liveness is determined by the sidecar OS lock. The marker only distinguishes files created by this protocol from ambiguous legacy files.

If marker initialization fails after the `O_EXCL` create, close and remove the just-created visible sentinel before propagating the error.

## TDD slices

### RED 1 — legacy holder exclusion

Add a helper that emulates the pre-#62 implementation with `os.open(... O_CREAT|O_EXCL ...)`, holds the sentinel until signalled, then unlinks it.

Tests:

- current `_lock(timeout=short)` fails while the legacy holder remains live;
- current `_lock(timeout=long)` waits and succeeds after a brief legacy holder releases;
- while current `_lock` is held, a legacy `O_EXCL` acquire gets `FileExistsError`.

These tests must fail against current `main`, where the advisory-only implementation can enter beside a legacy holder.

### RED 2 — no downgrade residue

Assert that the visible sentinel exists during a current critical section and is absent immediately after clean release. This fails against current `main`, which deliberately leaves the file behind.

### RED 3 — current crash recovery and ambiguous fail-closed

- Crash a child from inside current `_lock`; assert the marked visible sentinel remains, then a new current `_lock` recovers and succeeds.
- Seed an empty legacy sentinel and assert it is not removed automatically; after timeout the error mentions legacy/pre-migration recovery and the file still exists.

### GREEN

Implement sidecar + compatibility sentinel logic only in `scripts/agora_install_materializer.py`. Keep public call sites unchanged.

### Documentation

Update materializer installation documentation to state:

- lock compatibility across older checkouts;
- clean current runs no longer leave the old-visible sentinel;
- an empty stale file from pre-#63 may require one-time manual removal **only after verifying no older installer process is running**.

## Verification gate

Run at minimum:

```bash
python -m unittest discover -s tests -p 'test_materializer_installation.py' -v
python scripts/validate_registry.py
python scripts/generate_marketplaces.py --check
python scripts/generate_context_fabric_catalog.py --check
```

The existing Foundation cross-platform `materializer-install-locks` matrix must pass on Ubuntu, macOS, and Windows at the exact PR head.

## Independent adversarial review checklist

Review from a clean assumption set and try to falsify these points:

- Can a live pre-#62 holder and current holder ever both enter?
- Can an old `O_EXCL` client enter while current code is inside the critical section?
- Can current crash residue be confused with a live legacy holder?
- Does any cleanup unlink a path that might have been replaced by another process?
- Does a release or exception leave a permanent visible sentinel?
- Do timeout/error classifications remain accurate?
- Do Windows path/unlink semantics preserve the protocol?

Any blocker found here starts a fix → retest → fresh review loop before the PR is finalized.
