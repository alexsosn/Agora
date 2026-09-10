# Research: registered materializer nested-manifest consistency (#131)

## Scope and ownership

This is an Agora-owned integration bug. The materializer registry, managed installer, integrity verification, and registered runner are all Agora responsibilities. No third-party converter behavior or scholarly semantics need to change.

Normative boundaries: `AGENTS.md`, `CONTRIBUTING.md`, and `wiki/architecture/ref-plugin-boundary.md`.

## Current schema contract

`registry/schema/materializers.schema.json` defines `manifest` through `safeRelativePath`. That contract allows normalized relative descendants such as `pkg/agora.materializer.json` while rejecting absolute POSIX paths and explicit `..` traversal components. The runtime containment boundary is stricter than the schema regex: `installer._contained(root, relative, label)` resolves `root / relative` and rejects any result outside `root`.

Therefore root-level placement is not a registry invariant. Nesting below the managed source/runtime is intentionally representable.

## Installer and integrity path

The installer consistently uses the registered relative path rather than assuming a root-level manifest:

- `_validate_binding(plugin, root)` resolves `_contained(root, plugin["manifest"], "registered manifest")`, loads that exact manifest, and verifies plugin id/name/version/repository plus the exact ordered materializer-id list.
- `fetch_materializer()` stores the registered manifest path and hash in `agora-source.json` and hashes the complete source tree.
- the managed installation/runtime integrity receipt binds the installed bytes and source identity; `_verified_environment_receipt()` verifies those bytes before authorization/execution callers may trust them.

Nothing in this installer contract requires `manifest.parent == runtime`.

## Registered runner mismatch

`resolve_installed_manifest()` correctly resolves the current registered manifest via:

```python
runtime = (target / "runtime").resolve()
manifest = installer._contained(runtime, plugin["manifest"], "managed runtime manifest")
```

and returns that exact contained file after managed-environment verification.

`materialize_registered()` then acquires the install/runtime lock, calls the resolver, re-reads current registry state, and computes `expected_runtime`. Its final registry-drift guard currently requires:

```python
current_target == target and manifest.parent == expected_runtime
```

The parent-directory equality is incorrect in both directions:

1. **too strict:** a schema-valid `pkg/agora.materializer.json` resolves to `runtime/pkg/agora.materializer.json`, whose parent is not `runtime`, so direct registered execution rejects it;
2. **too weak:** if the registry changes from one root-level manifest filename to another file in the same runtime directory while the runner waits for the lock, `manifest.parent == expected_runtime` still holds. The runner can therefore continue with the stale verified manifest even though the current registry selects a different manifest path.

The later `installer._validate_binding(current_plugin, expected_runtime)` validates the *current* selected manifest but does not prove it is the same file that `resolve_installed_manifest()` returned and the host is about to execute. The missing invariant is exact manifest-path identity, not parent-directory identity.

The newer cacheability authorization path already learned this lesson during #106: it resolves both the previously verified and current registry-selected manifest under the same runtime and compares their exact resolved contained paths while holding the runtime lock. #131 should align direct execution with that boundary, without coupling direct execution to cacheability policy.

## Current canonical registrations

At research base `c6c7065bd877e04522f598f3aec21b812ce35ef7`, both registered materializer plugins (`pseudepigrapha-tf` and `ugarit-context-parsing`) use root-level `agora.materializer.json`. This explains why the bug is latent in current shipped registrations; it does not narrow the schema contract.

No generated client command or public runner contract establishes root-level placement as a requirement. The registry schema is the authoritative placement contract.

## Threat and race model

The important race is registry drift while a registered execution waits for the existing runtime lock. The runner must re-read current registry state under that lock and bind execution to the exact currently selected contained manifest path. It must continue to reject:

- changed installation target/ref;
- current manifest paths escaping the runtime;
- missing manifests;
- registry↔manifest id/name/version/repository/materializer-list drift;
- materializer IDs no longer approved by current registry state.

No new fetch/install/repair behavior is needed or permitted.

## Conclusion

The correct minimal invariant is:

```text
verified_manifest_path == contained(expected_runtime, current_plugin.manifest)
```

combined with the existing `current_target == target`, managed-environment integrity verification, `_validate_binding(current_plugin, expected_runtime)`, and approved-materializer check.

Do not replace this with root-parent equality, basename equality, string-prefix checks, or a second resolver that performs network/install side effects.
