# Research: materializer sandbox output mount compatibility (#82)

## Scope

Issue #82 is an Agora-owned materializer-execution compatibility problem. It was exposed by the Pseudepigrapha-TF `v0.1.0` release while validating Agora PR #80, but the defect is generic to converters that use a normal sibling-staging + atomic-rename pattern for output files.

This research is limited to Agora's sandbox topology, transactional publication, and integration contract. It does not propose changes to Pseudepigrapha-TF's writer or scholarly behavior.

## Observed failure

The `Pseudepigrapha-TF reference materialization` job for Agora PR #80 reached the released converter successfully and failed during output serialization:

```text
OSError: [Errno 18] Invalid cross-device link:
'/.pseudepigrapha-tf-.../otext.tf' -> '/output/otext.tf'
```

The bubblewrap command in the same job contains:

```text
--bind <Agora host staging directory> /output
...
pseudepigrapha_tf.cli convert /input --output /output ...
```

The converter creates a temporary staging directory beside the requested output directory and installs staged files with `os.replace()`. Inside the Linux sandbox, the sibling temporary directory is created under `/`, while `/output` is a separate bind mount. Linux therefore reports `EXDEV` even though both paths originate from one host filesystem outside the sandbox.

The converter installation, source acquisition, source revision propagation, semantic audit, and pre-write conversion phases all completed before this failure. The failure is specifically an execution-filesystem topology mismatch.

## Current Agora contract

`scripts/agora_materialize.py` currently has two staging layers conceptually collapsed into one directory:

1. `_create_staging_output(final_output)` creates a sibling directory in `final_output.parent`; this guarantees the host can publish with `os.replace(staging_output, final_output)` on the same host filesystem.
2. Linux `_build_linux_sandbox()` bind-mounts that exact staging directory as `/output`.
3. macOS `_build_macos_sandbox()` grants write access to the exact staging output and work directory, but not to `output.parent`.

The architecture reference promises a writable staging artifact directory and host-side transactional publication. It does not require the converter-visible output directory itself to be a mount point or prohibit converter-private temporary siblings.

## Compatibility requirement

A materializer should be able to use common local-filesystem output patterns inside the writable artifact workspace, including:

- direct writes into output;
- reopen/read-after-write;
- temporary files inside output;
- a temporary sibling directory under `output.parent`;
- atomic `os.replace()`/rename from that sibling into output.

Agora should not force a converter to know that its output is a sandbox mount boundary.

## Linux analysis

### Current topology

Conceptually:

```text
sandbox /          -> sandbox root filesystem
sandbox /output    -> bind mount of host staging_output
```

A converter that creates `/tmp-stage` beside `/output` crosses from the sandbox root filesystem into the `/output` bind mount when renaming.

### Unsafe simple fix: bind the user's output parent

Binding `final_output.parent` read-write and passing a child path would restore same-filesystem rename semantics, but it would expose unrelated sibling files/directories in the user's requested destination parent to third-party converter code. That violates the existing least-authority sandbox design and is rejected.

### Preferred topology: private output workspace

Create a dedicated temporary directory on the same host filesystem as `final_output`, then create the converter output as a child:

```text
<final parent>/.<name>.agora-stage-XXXX/   # private host staging parent
  output/                                  # converter-visible output
```

Bind only the private staging parent into bubblewrap:

```text
--bind <private staging parent> /agora-output
```

Pass `/agora-output/output` as `{output}`.

Inside the sandbox, both `/agora-output/output` and any sibling temporary directory under `/agora-output` belong to the same bind mount, so rename/replace stays on one filesystem. The converter receives write access only to the private staging parent, not the user's real output parent.

After successful converter execution, Agora validates `<private staging parent>/output`, writes reserved provenance there, and atomically renames that child to `final_output`. Because the private staging parent itself was created in `final_output.parent`, this host-side rename retains the current same-filesystem guarantee.

## macOS analysis

The current `sandbox-exec` profile grants writes under the output directory itself and the separate Agora work directory. A converter that creates a sibling next to output requires write permission on `output.parent`, so the same private staging-parent design should be used consistently:

- grant reads/writes under the private output parent;
- pass its `output` child to the converter;
- do not grant writes to the real requested output parent except indirectly through Agora after the sandboxed process exits.

This keeps the behavioral contract aligned across Linux and macOS even though their sandbox mechanisms differ.

## Transactionality and cleanup

The private parent should be created under `final_output.parent`, with an empty `output` child. On success:

1. converter exits successfully;
2. validate required output paths in the child;
3. write `agora-materialization.json` in the child using existing exclusive/no-follow logic;
4. `os.replace(child, final_output)`;
5. remove the now-empty private parent.

On converter, validation, or provenance failure, remove the entire private parent. The requested final output remains absent or remains the pre-existing empty directory according to current behavior.

The implementation must account for the existing case where `final_output` already exists as an empty directory. `os.replace(nonempty_staging_dir, existing_empty_dir)` is the current publication mechanism and should remain covered by tests on supported platforms.

## Security review of the proposed surface

The writable surface grows from one directory (`output`) to one private parent containing only Agora-created materializer staging state. It does **not** grow to the user's actual parent directory.

The converter can create arbitrary siblings of `output` inside that private parent. Those siblings are disposable and never published. Agora should clean the entire parent after execution. Required-path validation and provenance reservation continue to operate only on the designated `output` child.

Network isolation, source/plugin read-only mounts, filtered environment, and host-side output validation remain unchanged.

## Alternatives considered

### Ask/fix every converter to stage inside output

Rejected as an Agora integration strategy. Atomic sibling staging is conventional filesystem behavior and the artificial cross-device boundary is introduced by Agora. Requiring every third-party materializer to avoid it would leak sandbox implementation details into upstream code.

### Catch `EXDEV` and copy files in Agora

Rejected. The failure occurs inside third-party code before Agora regains control. Intercepting or emulating converter filesystem operations would be invasive and brittle.

### Mount a second writable directory only for temp files

Insufficient unless the converter is explicitly told to use it. Existing converters reasonably derive staging paths from `output.parent`.

### Disable sandbox for affected materializers

Rejected. It weakens the trust boundary to work around an Agora-owned mount-layout bug.

## Pseudepigrapha-TF-specific observations relevant to PR #80

The published `v0.1.0` manifest changes the pinned OCP source from the pre-release snapshot to `c939dcbacad78c5d18d2c4282cad23c47e19ac07`. Agora's reference-materialization workflow still hard-codes an older `OCP_COMMIT`, so PR #80 also needs to remove or update that stale expectation before it can be finalized.

Likewise, `tests/test_materializer_installation.py` currently hard-codes the old registered Pseudepigrapha-TF commit. A registry pin update must update that test expectation (or make the assertion derive from release metadata in a deterministic way).

These are separate from the sandbox topology defect, but they explain additional red CI expected from the release-pin change.

## Research conclusion

Use a dedicated private staging parent on the final destination filesystem and expose that parent, not the output child or real destination parent, as the sandbox's writable output workspace. Pass a designated child directory as `{output}`. This preserves least authority, enables sibling atomic staging, and retains Agora's host-side transactional publication semantics.

Implementation should be preceded by deterministic construction tests plus a real-sandbox regression fixture that reproduces the sibling `os.replace()` pattern on Linux and macOS.