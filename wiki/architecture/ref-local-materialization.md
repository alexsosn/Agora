# Local corpus materialization

**Status: experimental architecture reference for an exercised prototype.** The plugin ownership rules in `ref-plugin-boundary.md` remain normative.

## Goal

Agora must be able to expose corpora that cannot or should not be redistributed as pre-built artifacts. The common case is a corpus whose raw files are downloaded from an authoritative source or supplied locally by the user and then converted by third-party code.

The boundary is:

```text
resource -> source acquisition -> materializer -> local artifact -> consumer
```

A materializer is third-party executable code. Agora owns acquisition, execution constraints, integration metadata, artifact publication, and provenance; the materializer owns parsing, normalization, scholarly semantics, output construction, and converter-specific validation.

## Trust boundaries

There are now three distinct trust-sensitive phases. They must not be collapsed by future automatic composition.

### 1. Passive registered-source acquisition

`registry/materializers.yaml` may identify an immutable third-party plugin commit and its expected `agora.materializer.json`. The command:

```bash
python scripts/agora_install_materializer.py fetch <plugin-id>
```

fetches that exact commit, removes Git metadata, validates the manifest binding, and hashes the source tree. This phase does not build the Python project, import the plugin, or execute plugin Python.

### 2. Python package/build installation

A Python source project is not passive data. `pip install` can invoke a PEP 517 build backend and therefore execute third-party Python before a materializer itself is run. Registered Python projects consequently declare `package.install_trust: explicit-code-execution`, and Agora refuses installation unless the caller explicitly supplies:

```bash
--approve-code-execution
```

This is an explicit trust decision for the pinned plugin's packaging/build process. That installation code currently executes outside the materialization OS sandbox. Future resource → materializer composition must not synthesize this approval merely because a resource references a registered plugin.

Installation is performed from a disposable copy of the immutable fetched source. The canonical source tree is rehashed and its manifest binding is revalidated after the build. Module availability is checked by filesystem structure rather than Python import, so installation verification itself does not import package `__init__.py`.

### 3. Materializer execution

The materialization host still accepts an explicit manifest path. Supplying `--manifest` is the separate execution trust decision for the current prototype. The host validates that manifest, requires an OS sandbox by default, acquires source data, launches the declared module, validates output, and writes artifact provenance.

Automatic resource-to-materializer execution must eventually bind a resource to both an Agora-managed installation record and an explicit/defined execution-approval policy. An arbitrary filesystem manifest path must never self-authenticate.

## Materializer contract

Contract v1 accepts only:

- `execution.type: python-module`;
- a syntactically valid Python module name;
- argument strings using only `{source}`, `{output}`, and `{source_revision}` placeholders;
- `execution.network: deny`;
- directory input;
- public credential-free HTTPS Git acquisition and/or an explicitly user-provided local directory;
- a declared output format and required relative output paths.

There is no shell, script/eval field, executable URL, arbitrary environment block, or resource-supplied argv.

The JSON Schema is authoritative for structural validation. Runtime code adds cross-field/security checks that the schema does not express conveniently, such as duplicate materializer/acquisition ids and parsed URL credential checks.

## Registered installation identity

Agora separates immutable plugin source from interpreter/platform-specific installed environments:

```text
<root>/<plugin>/<commit>/
  source/
  agora-source.json
  environments/<python-abi-platform>/
    runtime/
      agora.materializer.json
      .agora-environment.json
      ... installed project and dependency files ...
    pip-report.json
    agora-installation.json
```

The environment key includes Python implementation, full Python version, ABI, and platform. A Python 3.12 environment is therefore not silently reused as a Python 3.13 environment, and architecture/platform changes select a different installation path.

`agora-installation.json` records:

- immutable plugin repository commit and version;
- fetched source-tree SHA-256;
- source and execution-manifest SHA-256 values;
- Python implementation/version/cache tag/ABI/platform/system/machine;
- exact resolved installed distribution names and versions;
- a digest of the runtime identity plus distribution closure;
- a SHA-256 over the complete managed runtime tree;
- pip report SHA-256;
- the install-time trust class;
- a combined execution identity over source tree, managed runtime tree, and Python runtime identity.

Idempotent reuse recomputes source and runtime hashes and re-reads distribution metadata. Editing plugin source, installed dependency files, distribution metadata, the execution manifest, or the pip report invalidates the installation. `--repair` uses a staging environment and replacement/rollback path. Per-source and per-environment exclusive locks prevent concurrent installations from racing.

The current registry does **not** yet guarantee reproducible rebuilding from a lockfile. Pseudepigrapha-TF currently declares a Text-Fabric version range and an unpinned build backend. Fresh installs may therefore resolve different dependency files. Agora distinguishes those executions by recording the resolved closure and complete runtime-tree hash; reviewed lock/constraints plus package hashes remain a prerequisite for unattended automatic installation.

## Source acquisition for corpus materialization

Agora acquires corpus source data before launching the materializer.

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

Before any automatic corpus-source network acquisition, Agora validates the materializer manifest, final-output feasibility, and availability of the required OS sandbox backend. A bad destination or missing sandbox therefore fails before a Git fetch.

Automatic corpus-source acquisition falls back to user-local mode only for acquisition/environment failures. A fetched source that violates the declared input contract is treated as a contract error rather than being hidden behind an interactive fallback.

## Execution

The materializer receives:

