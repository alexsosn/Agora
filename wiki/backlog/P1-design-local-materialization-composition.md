# Design local materialization composition

## Objective

Turn the exercised local-materialization primitive into a marketplace-integrated capability without weakening the thin-plugin or installation-trust boundaries.

Reference architecture: [`../architecture/ref-local-materialization.md`](../architecture/ref-local-materialization.md).

## Evidence already established

PR #43 establishes the host-level primitive:

- schema-authoritative materializer manifests;
- public Git and user-local acquisition;
- immutable Git revision propagation through `{source_revision}`;
- deterministic local-source and plugin-code identities;
- preflight before network acquisition;
- shell-free execution with filtered environment;
- fail-closed Linux bubblewrap and macOS `sandbox-exec` backends;
- real E2E execution on both supported GitHub-hosted runner platforms;
- output read/write parity across Linux/macOS;
- network-denial E2E against a live loopback listener;
- transactional staging/validation/provenance/atomic publication;
- protected Agora provenance path;
- a pinned Pseudepigrapha-TF/OCP reference materialization executed through the real Linux sandbox, with the exact OCP commit verified in Agora provenance, the converter report, and generated Text-Fabric metadata.

The Pseudepigrapha-TF companion materializer is the reference contract and uses its existing `--upstream-commit` option rather than changing converter semantics.

## Next design decisions

1. Define an Agora installation/approval record that binds plugin identity, code/artifact identity, and its materializer manifest. An arbitrary filesystem manifest path must not self-authenticate once automatic composition exists.
2. Define the canonical resource → approved materializer reference without placing executable fields in resource/catalog metadata.
3. Define deterministic artifact cache keys from source identity + approved materializer/code identity + manifest/options.
4. Define output-format compatibility and hand-off to consumers such as Context-Fabric or SQL MCPs.
5. Define lifecycle/retention behavior for cached local artifacts and failed/interrupted builds.
6. Decide whether the materialization runtime graduates from `scripts/` into an Agora package when it becomes a supported user-facing runtime API.
7. Add resource-level smoke evidence only after the installation and composition model exists; do not duplicate upstream converter semantic tests in Agora.

## Constraints

- Keep converter/domain behavior upstream.
- Do not redistribute source or derived artifacts unless their licenses independently permit it.
- Do not bypass authentication, click-through terms, or access controls.
- Do not weaken sandbox requirements implicitly when a backend is unavailable.
