# Issue #197 research and plan

## Research

Agora 1.0 already has the pieces needed for a standalone CopticScriptorium-TF
materializer without invoking the post-1.0 parent/module composition work in #135:

- `registry/materializers.yaml` supports multiple immutable third-party Python
  materializer plugins.
- passive `fetch` checks out an exact commit and validates
  `agora.materializer.json` against the registry without running packaging code;
- explicit `install --approve-code-execution` creates and integrity-records the
  managed Python runtime;
- `agora_materialize_registered.py` runs only an already-installed,
  integrity-verified registry plugin by plugin/materializer ID and delegates to the
  existing sandboxed host;
- the host supports standalone `output.format = text-fabric` artifacts. Consumer
  discovery/composition is separate and must not be implied by registry status.

The upstream CopticScriptorium-TF commit
`ce49555aaa6cb6618c5e1b97ddc8ce337e45e45f` contains:

- plugin id `copticscriptorium-tf`, version `0.1.0`,
  repository `alexsosn/CopticScriptorium-TF`;
- materializer id `copticscriptorium-text-fabric`;
- immutable automatic source acquisition at CopticScriptorium/corpora
  `3ac067f1709a0012daf39ea8da2fac79980176a5`;
- user-local directory acquisition;
- network-denied Python-module execution;
- native TF output under `tf/` plus `conversion-summary.json`.

The upstream project has no GitHub release yet, so this registration should remain
commit-pinned and should not invent release-tracking metadata. Verification should
start at `community`: upstream real Agora-host and native-TF regression evidence
exists, while this ticket adds the canonical Agora-side registered install/run smoke.

## Plan

1. RED: assert the canonical materializer registry contains the Coptic plugin at
   the exact upstream commit/version/materializer ID and that the install workflow
   contains a Coptic registered-run smoke. Preserve this failing state before edits.
2. Add the registry entry with explicit-code-execution trust, MIT software,
   upstream-dependent data, and community verification notes.
3. Extend the registered materializer workflow with an independent Coptic job:
   validate registry; resolve the registry pin; passive fetch; assert no managed
   environment exists yet; explicitly install; verify receipt/manifest/importability;
   create a tiny physical TT user-local fixture; run by registered IDs under the
   required Linux sandbox; verify native TF required files + operational summary.
4. Keep execution network-denied through the materializer manifest/sandbox. Do not
   add consumer-discovery or Context-Fabric claims.
5. Update registry documentation from the obsolete single-materializer wording.
6. Run exact-head Foundation/unit + registered materializer live workflow.
7. Freeze the head and perform a logically independent adversarial review grounded
   in the immutable upstream manifest, passive/install separation, run-by-ID code,
   sandboxed live artifact, and registry diff.

## Non-goals

No generic artifact cache, no feature-module parent binding, no Context-Fabric
consumer discovery/load claim, no Coptic scholarly/data-quality certification, and
no release-tracking invention before an upstream release exists.
