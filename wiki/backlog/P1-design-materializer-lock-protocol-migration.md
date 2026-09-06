# Design: mixed-version-safe materializer installation locking

Issue: #63

Research: [`P1-research-materializer-lock-protocol-migration.md`](P1-research-materializer-lock-protocol-migration.md)

## Goals

- Preserve mutual exclusion with pre-#62 sentinel-file installers.
- Preserve mutual exclusion with the advisory-only implementation introduced by #62, in both directions.
- Preserve OS-backed current-current exclusion and process-death release.
- Stop current clean runs from leaving the historical visible lock path behind.
- Recover current-protocol crash residue only when neither current nor #62 code owns it.
- Fail closed, with actionable guidance, for ambiguous empty/unrecognized historical lock files.

## Non-goals

- Automatically deleting every stale pre-#62/#62 lock file. A live pre-#62 holder produces the same observable empty/unlocked state.
- Making old versions mutually safe with each other; pre-#62 and #62 already fail to coordinate if run directly together.
- Coordinating different machines that do not share the same filesystem.
- Changing materializer execution, source integrity, packaging, or registry semantics.

## Protocol

For a historical visible path such as `.source.lock`:

1. Current code acquires an OS-backed advisory lock on a stable sidecar such as `.source.lock.current`. This serializes current versions and supplies current-protocol liveness independent of historical semantics.
2. While holding the sidecar, current code attempts `O_CREAT|O_EXCL` on the original visible path.
3. On successful creation it writes the fixed current-protocol marker. File existence now excludes pre-#62 clients.
4. Before entering the critical section, current code also acquires an exclusive advisory lock on that same original visible path. This excludes #62 clients.
5. If the visible path already contains the exact current marker, do not unlink it first. Treat it as current crash residue, acquire the visible-path advisory lock, re-read/verify marker plus filesystem identity, and reuse that sentinel. A #62 process that attached to the residue therefore blocks recovery until it releases its advisory lock.
6. If the visible path is empty or unrecognized, do not delete or rewrite it. Poll until it disappears or the remaining timeout expires. The state may be a live pre-#62 holder even when no advisory lock exists.
7. During clean release, verify that the visible sentinel is still the owned filesystem object, unlink it while both advisory locks are still held, then release the visible advisory lock and finally the sidecar.

A #62 client may win the visible advisory lock in the small interval after current code creates the marker and before current code locks the visible path. That race is safe: current code waits and does not enter its critical section until #62 releases. The visible marker already exists during the wait, so pre-#62 arrivals remain excluded.

## Timeout semantics

The caller's `timeout` is one budget across all phases. Record one monotonic deadline before sidecar acquisition. Waiting for an ambiguous historical sentinel and acquiring the historical advisory lock use only the remaining budget.

A current process that acquires the sidecar near the deadline can still take an immediately available historical advisory lock with zero remaining wait; it must not gain a second full timeout window.

## Marker and ownership

Use the fixed ASCII marker:

```text
agora-materializer-lock-v3\n
```

The marker is a protocol discriminator, not proof of liveness. Liveness/ownership comes from OS locks. In particular, a marked sentinel is not safe to recover until the current process owns the sidecar **and** the historical-path advisory lock.

Capture `(st_dev, st_ino)` from the sentinel object and re-check that identity before cleanup. This is a best-effort refusal to unlink a replacement path if the sentinel was externally changed.

If marker initialization itself fails after `O_EXCL`, remove only the just-created matching filesystem object before propagating the error.

## TDD sequence

### RED 1 — pre-#62 interoperability

Emulate pre-#62 with `os.open(... O_CREAT|O_EXCL ...)` plus unlink-on-release.

Prove:

- a live pre-#62 holder blocks current code;
- current waits for a brief pre-#62 holder and enters only after it unlinks;
- a current holder causes a pre-#62 `O_EXCL` attempt to fail.

These tests fail against #62/current `main`, whose advisory-only lock does not coordinate with the old sentinel protocol.

### RED 2 — no downgrade residue and crash identity

Prove:

- the historical visible sentinel exists while current code owns the critical section and is absent after clean release;
- current crash residue contains the current marker and is recoverable by later current code;
- an empty/unrecognized historical sentinel is not auto-deleted and produces migration guidance.

### Review-driven RED 3 — #62 advisory interoperability

Independent review of the first GREEN draft found that sidecar + `O_EXCL` alone still allowed #62 advisory-only code to enter concurrently. Add a direct emulator of #62 using `portalocker.Lock` on the historical visible path.

Prove:

- a live #62 advisory holder blocks current code;
- a current holder blocks a #62 advisory-only arrival;
- a marked current crash sentinel is not recovered through a live #62 holder, but becomes recoverable after that holder releases.

### GREEN

Implement the sidecar + historical sentinel + historical advisory-lock bridge only in `scripts/agora_install_materializer.py`. Keep all public installer call sites unchanged.

### Documentation

Document:

- the three-part migration bridge;
- clean current runs no longer leave the historical visible sentinel;
- marked current crash residue is automatically recoverable only after historical advisory ownership is available;
- empty stale state from pre-#63 may require one-time manual removal **only after verifying no older installer process is running**.

## Verification gate

Run at minimum:

```bash
python -m unittest discover -s tests -p 'test_materializer_install*.py' -v
python scripts/validate_registry.py
python scripts/generate_marketplaces.py --check
python scripts/generate_context_fabric_catalog.py --check
```

The Foundation `materializer-install-locks` matrix must exercise both installation and migration test files and pass on Ubuntu, macOS, and Windows at the exact PR head.

## Independent adversarial review checklist

Review from a clean assumption set and try to falsify these points:

- Can a live pre-#62 holder and current holder ever both enter?
- Can a #62 advisory-only holder and current holder ever both enter, in either arrival order?
- Can a #62 process attach to marked current crash residue while current code deletes/replaces that path underneath it?
- Can current crash residue be confused with ambiguous empty historical state?
- Does any cooperative cleanup unlink a path owned by another protocol generation?
- Does a normal current release leave a historical visible sentinel that wedges pre-#62 clients?
- Is the timeout still one budget across sidecar, sentinel wait, and historical advisory acquisition?
- Does backend lock failure remain distinct from contention?
- Do Windows path/unlink semantics preserve the same protocol behavior?

Any blocker starts a fix → retest → fresh independent review loop before the PR is finalized.