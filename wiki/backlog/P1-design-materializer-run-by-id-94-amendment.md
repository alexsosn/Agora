# Design amendment: isolate registered materializer execution (#94)

During pre-implementation review of the RED-1 contract, the lowest-risk CLI ownership changed.

`agora_install_materializer.py` already imports `load_manifest` from `agora_materialize.py`. Adding registry execution directly to `agora_materialize.py` would require a reverse installer import (even if lazy), coupling two security-sensitive modules and making script/module execution semantics harder to reason about.

Use a new thin Agora-owned module instead: `scripts/agora_materialize_registered.py`.

It will:

- import the installer as a module and reuse its registry/path/integrity primitives;
- expose `resolve_installed_manifest()` and `materialize_registered()` as public read-only operations;
- never call `fetch_materializer()` or `install_materializer()`;
- import/delegate to the existing `agora_materialize.materialize()` host rather than duplicating sandbox/source/output logic;
- provide a registry-ID CLI while leaving the existing explicit `--manifest` CLI byte-for-byte unchanged.

This is safer than modifying either existing security boundary and gives explicit-manifest mode the strongest possible backward-compatibility guarantee: no production changes at all to that code path.

The initial RED commit remains useful evidence that no managed resolver existed. A revised tests-only RED will bind the resolver contract to the thin module before production implementation.