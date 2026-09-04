# Local corpus materialization

**Status: experimental architecture reference for an exercised prototype.** The plugin ownership rules in `ref-plugin-boundary.md` remain normative.

## Goal

Agora must be able to expose corpora that cannot or should not be redistributed as pre-built artifacts. The common case is a corpus whose raw files are downloaded from an authoritative source or supplied locally by the user and then converted by third-party code.

The boundary is:

```text
resource -> source acquisition -> materializer -> local artifact -> consumer
```

A materializer is third-party executable code. Agora owns acquisition, execution constraints, integration metadata, artifact publication, and provenance; the materializer owns parsing, normalization, scholarly semantics, output construction, and converter-specific validation.

## Trust boundary

The prototype has two metadata layers:

1. Resource/catalog metadata may eventually refer only to a registered materializer id. Resource records must not contain executable code, shell snippets, executable URLs, or arbitrary command lines.
2. A trusted materializer plugin may contain `agora.materializer.json`, declaring acquisition modes, a Python module entry point, argument templates, and the expected artifact contract.

The current CLI does not yet prove that an arbitrary manifest path came from an Agora installation record. **Supplying `--manifest` is therefore the explicit trust decision in the prototype.** Automatic resource-to-materializer composition must bind the manifest to an Agora installation/approval record before it is added.

Contract v1 accepts only:

- `execution.type: python-module`;
- a syntactically valid Python module name;
- argument strings using only `{source}`, `{output}`, and `{source_revision}` placeholders;
- `execution.network: deny`;
- directory input;
- public credential-free HTTPS Git acquisition and/or an explicitly user-provided local directory;
- a declared output format and required relative output paths.

There is no shell, script/eval field, executable URL, arbitrary environment block, or resource-supplied argv.

The JSON Schema is authoritative for structural validation. Runtime code adds only cross-field/security checks that the schema does not express conveniently, such as duplicate materializer/acquisition ids and parsed URL credential checks.

## Acquisition

Agora acquires source data before launching the materializer.

### Git

Agora creates a temporary repository, fetches the declared ref with a bounded Git operation, checks out `FETCH_HEAD`, records the exact resolved commit, validates the declared subdirectory, and removes the checkout after materialization. Git runs with an isolated temporary home/config and without interactive credential prompts.

The resolved commit is available to the upstream CLI as `{source_revision}`. This lets a converter preserve its native provenance semantics without exposing `.git` inside the sandbox.

### User-local

For a local source directory Agora:

- validates declared globs and symlink policy;
- records only the directory basename rather than its absolute path;
- records a deterministic SHA-256 tree digest over relative paths and contents;
- records the containing Git `HEAD` when it can be detected locally, so `{source_revision}` can preserve converter provenance for a checked-out source tree as well.

The tree digest distinguishes equally named directories and detects edits even when the source is dirty or is not under Git.

## Preflight and side effects

Before any automatic network acquisition, Agora validates the manifest, final-output feasibility, and availability of the required OS sandbox backend. A bad destination or missing sandbox therefore fails before a Git fetch.

Automatic acquisition falls back to user-local mode only for acquisition/environment failures. A fetched source that violates the declared input contract is treated as a contract error rather than being hidden behind an interactive fallback.

## Execution

The materializer receives:

- a read-only source directory;
- a writable staging artifact directory;
- its trusted installed/plugin code;
- a filtered environment.

Agora launches the declared module directly with the current Python interpreter and never invokes a shell.

### Sandbox policy

Sandboxing fails closed by default.

- Linux: bubblewrap (`bwrap`) creates new namespaces, including an isolated network namespace; system/runtime/plugin/source mounts are read-only and output is read/write.
- macOS: `sandbox-exec` uses a deny-by-default profile; system/runtime/plugin/source/output paths receive the reads needed by Python/converters, only output/work receive writes, and network operations are denied.
- Other platforms: contract v1 refuses to run with sandbox mode `required`.

`--sandbox off` is explicit development/trust override only.

