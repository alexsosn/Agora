# Research: private permissions for published materializer artifacts (#84)

## Question

Did the staging-topology change from #83 broaden POSIX permissions on the
directory that is eventually published as a materializer artifact, and what is
the narrowest Agora-owned fix that restores the historical privacy invariant
without changing sandbox topology or converter behavior?

## Baseline

Research was performed against Agora main commit
`122b27d9326a57f464a7ce6f610385e6d6182999` and merged PR #83.

Before the #83 topology change, the directory ultimately published as the
artifact was created directly by `tempfile.mkdtemp()`. Python documents and
implements `mkdtemp()` as a private temporary directory; on POSIX this yields
mode `0700` independent of the ordinary process umask.

PR #83 introduced a necessary two-level staging layout:

- a private `mkdtemp()` staging root on the destination filesystem;
- a designated `output/` child inside that root;
- only the staging root is exposed to the sandbox as writable;
- the user-selected destination parent is not exposed read-write;
- the designated output child is checked against substitution/redirect attacks;
- after validation/provenance, `os.replace(staging.output, final_output)`
  publishes the child atomically on the same filesystem.

This topology is required for materializers that create sibling staging
locations or use same-filesystem atomic rename internally and must remain
unchanged.

## Current permission regression

Current `_create_staging_output()` does:

```python
root = Path(tempfile.mkdtemp(...)).resolve()
output = root / "output"
output.mkdir()
```

The staging root retains the private `0700` semantics of `mkdtemp()`. The child
uses ordinary `mkdir()` defaults (`0o777` masked by the process umask). Under the
common POSIX umask `022`, that creates `0755`.

`os.replace()` renames the directory object; it does not recreate it with the
permissions of its destination parent. Consequently a successfully published
artifact can retain the broader `0755` mode. On a multi-user host this can make
the artifact directory searchable/readable by users who could not traverse the
historical private staging directory.

This is Agora-owned publication/security behavior. Third-party materializer
file modes and the permissions of files created *inside* the output directory
are not part of this narrow regression unless an existing contract separately
requires them.

## Desired invariant

On POSIX, immediately after `_create_staging_output(final)`:

- `staging.root` is `0700`;
- `staging.output` is `0700`.

The output child must start no broader than the historical published-directory
baseline. This preserves private directory traversal after the child is renamed
to the final artifact path.

The test should set a known umask (`022`) temporarily so it deterministically
reproduces the current regression rather than depending on the CI runner's
ambient umask. The original umask must be restored in `finally`.

On Windows, POSIX permission-bit semantics are not a reliable contract. The
production change should use a portable `Path.mkdir(mode=...)`; the mode
assertion should be POSIX-only.

## Candidate fixes

### `output.mkdir(mode=0o700)` — preferred

This is the smallest production change. POSIX applies the requested mode masked
by the umask; because `0700` contains no group/other bits, a normal umask cannot
broaden it. It preserves the existing path, same-filesystem topology, and
sandbox mappings.

It also remains a valid portable call on Windows, where the mode argument has
platform-specific semantics and the test does not assert POSIX bits.

### `output.mkdir(); output.chmod(0o700)`

This creates a window where the directory can have broader permissions and adds
an unnecessary second filesystem operation. It is inferior to requesting the
correct permissions at creation time.

### Change process umask globally

Rejected. A process-global umask would affect materializer-created files and
other concurrent filesystem operations, widening the scope far beyond the
regression.

### Publish the private staging root again

Rejected. It would undo #83's sandbox/workspace topology and break the
same-filesystem sibling-staging behavior that #83 intentionally established.

## Verification surface

The deterministic unit regression should import `_create_staging_output` and
assert both root and publishable child modes under a known umask on POSIX.

After the minimal fix, rerun:

- focused materialization tests;
- Foundation/unit suite;
- real Linux and macOS materialization-sandbox workflows if triggered/available;
- registered materializer smoke, because publication is shared infrastructure.

The exact final head then receives a logically independent adversarial review
focused on permission broadening, writable-surface changes, destination-parent
exposure, cleanup, and whether the fix accidentally changes #83's atomic
publication/sandbox topology.

## Conclusion

The regression is confirmed in current Agora code. The correct narrow repair is
to create the designated publishable `output/` directory with mode `0700` and
test that invariant explicitly on POSIX. No third-party materializer semantics,
source acquisition, network policy, or composition behavior needs to change.
