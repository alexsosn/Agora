# Plan: preserve private materializer output permissions

Issue: #84
Research: `wiki/backlog/P1-research-materializer-private-output-mode-84.md`

## Goal

Restore the pre-#83 privacy baseline for the directory that Agora publishes as a materialized artifact, without changing the private-workspace sandbox topology added by #83.

## Ownership

Agora owns staging-directory construction and final artifact publication. This plan changes no third-party materializer parsing, output semantics, or scholarly behavior.

## TDD sequence

### RED

Add a POSIX-only regression to `tests/test_materialization_staging_security.py`:

1. create a final artifact path under a temporary directory;
2. temporarily force `umask 022`, restoring the previous umask immediately after staging creation;
3. call `_create_staging_output(final)`;
4. require the staging root mode to be `0700`;
5. require the publishable `staging.output` child mode to be `0700`;
6. always clean the staging workspace.

Expected current-main result: root passes while the output child is `0755`, because plain `Path.mkdir()` requests `0777` and the forced `022` umask removes only write bits for group/other.

### GREEN

Change only `_create_staging_output()`:

```python
output.mkdir(mode=0o700)
```

No sandbox command/profile, validation, provenance, cleanup, or `os.replace()` behavior should change.

### Focused tests

Run/observe:

- `tests/test_materialization_staging_security.py`;
- existing materialization unit tests;
- real Linux/macOS sandbox E2E, including sibling staging + atomic replace;
- registered materializer install smoke;
- Foundation.

## Review gate

Freeze the exact final head after CI is green. A logically independent adversarial review must re-derive #84 from current `main` and inspect:

1. whether the change actually restores the historical published-directory privacy baseline;
2. whether it accidentally changes the sandbox writable surface;
3. whether success/failure cleanup and atomic publication are untouched;
4. whether the test is deterministic and meaningful on POSIX, restores process umask, and does not assert fake Windows ACL semantics;
5. whether any broader recursive permission policy has been introduced without requirement;
6. exact-head CI status and current-main ancestry.

## Acceptance mapping

- private root/output modes: focused RED/GREEN regression;
- #83 atomic sibling staging: existing real sandbox E2E;
- destination-parent isolation: existing deterministic sandbox construction tests;
- cleanup/provenance: existing staging security/materialization tests;
- portability: POSIX assertion skipped on Windows, production `mkdir(mode=...)` remains portable;
- final correctness: exact-head Foundation + relevant materialization workflows + independent review.
