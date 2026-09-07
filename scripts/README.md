# Scripts

Repository tooling lives here: registry validation, deterministic marketplace generation, verification helpers, maintenance scripts, and experimental integration prototypes.

## Registry validation

```bash
python scripts/validate_registry.py
```

Validates Agora's canonical marketplace, MCP plugin/provider/resource, collection, vocabulary, materializer-plugin, and v0.1 scope documents. Materializer disciplines and verification statuses use the same controlled vocabularies as the rest of the registry.

## Marketplace generation

```bash
python scripts/generate_marketplaces.py
```

Generates the native Claude Code and ChatGPT/Codex marketplace/plugin metadata from the canonical registry.

Use the freshness-only mode in CI or before committing registry changes:

```bash
python scripts/generate_marketplaces.py --check
```

Phase 2 intentionally does not generate Antigravity artifacts.

## v0.1 release verification status

```bash
python scripts/generate_release_status.py
```

Regenerates only the bounded plugin/client verification block in `wiki/releases/v0.1-plan-active.md`. The block is derived from the fixed plugin set in `registry/v0.1.yaml`, aggregate/client statuses in `registry/plugins.yaml`, and the referenced check semantics in `registry/verification-checks.yaml`. It does not infer live evidence from check-ID names and does not promote aggregate plugin status from a stronger client path.

Verify freshness without writing:

```bash
python scripts/generate_release_status.py --check
```

The generator fails closed when required plugin verification metadata or referenced/matching verification checks are missing. Narrative release history outside the generated markers remains hand-authored.

## Context-Fabric source coverage

```bash
python scripts/audit_context_fabric_sources.py
```

Audits every Context-Fabric resource in the fixed v0.1 catalog using upstream Git tree metadata. The report records the resolved source revision, discovered TF-root count, and selected root for ordinary corpora; collection roots are reported without materializing corpus blobs.

This is an installation and source-resolution check. It does not assess upstream corpus semantics, data quality, or research suitability.

## Registered materializer plugins

Discover materializer plugins Agora knows about:

```bash
python scripts/agora_install_materializer.py list
```

A registered Python materializer has two separate phases.

### Passive fetch

```bash
python scripts/agora_install_materializer.py fetch pseudepigrapha-tf
```

`fetch` downloads the exact immutable Git commit from `registry/materializers.yaml`, removes Git metadata, validates the upstream `agora.materializer.json`, and hashes the fetched source tree. It does **not** build the project, import the package, or execute plugin Python.

### Explicit installation trust

Python package installation is executable code: a PEP 517 build backend can run while pip builds or inspects a source project. Agora therefore refuses to install a registered Python materializer without an explicit acknowledgement:

```bash
python scripts/agora_install_materializer.py install pseudepigrapha-tf \
  --approve-code-execution
```

Installation shells out to `pip` from the interpreter you run the installer with, so that interpreter must provide pip. Environments created by `uv venv` or `python -m venv --without-pip` do not; the installer says so before building rather than failing with an opaque pip exit status.

This install-time code runs outside the later materialization sandbox. The flag is a user trust decision for the pinned plugin source and its packaging/build process; it must not be supplied silently by future resource-to-materializer automatic composition.

The installer builds from a disposable copy of the fetched source. The canonical fetched source remains separate and is rehashed/revalidated after the build. Module verification is filesystem-only and does not import the plugin.

Installations are separated by immutable plugin commit and current Python/runtime identity:

```text
<root>/<plugin>/<commit>/
  source/
  agora-source.json
  environments/<python-abi-platform>/
    runtime/
      agora.materializer.json
      .agora-environment.json
      ... installed package and dependencies ...
    pip-report.json
    agora-installation.json
```

`agora-installation.json` records the source-tree hash, Python implementation/version/ABI/platform, exact installed distribution names and versions, a distribution/runtime descriptor digest, the full managed-runtime tree hash, pip-report hash, manifest hashes, and a combined execution identity. Reuse re-hashes source and runtime contents and re-reads installed distribution metadata; source or dependency modification invalidates the installation. `--repair` performs a transactional replacement.

