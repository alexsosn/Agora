# Design amendment: bind registered execution to the managed-runtime lock (#94)

## Trigger

The RED lifecycle regression demonstrated a TOCTOU gap in the first GREEN implementation: `resolve_installed_manifest()` verified the managed runtime, returned its manifest path, and only then did `materialize_registered()` delegate to the sandbox host. A concurrent explicit `install --repair` could replace the managed runtime between the final integrity check and converter execution.

The real Burns sandbox smoke still passed, but that does not prove the stronger managed-installation integrity invariant.

## Revised invariant

For registry-ID execution, one canonical registry snapshot determines the plugin, immutable ref, current-runtime installation path, and runtime lock path. The installer runtime lock must be acquired before the final `_environment_current()` check and held until the delegated materialization call returns or fails.

This guarantees that the exact managed runtime whose receipt/tree/dependency identity was verified cannot be replaced by another Agora installer operation during converter startup/execution.

## Implementation shape

- Keep `resolve_installed_manifest()` as a public read-only standalone resolver for callers that only need a verified path.
- Factor target selection and final manifest validation into private helpers that can operate on one already-selected plugin/target.
- `materialize_registered()` loads/selects the registry entry once, derives the exact managed target, acquires the same lock path used by `install_materializer()`, then performs the final integrity check and delegates to the existing sandbox host while that lock remains held.
- Do not call `fetch_materializer()`, `install_materializer()`, or repair paths.
- Do not modify `agora_materialize.py` or its explicit-manifest trust semantics.

## Test correction

The earlier RED-2 unit test asserted the internal call `materialize_registered() -> resolve_installed_manifest()`. That assertion encoded the unsafe implementation shape rather than the user/security contract. Replace it with assertions that one registry snapshot is selected, final integrity verification occurs while the installer runtime lock is held, host delegation receives the managed manifest, and fetch/install are never invoked.

The lifecycle RED remains the acceptance gate for this amendment.