# Research: preserve private permissions for published materializer artifacts

Issue: #84

## Scope

This investigation is limited to Agora-owned filesystem permissions at the materializer staging/publication boundary introduced by #83. It does not change third-party converter behavior, output semantics, or a converter's own choices for individual file modes.

## Current and historical behavior

Before #83, `_create_staging_output(final)` returned the directory created directly by `tempfile.mkdtemp(..., dir=final.parent)`. That staging directory was the object later atomically published with `os.replace(staging_output, final_output)`. On POSIX, `mkdtemp()` creates a private directory with mode `0700`, independent of a normal permissive directory-creation default.

#83 introduced a private workspace so sandboxed converters can create sibling staging paths without seeing the user's real destination parent. The workspace root still comes from `mkdtemp()` and remains private, but the object now published is its `output/` child:

```text
.<artifact>.agora-stage-XXXX/   <- mkdtemp, private
  output/                       <- Path.mkdir(), later published
```

`Path.mkdir()` without an explicit restrictive mode requests the platform/default directory mode (subject to umask). On a common `022` umask the child is `0755`. `os.replace(staging.output, final_output)` renames that directory; it does not recreate it with the old `mkdtemp()` permissions. #83 can therefore broaden the published artifact directory's local visibility even though its temporary parent was private while the converter ran.

## Security and compatibility invariant

The topology change from #83 should not silently broaden the historical permission baseline of the published artifact. The designated output child should be created with mode `0700` on POSIX, matching the directory that Agora historically published.

This is a construction-time invariant. A trusted materializer can still call `chmod()` on paths it controls; sandboxing is defense in depth and the current contract does not attempt to police every converter-created file mode after execution. Expanding this ticket into recursive permission normalization would create a new artifact policy and is out of scope.

## Cross-platform behavior

Passing `mode=0o700` to `Path.mkdir()` is portable Python. POSIX applies the mode subject to umask; because `0700` contains no group/other bits, a umask cannot broaden it. Windows does not expose a directly equivalent POSIX permission contract, so the regression assertion should be skipped there rather than inventing Windows ACL semantics.

## Interaction with #83

The fix must leave these #83 properties unchanged:

- the workspace root is a sibling of the final destination on the same filesystem;
- Linux binds only that private workspace read-write at `/agora-output`;
- macOS grants write access only to that private workspace and the work directory;
- `{output}` is the workspace's `output/` child;
- sibling staging and same-filesystem `os.replace()` remain supported;
- host-side output validation, protected provenance creation, final atomic publication, and cleanup remain unchanged.

Changing only the creation mode of `output/` satisfies the permission invariant without altering mount topology or publication sequencing.

## TDD implication

A focused POSIX test should inspect both the `mkdtemp()` root and its publishable `output/` child immediately after `_create_staging_output()` and require `0700` for both. Against #83/current `main`, the root should pass and the child should fail, isolating the regression before production code is touched.

## Conclusion

The smallest correct fix is explicit private creation of the designated child (`output.mkdir(mode=0o700)`) plus the POSIX regression. No converter, schema, registry, sandbox profile, or publication algorithm change is required.