- a read-only corpus source directory;
- a writable staging artifact directory;
- its trusted installed/plugin code;
- a filtered environment.

Agora launches the declared Python module directly and never invokes a shell.

### Sandbox policy

Sandboxing fails closed by default.

- Linux: bubblewrap (`bwrap`) creates new namespaces, including an isolated network namespace; system/runtime/plugin/source mounts are read-only and output is read/write.
- macOS: `sandbox-exec` uses a deny-by-default profile; system/runtime/plugin/source/output paths receive the reads needed by Python/converters, only output/work receive writes, and network operations are denied.
- Other platforms: contract v1 refuses to run with sandbox mode `required`.

`--sandbox off` is an explicit development/trust override only.

Both supported backends are exercised by `.github/workflows/materialization-sandbox.yml`. The E2E launches a real fixture through `sandbox="required"`, reads the source, writes and reopens output, verifies the artifact/provenance, and attempts to connect to a live loopback listener that must be denied by the sandbox.

The same workflow exercises the pinned Pseudepigrapha-TF reference materializer on Linux: Agora acquires the pinned OCP source itself, runs the real converter under bubblewrap, and verifies that the exact resolved OCP commit survives through Agora provenance, the converter report, and generated Text-Fabric metadata. This is an integration smoke, not a duplicate of Pseudepigrapha-TF's semantic test suite.

The sandbox is defense in depth around code the user chose to trust; it is not a claim that arbitrary untrusted Python is safe.

## Transactional output

Converters never write directly into the requested final artifact path.

Agora creates a sibling staging directory on the same filesystem, runs the converter there, validates all required output paths, writes protected provenance, and only then atomically renames the staging directory to the requested destination. Converter failure, output-validation failure, or provenance failure removes staging and leaves an existing empty destination empty (or an absent destination absent).

`agora-materialization.json` is reserved for Agora and is created with exclusive/no-follow semantics after the converter exits, preventing a converter-created symlink from redirecting the provenance write.

## Provenance

A successful artifact records the materializer plugin id/version, a deterministic code-tree SHA-256, materializer id, corpus-source identity, output format, sandbox backend, manifest SHA-256, and UTC timestamp.

For an unmanaged manifest, `plugin.code_sha256` remains a digest of the importable plugin code tree as defined by the prototype host; it must not be interpreted as a dependency lock.

For an Agora-managed registered environment, installation intentionally places the complete installed project and dependencies directly under the managed `runtime/` root and reserves a top-level `src/` path. The materialization host therefore hashes the **entire managed runtime tree** for `plugin.code_sha256`. `agora-installation.json` records the same runtime-tree hash together with Python/ABI/platform identity and the exact distribution closure. This makes the artifact code digest traceable to a concrete managed environment even though rebuilds are not yet lockfile-deterministic.

The manifest hash is separate from the runtime-tree digest: changing the declared contract or changing executable/dependency files changes independently visible identities.

## Consumer boundary

The materializer output format is independent of the eventual consumer. A converter may produce Text-Fabric, SQLite, DuckDB, or another registered local format. Resource-to-materializer selection, artifact cache keys, and consumer hand-off remain a later integration layer.

The first reference implementation is `alexsosn/Pseudepigrapha-TF`:

```text
OCP XML -> pseudepigrapha-tf -> text-fabric -> Context-Fabric-compatible local artifact
```

Pseudepigrapha-TF already exposes `--upstream-commit`; its materializer manifest uses `{source_revision}` so the Agora path records the same immutable upstream commit rather than losing it when only `static/docs` is mounted as the source.

## Ownership

Agora owns:

- canonical materializer registration and install metadata;
- passive source acquisition and integrity receipts;
- explicit install-time trust UX and environment identity;
- manifest contract/schema;
- corpus source acquisition orchestration;
- integration-level input/output validation;
- sandbox/process launch;
- transactional local artifact publication;
- integration provenance.

The converter repository owns:

- its Python package/build configuration and dependencies;
- parsing and normalization;
- domain semantics;
- output construction;
- converter-specific semantic validation.

If a converter produces an incorrect scholarly result when run directly without Agora, the fix remains upstream under `ref-plugin-boundary.md`.

## Prototype commands

Passive registered fetch:

```bash
python scripts/agora_install_materializer.py fetch pseudepigrapha-tf
```

Explicit registered installation:

```bash
python scripts/agora_install_materializer.py install pseudepigrapha-tf \
  --approve-code-execution
```

The installer prints the managed execution-manifest path. Materialize through that path:

```bash
python scripts/agora_materialize.py \
  --manifest <managed-environment>/runtime/agora.materializer.json \
  --materializer ocp-text-fabric \
  --output ~/.local/share/agora/artifacts/pseudepigrapha
```

For legally obtained local corpus input, add:

```bash
--source /path/to/OCP/static/docs
```

The final artifact path must be absent or an empty directory.

## Deliberately deferred

The prototype still does not define:

- automatic resource → approved installation → materializer binding;
- a policy for how explicit install/build approval is represented in unattended agent workflows;
- lock/constraints files plus package hashes for reproducible Python-environment rebuilding;
- persistent artifact cache keys and retention;
- automatic consumer hand-off;
- Windows sandboxing;
- authenticated/click-through acquisition;
- CPU/RAM/disk quotas;
- a stable public artifact-format compatibility vocabulary.

Those must be resolved before registered materializers are installed and executed automatically merely because a resource references them.
