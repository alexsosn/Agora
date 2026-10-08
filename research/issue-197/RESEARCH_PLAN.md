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
`ca0ee11bec734858628b2a237c11acb463a63863` contains:

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
4. Keep execution network-denied through the materializer manifest/sandbox. Registration alone must not imply consumer discovery/load; after #196, a separate explicit public-API handoff acceptance may prove that boundary without coupling the systems.
5. Update registry documentation from the obsolete single-materializer wording.
6. Run exact-head Foundation/unit + registered materializer live workflow.
7. Freeze the head and perform a logically independent adversarial review grounded
   in the immutable upstream manifest, passive/install separation, run-by-ID code,
   sandboxed live artifact, and registry diff.

## Non-goals

No generic artifact cache, no feature-module parent binding, no automatic materializer-to-Context-Fabric orchestration, no Coptic scholarly/data-quality certification, and no release-tracking invention before an upstream release exists. The explicit `install_local_corpus` acceptance added after #196 is a consumer test of two existing public boundaries, not new orchestration.


## Registration pin refinement

Before finalization, the registration pin was advanced from the earlier reviewed
converter commit to `6b4c5d01135ffc56373c2513d87ab42f5b3c3487`, the current merged CopticScriptorium-TF main
at this integration gate. The materializer manifest, plugin/materializer IDs,
package version, acquisition contract, network denial, and Agora adapter are
unchanged between the two commits. The newer pin additionally includes the
merged fail-closed handling for empty supported TT containers plus the local
web-app and researcher-documentation slices. The live registered install/run
workflow must be rerun on the Agora exact head after this pin change.


After CopticScriptorium-TF #62 merged, the immutable registration pin was
advanced again to `ca0ee11bec734858628b2a237c11acb463a63863`. This commit changes installed-package/browser
packaging but not the materializer manifest or converter semantics. Because
Agora installs the repository as a Python project, the registered live smoke is
required to prove that the new Hatch wheel resource mapping does not disturb
explicit installation or sandboxed materialization.


## Materializer-to-consumer acceptance refinement

After Agora #196 merged, the remaining CopticScriptorium-TF #17 boundary became
testable end to end. Separate proofs of (a) registered materialization and
(b) generic local-TF import were not sufficient to claim the generated Coptic
artifact itself was discoverable/loadable through Context-Fabric.

The final acceptance job therefore takes the exact registered materializer
output at `coptic-output/tf`, switches to the Context-Fabric plugin's supported
Python 3.13 runtime, installs the real plugin/cfabric-mcp dependency set, starts
the stdio MCP server, and executes:

`install_local_corpus -> list_available_corpora -> prepare_corpus -> load_corpus -> search -> unload_corpus -> remove_cached_corpus`.

The test intentionally imports the already materialized native TF rather than
adding converter-to-consumer orchestration to either product. This proves the
documented handoff while preserving the ownership boundary: the materializer
produces TF; Context-Fabric imports and queries TF.


## Automatic Git acquisition acceptance

The CopticScriptorium-TF #17 contract also requires the Agora-acquired source
path, not only an equivalent user-local tree. The registration gate therefore
runs the registered materializer a second time without `--source`. This forces
Agora to select the manifest's pinned Git acquisition for
`CopticScriptorium/corpora@3ac067f1709a0012daf39ea8da2fac79980176a5`,
then executes the converter under the same required network-denied sandbox.

Because the canonical manifest intentionally describes the complete upstream
source tree, this is a full-corpus acceptance rather than a synthetic substitute.
The post-run check binds source provenance to the exact upstream commit and
rechecks stable full-corpus invariants already established by the upstream
converter regression: 2,628 source records, 2,394,354 word slots, 130 native TF
files, successful bare Text-Fabric reload, and section lookup for a real
Sahidic Mark record. The job timeout is raised to 35 minutes to preserve margin
around the previously measured roughly 8-minute full conversion.
