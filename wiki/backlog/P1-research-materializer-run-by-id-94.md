# Research: run approved installed materializers by registry ID (#94)

## Goal

Remove the requirement for callers to discover a managed runtime path and pass its `agora.materializer.json` explicitly after a third-party materializer has already been registered and explicitly installed.

This is intentionally narrower than resource → materializer → Context-Fabric composition: no resource metadata execution fields, no automatic materializer selection, no artifact cache, and no automatic Context-Fabric registration/loading.

## Current trust and execution paths

`agora_install_materializer.py` owns the immutable registry and managed installation lifecycle. `installation_path(plugin, root)` selects the environment for the current Python/runtime identity. Installation records a schema-v2 receipt and a managed-runtime marker.

`_environment_current(plugin, target)` is already the complete read-only verifier needed before execution. It checks:

- installation receipt schema and registered plugin id/commit;
- exact current Python/runtime identity;
- immutable fetched source tree hash;
- installed runtime tree hash (excluding declared cache/build noise);
- resolved installed distributions and descriptor hash;
- pip report hash and explicit-code-execution trust marker;
- source and execution manifest hashes;
- managed-runtime marker, source binding, and execution identity hash.

It performs no package installation and no third-party code execution. Therefore registry-ID execution should reuse this verifier rather than calling `install_materializer()`.

`agora_materialize.py` currently accepts only an explicit `--manifest`. It validates/selects the requested materializer before source acquisition, preflights destination/sandbox before acquisition, executes through the existing sandbox path, validates required outputs, writes host provenance, and atomically publishes the staging output.

## Design conclusion

Add a public read-only resolver to `agora_install_materializer.py` that:

1. loads the canonical (or explicitly supplied) registry;
2. selects the plugin id (unknown ids fail immediately);
3. derives the current-runtime installation path;
4. fails actionably if it is not installed;
5. runs the existing environment-integrity verifier;
6. fails closed on stale/tampered/runtime-mismatched state without repair or reinstall;
7. returns the copied manifest inside the verified managed runtime.

Extend `agora_materialize.py` with a registry mode that lazily imports this resolver (avoiding the existing installer → materializer import dependency becoming a module-level cycle), resolves the verified manifest, then delegates unchanged to `materialize()`.

CLI contract: exactly one of `--manifest` or `--plugin` is required. Registry mode also accepts `--install-root` and `--registry`; those options are invalid/useless for explicit-manifest trust mode and should be rejected or clearly scoped.

## Trust distinction

- `--manifest PATH`: existing prototype behavior. The caller explicitly trusts the supplied manifest/plugin tree for this invocation.
- `--plugin ID`: stronger managed behavior. The caller selects an Agora registry entry that must already have been explicitly installed; execution is allowed only if the managed installation still verifies exactly against the current registry pin and current Python/runtime identity.

A run-by-ID command must never fetch, repair, install, or execute packaging/build hooks implicitly.

## Failure behavior

- Unknown plugin: fail before source acquisition.
- Registered but not installed for the current runtime: actionable install command, no fetch/install side effects.
- Registry pin drift: the new immutable commit maps to another installation path and therefore behaves as not installed.
- Tampered source/runtime/receipt/manifest/pip report: fail integrity verification before converter execution.
- Python/runtime identity mismatch: current runtime selects another installation path; fail as not installed.
- Unknown materializer ID: verified manifest resolves first, then existing manifest selection fails before source acquisition.
- Explicit manifest mode: unchanged.

## Burns / Pseudepigrapha compatibility

Burns (`ugarit-context-parsing`) and Pseudepigrapha-TF use the same managed installer/receipt model. No plugin-specific execution code is required. The registered Burns synthetic CSV sandbox smoke is the strongest acceptance fixture because it proves an installed third-party runtime, network-denied execution, TF output, and CUC identifier normalization.

## Security notes

Registry-ID mode reduces caller-controlled executable-path surface: plugin code must come from the already verified managed runtime corresponding to the immutable registry pin. The resolver must not accept an arbitrary runtime path. Existing source validation, sandbox preflight, output staging, network isolation and provenance remain owned by `agora_materialize.py` and must not be duplicated.

## Out of scope / follow-up

The produced TF directory is still an output path chosen by the caller. Automatic durable artifact identity/caching and automatic registration/loading by Context-Fabric/cfabric-mcp remain a separate composition problem.