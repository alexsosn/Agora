# Plan: materializer sandbox output workspace (#82)

## Objective

Preserve Agora's transactional output publication while making the converter-visible output path behave like an ordinary directory with a writable same-filesystem parent. The sandbox must expose only disposable Agora staging state, never the user's real destination parent.

## Design

### Host staging layout

Replace the single staging directory with a private staging workspace created in the requested final output parent:

```text
<final parent>/.<final name>.agora-stage-XXXX/
  output/
```

Represent it explicitly in code so cleanup ownership is unambiguous:

```python
@dataclass(frozen=True)
class StagingOutput:
    root: Path
    output: Path

    def cleanup(self) -> None: ...
```

Creation contract:

- `root` is created by `tempfile.mkdtemp(..., dir=final.parent)`, so it is on the final destination filesystem;
- `output = root / "output"` is created empty;
- the root is private/disposable and contains no user files.

Publication contract:

1. run converter against `StagingOutput.output`;
2. validate only `output`;
3. write reserved Agora provenance only inside `output`;
4. atomically `os.replace(output, final_output)`;
5. remove the now-empty staging root;
6. on every failure path, recursively remove `root`.

### Linux bubblewrap

`_build_linux_sandbox()` will receive the designated output child. Its parent is guaranteed by the host to be the private staging root.

Bind the private parent, not the child:

```text
--bind <staging_output.parent> /agora-output
```

Render `{output}` as:

```text
/agora-output/output
```

Do not bind the requested final-output parent.

The sandbox path name should be a constant (for example `/agora-output`) so construction tests can assert the exact trust surface.

### macOS sandbox-exec

Grant read/write access to the private staging parent rather than only the designated output child. Render `{output}` as the real designated child path, since sandbox-exec does not create a mount namespace.

The user destination parent remains outside the write allow-list; the private staging root happens to be physically located inside it, but the profile grants the exact private subtree only.

### Non-sandbox execution

Use the same private staging parent/output child layout. This keeps host transactionality and cleanup identical across sandbox modes and gives unsandboxed converters the same ordinary sibling-staging filesystem semantics.

## TDD sequence

### RED 1 — construction contract

Update/add deterministic tests in `tests/test_materialization.py` before production code:

- Linux command binds `output.parent` to `/agora-output` and renders `{output}` as `/agora-output/output`;
- Linux command does not bind a higher-level user destination parent supplied by the fixture;
- macOS profile grants write access to the private output parent;
- macOS profile continues to deny network;
- command/profile still exposes source/plugin as read-only.

These tests should fail against current code because current Linux binds the output child to `/output` and current macOS grants only the child.

### RED 2 — real sandbox sibling-rename regression

Add a real-sandbox fixture in `tests/test_materialization_sandbox_e2e.py` that:

- computes `stage = output.parent / ".fixture-stage"`;
- creates the sibling staging directory;
- writes `otype.tf` and `oslots.tf` there;
- `os.replace()`s each file into output;
- removes the temporary sibling directory;
- exits successfully.

Run through `materialize(..., sandbox="required")` on the existing Linux/macOS matrix. Against current code:

- Linux should reproduce `EXDEV` because the sibling and `/output` are different mounts;
- macOS should be denied when attempting to create the sibling beside output.

### RED 3 — cleanup/transactionality

Extend deterministic unit coverage so a converter failure leaves no `.<name>.agora-stage-*` private workspace and does not publish partial output. Preserve the existing pre-existing-empty-destination case.

## Implementation gate

After RED evidence is committed:

1. add `StagingOutput` (or an equivalently explicit private-workspace abstraction);
2. change staging creation/publication/cleanup in `materialize()`;
3. change Linux sandbox mount + rendered output path;
4. change macOS write profile to the private staging parent;
5. update architecture documentation;
6. make no upstream converter changes.

Keep the patch narrowly scoped; do not redesign acquisition, installation, manifest schema, or network policy.

## Test gate

Required deterministic commands:

```bash
python -m unittest tests.test_materialization -v
python -m unittest tests.test_materialization_sandbox_e2e -v
python -m unittest discover -s tests -v
python scripts/validate_registry.py
python scripts/generate_marketplaces.py --check
```

CI evidence required:

- Foundation relevant unit jobs;
- `Materialization sandbox E2E` real sandbox jobs on Linux and macOS;
- after merge/rebase into PR #80, released Pseudepigrapha-TF reference materialization must pass the output-writing phase.

## Independent adversarial review gate

Freeze the candidate head and review it independently against `CONTRIBUTING.md`, `AGENTS.md`, `ref-local-materialization.md`, `agora-pr-review`, and `agora-plugin-review`.

The review must specifically attempt to falsify:

- that the real destination parent is not exposed read-write;
- that the private parent cannot cause publication outside the requested final path;
- that cleanup handles converter/validation/provenance failures;
- that host-side final publication remains same-filesystem and atomic;
- that macOS profile permissions do not accidentally widen beyond the private subtree;
- that Linux mount layout does not introduce another mount boundary between converter sibling staging and output;
- that network/source/plugin protections remain unchanged;
- that tests exercise Agora-owned integration behavior rather than Pseudepigrapha-TF internals.

Any material finding returns the PR to implementation/test and requires a fresh review of the new head.

## Follow-up to PR #80

Once #82 is merged, revise #80 to:

- update the deterministic expected Pseudepigrapha-TF registry commit;
- derive or update the reference OCP source revision expected by the integration smoke;
- rerun the released reference materialization on the fixed sandbox topology;
- perform a fresh independent review before merge.

Issue #81 (automatic materializer release discovery/pin PRs) resumes only after the released pin is installable/materializable through Agora.