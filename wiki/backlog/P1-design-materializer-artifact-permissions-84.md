# Design/implementation plan: private materializer artifact permissions (#84)

## Scope

Restore the historical POSIX privacy baseline for the directory that Agora
publishes as a local materializer artifact. Preserve every #83 sandbox and
transactional-publication property.

## Gate 1 — RED permission regression

Before production changes, add a focused unit test for
`_create_staging_output()`.

On POSIX:

1. create a temporary final destination parent;
2. temporarily set process umask to `0o022`, restoring it in `finally`;
3. call `_create_staging_output(final)`;
4. assert `stat.S_IMODE(staging.root.stat().st_mode) == 0o700`;
5. assert `stat.S_IMODE(staging.output.stat().st_mode) == 0o700`;
6. always clean up the staging root.

This must fail on current main because `output.mkdir()` produces `0755` under
umask `022` while the `mkdtemp()` root remains `0700`.

The permission-bit assertion is skipped on Windows; production code remains
portable.

Record the RED failure before the implementation commit.

## Gate 2 — minimal GREEN implementation

Change only the designated child creation:

```python
output.mkdir(mode=0o700)
```

Do not:

- chmod the destination parent;
- alter process umask in production;
- expose the destination parent to the sandbox;
- change Linux/macOS bind/profile rules;
- change the two-level staging topology;
- change `os.replace()` publication;
- normalize modes of converter-created files.

Run the focused test first, then the complete materialization test module.

## Gate 3 — integration tests

Run/observe all relevant exact-head checks available in Agora:

- Foundation/unit workflow;
- Linux materialization sandbox E2E;
- macOS materialization sandbox E2E;
- registered materializer install/materialization smoke where triggered.

Existing regressions for sibling staging, atomic rename, network isolation,
output-root substitution, failure cleanup, and destination-parent isolation must
stay green.

## Independent adversarial review

Review the exact frozen PR head independently of the implementation narrative.
Inspect at least:

- whether any path besides the publishable child changes mode;
- whether requested `0700` can be broadened by ordinary POSIX umask behavior;
- whether symlink/substitution guards still run after materializer execution;
- whether cleanup handles the private parent after output publication;
- whether `os.replace()` still preserves same-filesystem atomic publication;
- whether Linux/macOS sandbox writable surfaces are unchanged;
- whether Windows receives only the portable `mkdir(mode=...)` call and no
  unsupported permission assertion;
- whether tests could pass while inspecting a different directory than the one
  actually published.

Any material finding gets a failing regression before the fix, then a full
retest and a fresh exact-head review.

## Completion

After all exact-head gates are green and the independent review has no blocker:

- mark the PR ready/final;
- merge it;
- close #84 with the frozen-head test/review evidence;
- resume the highest-priority unblocked feature ticket. If the Burns upstream
  PR remains externally queued, continue another independent stability or
  ergonomics ticket rather than bypassing its final CI gate.
