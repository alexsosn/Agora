# Plan: run approved installed materializers by registry ID (#94)

## Invariants

- Running by registry ID never fetches, installs, repairs, or executes packaging hooks.
- The current immutable registry pin and current Python/runtime identity determine the only acceptable managed installation path.
- Installation integrity is re-verified immediately before resolving executable plugin code.
- Explicit `--manifest` trust mode remains backward compatible.
- Materialization semantics, sandbox/network denial, source validation, staging publication, and provenance remain delegated to the existing host.
- No automatic Context-Fabric composition is introduced.

## TDD sequence

### RED 1 — managed resolver contract

Add tests for a public installer-side resolver before production code:

- unknown plugin fails without invoking install/fetch;
- registered but missing current-runtime installation gives an actionable error;
- valid installed target resolves to `runtime/<registered manifest>`;
- failed `_environment_current` check rejects tampered/stale state;
- resolver never calls `install_materializer` or `fetch_materializer`.

### GREEN 1 — read-only resolver

Implement the smallest public resolver around `load_registry`, `select_plugin`, `default_install_root`, `installation_path`, and `_environment_current`. Return only the verified managed manifest path. No repair option.

### RED 2 — materialization registry mode

Add tests before CLI production changes:

- programmatic `materialize_registered()` resolves then delegates to `materialize()`;
- unknown materializer id fails through existing manifest selection before source acquisition;
- parser requires exactly one trust source (`--manifest` xor `--plugin`);
- explicit-manifest invocation remains unchanged;
- registry mode accepts managed install/registry paths but does not trigger installation.

### GREEN 2 — CLI/programmatic delegation

Add a lazy installer import in `agora_materialize.py`, a thin `materialize_registered()` wrapper, mutually exclusive CLI selection, and scoped `--install-root`/`--registry` arguments. Keep `materialize()` untouched except where necessary to preserve its public contract.

### RED 3 — live registered Burns acceptance

Change the existing Burns workflow contract first so it requires registry-ID execution and rejects the old manually resolved `--manifest "$UGARIT_RUNTIME/..."` execution path.

### GREEN 3 — real sandbox smoke

Update the registered Burns workflow to execute its synthetic CSV through `--plugin ugarit-context-parsing` plus the managed install root. Continue verifying:

- immutable registered commit / receipt / dependency closure;
- packaged PDF parser import;
- bubblewrap + network isolation;
- required TF files, conversion report and Agora provenance;
- Text-Fabric reload and `cuc_tablet="KTU 1.14"`.

## Test gates

After each RED commit, retain the failing Actions run as evidence before the minimal GREEN commit. Before merge, require the exact final head to pass Foundation, registered materializer install smoke, and materialization sandbox E2E.

## Independent review

Freeze the exact green head, then review it independently from the implementation path for:

- accidental implicit install/fetch/repair;
- path substitution or registry-pin bypass;
- runtime identity and integrity TOCTOU assumptions;
- circular imports / duplicate module execution;
- CLI ambiguity between manifest trust and registry trust;
- source-acquisition ordering and unknown-id fail-closed behavior;
- sandbox/network behavior regressions;
- Burns and Pseudepigrapha compatibility;
- scope creep into resource composition.

Any blocking finding gets its own regression RED → minimal fix → full GREEN → fresh exact-head review.

## Branch / PR hygiene

Keep one working branch for #94. After merge, audit open PRs and feature branches; branches associated only with merged/closed Burns work must not be left as active competing work. Where connector capabilities cannot delete refs, document the limitation and at minimum ensure there is no open PR pointing at them and no divergent unmerged work.