Both supported backends are exercised by `.github/workflows/materialization-sandbox.yml`. The E2E launches a real fixture through `sandbox="required"`, reads the source, writes and reopens output, verifies the artifact/provenance, and attempts to connect to a live loopback listener that must be denied by the sandbox.

The same workflow also exercises the pinned Pseudepigrapha-TF reference materializer on Linux: Agora acquires the pinned OCP source itself, runs the real converter under bubblewrap, and verifies that the exact resolved OCP commit survives through Agora provenance, the converter report, and generated Text-Fabric metadata. This is an integration smoke, not a duplicate of Pseudepigrapha-TF's semantic test suite.

The sandbox is defense in depth around code the user chose to trust; it is not a claim that arbitrary untrusted Python is safe.

## Transactional output

Converters never write directly into the requested final artifact path.

Agora creates a sibling staging directory on the same filesystem, runs the converter there, validates all required output paths, writes protected provenance, and only then atomically renames the staging directory to the requested destination. Converter failure, output-validation failure, or provenance failure removes staging and leaves an existing empty destination empty (or an absent destination absent).

`agora-materialization.json` is reserved for Agora and is created with exclusive/no-follow semantics after the converter exits, preventing a converter-created symlink from redirecting the provenance write.

## Provenance

A successful artifact records:

- materializer plugin id and self-declared version;
- deterministic SHA-256 identity of the importable plugin code tree;
- materializer id;
- source acquisition type;
- exact requested/resolved Git revision where applicable;
- deterministic local-source tree SHA-256 for user-local input;
- output format;
- sandbox backend;
- SHA-256 of the materializer manifest;
- UTC materialization timestamp.

The manifest hash is intentionally separate from the executable-code digest: changing `src/` without changing the manifest/version still changes artifact provenance.

## Consumer boundary

The materializer output format is independent of the eventual consumer. A converter may produce Text-Fabric, SQLite, DuckDB, or another registered local format. Resource-to-materializer selection, cache keys, and consumer hand-off remain a later integration layer.

The first reference implementation is `alexsosn/Pseudepigrapha-TF`:

```text
OCP XML -> pseudepigrapha-tf -> text-fabric -> Context-Fabric-compatible local artifact
```

Pseudepigrapha-TF already exposes `--upstream-commit`; its materializer manifest uses `{source_revision}` so the Agora path records the same immutable upstream commit rather than losing it when only `static/docs` is mounted as the source.

## Ownership

Agora owns:

- manifest contract/schema;
- source acquisition orchestration;
- integration-level input/output validation;
- sandbox/process launch;
- transactional local artifact publication;
- integration provenance.

The converter repository owns:

- parsing and normalization;
- domain semantics;
- output construction;
- converter-specific semantic validation.

If a converter produces an incorrect scholarly result when run directly without Agora, the fix remains upstream under `ref-plugin-boundary.md`.

## Prototype CLI

```bash
python scripts/agora_materialize.py \
  --manifest /path/to/trusted/plugin/agora.materializer.json \
  --materializer ocp-text-fabric \
  --output ~/.local/share/agora/artifacts/pseudepigrapha
```

For legally obtained local input:

```bash
python scripts/agora_materialize.py \
  --manifest /path/to/trusted/plugin/agora.materializer.json \
  --materializer ocp-text-fabric \
  --source /path/to/OCP/static/docs \
  --output ~/.local/share/agora/artifacts/pseudepigrapha
```

The final output path must be absent or an empty directory.

## Deliberately deferred

The prototype does not yet define:

- canonical installation/approval records for materializer plugins;
- a resource-registry reference to an approved materializer id;
- persistent artifact cache keys and retention;
- automatic consumer hand-off;
- Windows sandboxing;
- authenticated/click-through acquisition;
- CPU/RAM/disk quotas;
- a stable public artifact-format compatibility vocabulary.

Those belong to the next design phase after the source/materializer/artifact boundary is proven on both supported sandbox backends.
