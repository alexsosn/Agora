# Scripts

Repository tooling lives here: registry validation, deterministic marketplace generation, verification helpers, maintenance scripts, and experimental integration prototypes.

## Registry validation

```bash
python scripts/validate_registry.py
```

Validates Agora's canonical marketplace, plugin, provider, resource, collection, vocabulary, and v0.1 scope documents.

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

## Context-Fabric source coverage

```bash
python scripts/audit_context_fabric_sources.py
```

Audits every Context-Fabric resource in the fixed v0.1 catalog using upstream Git tree metadata. The report records the resolved source revision, discovered TF-root count, and selected root for ordinary corpora; collection roots are reported without materializing corpus blobs.

This is an installation and source-resolution check. It does not assess upstream corpus semantics, data quality, or research suitability.

## Registered materializer plugins

Discover materializer plugins Agora knows how to install:

```bash
python scripts/agora_install_materializer.py list
```

Install the registered Pseudepigrapha-TF converter and its Python dependencies:

```bash
python scripts/agora_install_materializer.py install pseudepigrapha-tf
```

The installer reads `registry/materializers.yaml`, fetches the exact immutable Git commit declared there, verifies that the upstream `agora.materializer.json` has the expected plugin identity/version/repository and exact materializer IDs, installs the upstream Python project into the managed checkout, verifies its execution modules are importable, and writes `agora-installation.json` as an installation receipt.

By default installations live under `$AGORA_DATA_HOME/agora/materializers` when `AGORA_DATA_HOME` is set, otherwise under `$XDG_DATA_HOME/agora/materializers` or `~/.local/share/agora/materializers`. Use `--root /path/to/root` for an explicit location. Re-running an installation is idempotent only when the existing receipt and manifest still match the canonical registry.

The installation receipt records what Agora downloaded and installed; it is not yet an automatic execution approval. Resource → materializer → consumer composition and binding an installed manifest into the materialization trust decision remain tracked separately.

## Experimental local materialization

After installing Pseudepigrapha-TF, pass its installed manifest to the existing materialization host:

```bash
python scripts/agora_materialize.py \
  --manifest ~/.local/share/agora/materializers/pseudepigrapha-tf/a2300b3c5b1a5e859d82691dc28bd53967053a8d/agora.materializer.json \
  --materializer ocp-text-fabric \
  --output /path/to/artifact
```

For any trusted materializer manifest:

```bash
python scripts/agora_materialize.py \
  --manifest /path/to/trusted/plugin/agora.materializer.json \
  --materializer <id> \
  --output /path/to/artifact
```

The host acquires a declared public Git source or accepts `--source /path/to/local/files`, validates the input contract, runs the materializer without a shell, requires an OS sandbox by default, validates the declared output, records immutable source/code provenance, and atomically publishes the finished artifact.

Supplying `--manifest` is still the explicit execution trust decision. Agora now has canonical download/install metadata for registered materializers, but it does not yet automatically bind an arbitrary manifest path to that installation record. `--sandbox off` is a development-only override.

Contract v1 exposes `{source}`, `{output}`, and `{source_revision}` argument placeholders. `{source_revision}` is the immutable commit resolved by Agora when one is available; it is an empty string for source trees with no Git revision.

Linux requires a working bubblewrap installation with user/network namespaces enabled by the host policy. Some Ubuntu configurations install `bwrap` while AppArmor still blocks unprivileged user namespaces; Agora fails closed in that situation rather than silently running unsandboxed. The GitHub-hosted Ubuntu E2E adjusts that restriction only on its disposable CI VM. A persistent host should use its distribution's supported bubblewrap/AppArmor configuration instead of copying the CI sysctl blindly.

The dedicated sandbox workflow exercises both OS backends with generic integration fixtures and also performs a pinned Pseudepigrapha-TF/OCP reference smoke. A separate install smoke exercises discovery, immutable download, package installation, receipt creation, manifest validation, and importability through `registry/materializers.yaml`. These checks validate Agora integration; converter semantics remain tested upstream.

See [`../wiki/architecture/ref-local-materialization.md`](../wiki/architecture/ref-local-materialization.md) for the ownership, sandbox, provenance, and trust boundaries.
