# Empirical research amendment: materializer execution identity reproducibility (#111)

**Status: normative empirical amendment.** This document supersedes speculative statements in `P1-research-materializer-execution-identity-111.md` where they conflict with the observed two-install evidence below.

## Experiment actually run

PR #113 head `5f29c84258e1897082881b00e9d4db28b96f430b` ran the production `install_materializer()` path twice from identical synthetic immutable source in distinct managed roots, using real pip local-project installation and an offline deterministic PEP 517 fixture.

Workflow: `Materializer execution identity research`, run `34323481318`.

Platforms:

- Ubuntu 24.04, CPython 3.13.15;
- macOS 26.6.2 arm64, CPython 3.13.15;
- Windows Server 2025 x64, CPython 3.13.15.

For every platform the two installs had equal:

- source tree SHA-256;
- `runtime_identity()` object;
- resolved target distribution list.

For every platform the current schema-v2 installs had unequal:

- raw managed environment tree SHA-256;
- `execution_identity_sha256`;
- pip report SHA-256.

This establishes the #111 defect empirically: equivalent clean managed installs do not reproduce the current execution identity.

## Complete observed runtime diff

### Linux

Only these runtime paths differed:

1. `research_probe-1.0.0.dist-info/direct_url.json`;
2. `research_probe-1.0.0.dist-info/RECORD`.

`direct_url.json` differed only in the random Agora staging URI, for example:

```text
file:///tmp/agora-materializer-build-.../source
```

The `RECORD` difference was the derived SHA-256 digest for that `direct_url.json` row. Other runtime files, including the generated console script, were byte-identical.

### macOS

Only these runtime paths differed:

1. `research_probe-1.0.0.dist-info/direct_url.json`;
2. `research_probe-1.0.0.dist-info/RECORD`.

Again the origin URI was the only direct textual difference and the `RECORD` change was its derived digest. The generated console script was byte-identical.

### Windows

Exactly three runtime paths differed:

1. `bin/research-probe.exe`;
2. `research_probe-1.0.0.dist-info/direct_url.json`;
3. `research_probe-1.0.0.dist-info/RECORD`.

The origin and `RECORD` classifications are the same as POSIX.

The generated launcher had identical size (`108357` bytes) and differed at exactly two byte offsets in the detailed probe. No differing build-root/install-root/interpreter-path text was found in the launcher strings. The two byte values each advanced by one between successive installs.

## Windows launcher cause

The current upstream distlib `ScriptMaker._write_script()` implementation constructs a Windows console launcher as:

```text
launcher stub + shebang + ZIP archive containing __main__.py
```

At upstream distlib commit `454a87c64f0b545138dc4798aa833a4ff8ac2377`, the ZIP member receives a deterministic `ZipInfo.date_time` only when `SOURCE_DATE_EPOCH` is set. Otherwise distlib calls `ZipFile.writestr('__main__.py', script_bytes)` and the ZIP implementation records the current time.

That implementation, together with the observed fixed-size launcher and exactly two changed bytes with no path-string drift, classifies the Windows-only difference as installer-generated ZIP timestamp metadata. It is not evidence that the launcher executes a different module, interpreter, target path, or payload.

The launcher still remains execution-bearing. The implementation must therefore normalize only the recognized ZIP timestamp metadata in the canonical execution representation, or make that timestamp deterministic at install time without changing other launcher bytes. It must not ignore the launcher file.

## Pip report classification

The detailed probe parsed both `pip-report.json` files. On all three platforms the only JSON difference was:

```text
$.install[0].download_info.url
```

whose value was the random local `file://.../agora-materializer-build-.../source` URI.

The pip report is receipt/integrity provenance and is not part of the current runtime-tree input to `execution_identity_sha256`. Its raw hash can therefore remain integrity-sensitive in receipt v3. There is no need to make raw pip reports byte-identical merely to obtain a reproducible canonical execution identity.

## Empirical classification table

| Artifact | Platforms | Classification | Canonical execution treatment |
| --- | --- | --- | --- |
| `*.dist-info/direct_url.json` local `file://` URL | Linux/macOS/Windows | direct Agora staging provenance | canonicalize only the proven random staging URI, fail closed on unexpected/non-local shape |
| corresponding `RECORD` row | Linux/macOS/Windows | cryptographic derivative of canonicalized origin | recompute digest/size from canonical `direct_url.json`; preserve all unrelated rows byte-semantically |
| Windows `bin/*.exe` ZIP member timestamp | Windows | generated volatile installer timestamp | canonicalize only recognized ZIP timestamp fields or deterministically produce them; preserve stub, shebang, payload and all other archive bytes/metadata |
| `pip-report.json $.install[0].download_info.url` | Linux/macOS/Windows | raw installation provenance | retain raw receipt hash; do not include this volatile URL in canonical execution identity |

No category-(4) unexplained runtime difference remains in this synthetic real-pip experiment.

## Security consequences

The evidence supports separating raw integrity from canonical execution identity rather than weakening `_environment_current()`:

- raw `environment.tree_sha256` continues to cover every installed runtime byte, including raw `direct_url.json`, raw `RECORD`, and raw Windows launcher bytes;
- raw `pip_report_sha256` remains checked;
- canonical execution hashing transforms only the explicitly classified fields above;
- actual module/package/distribution/entry-point/launcher payload changes remain identity-bearing;
- malformed or structurally unexpected metadata must fail closed rather than fall through to broad normalization.

The Windows result specifically rules out a whole-launcher ignore: only timestamp metadata is volatile; the executable stub, shebang and embedded `__main__.py` payload remain semantically relevant.

## Remaining implementation RED

The research probes assert the current defect and emit diagnostics. Before production GREEN, the implementation PR must replace/add focused RED contracts for the desired state:

1. two clean equivalent installs have equal canonical execution identities on Linux/macOS/Windows;
2. raw integrity tree hashes may remain different and both installations still verify;
3. only the exact random local-project origin URI is normalized;
4. its canonical `RECORD` digest is recomputed, not ignored;
5. Windows launcher timestamp-only variation is neutral, but changing stub/shebang/embedded script bytes changes canonical identity;
6. changing a non-ephemeral `direct_url.json` field or unrelated `RECORD` row changes identity or fails closed;
7. changing actual installed module/package/version/entry-point bytes changes identity;
8. receipt v2/v3 migration is explicit and cannot authorize an old v2 digest as a new reproducible identity by accident.

## Decision

The production direction is now evidence-backed: retain full raw integrity and add a separate canonical execution-tree identity with narrowly enumerated, dependency-aware transforms for the observed installer provenance graph. No broad `.dist-info`, `RECORD`, script, launcher, or pip-report exclusions are justified.