Per-target installation locking uses a persistent lock file containing the marker `agora-materializer-lock-v3`. The file itself remains after a successful run or process crash; the OS-backed advisory lock on that file is the live ownership signal and is released automatically when a process exits. Current Agora and the advisory-only #62 implementation coordinate on that same advisory lock. Do not delete a marked v3 lock file during normal use.

The marker is fixed newline-free ASCII bytes. Current Agora inspects only file metadata before lock acquisition, then verifies the exact marker bytes through the already acquired readable lock handle. This order keeps the configured contention timeout effective on Windows, where exclusive file locks are mandatory and a separate pre-acquire read can itself block.

The persistent marker is also a one-way migration boundary for older pre-#62 checkouts, which treated file existence as ownership. If the installer reports an empty or unrecognized legacy/pre-migration lock file, first confirm that no older materializer operation is running, then remove that file once and retry. If deliberately downgrading to a pre-#62 checkout after a v3 marker has been established, first confirm that no #62/current operation is active, then remove the marked file manually. The installer waits up to 60 seconds for live contention or a releasing legacy holder before failing.

The dependency resolver is not yet lockfile-reproducible: Pseudepigrapha-TF currently permits a Text-Fabric version range and its build backend is not hash-pinned. Two fresh installs may therefore resolve different environments. Agora records the resulting environment identity so they are distinguishable; a reviewed lock/constraints-and-hashes policy remains necessary before zero-touch automatic installation is appropriate.

By default data lives under `$AGORA_DATA_HOME/agora/materializers` when `AGORA_DATA_HOME` is set, otherwise under `$XDG_DATA_HOME/agora/materializers` or `~/.local/share/agora/materializers`. Use `--root /path/to/root` for an explicit location.

## Experimental local materialization

The installer prints the execution manifest path after a successful installation. Pass that **managed runtime** manifest to the materialization host:

```bash
python scripts/agora_materialize.py \
  --manifest <installed-environment>/runtime/agora.materializer.json \
  --materializer ocp-text-fabric \
  --output /path/to/artifact
```

For any trusted unmanaged materializer manifest:

```bash
python scripts/agora_materialize.py \
  --manifest /path/to/trusted/plugin/agora.materializer.json \
  --materializer <id> \
  --output /path/to/artifact
```

The host acquires a declared public Git source or accepts `--source /path/to/local/files`, validates the input contract, runs the materializer without a shell, requires an OS sandbox by default, validates the declared output, records immutable source/code provenance, and atomically publishes the finished artifact.

Supplying `--manifest` remains the explicit **materializer execution** trust decision in this prototype. It is distinct from the earlier install-time build-code approval. Agora does not yet automatically bind a resource to an approved installed materializer.

For a managed environment, its `runtime/` directory intentionally has no top-level `src/`; the existing materialization host therefore hashes the complete managed runtime tree as `plugin.code_sha256`. The same tree hash is recorded in `agora-installation.json`, binding artifact code provenance to the installed package/dependency contents rather than only to the upstream `src/` tree.

Contract v1 exposes `{source}`, `{output}`, and `{source_revision}` argument placeholders. `{source_revision}` is the immutable commit resolved by Agora when one is available; it is an empty string for source trees with no Git revision.

Linux requires a working bubblewrap installation with user/network namespaces enabled by the host policy. Some Ubuntu configurations install `bwrap` while AppArmor still blocks unprivileged user namespaces; Agora fails closed in that situation rather than silently running unsandboxed. The GitHub-hosted Ubuntu E2E adjusts that restriction only on its disposable CI VM. A persistent host should use its distribution's supported bubblewrap/AppArmor configuration instead of copying the CI sysctl blindly.

The dedicated sandbox workflow exercises both OS backends with generic integration fixtures and performs a pinned Pseudepigrapha-TF/OCP reference smoke. A separate install smoke exercises passive source acquisition and explicit approved environment installation from `registry/materializers.yaml`. These checks validate Agora integration; converter semantics remain tested upstream.

See [`../wiki/architecture/ref-local-materialization.md`](../wiki/architecture/ref-local-materialization.md) for the ownership, sandbox, provenance, and trust boundaries.
