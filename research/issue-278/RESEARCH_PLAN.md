# Issue #278 — released Pseudepigrapha-TF corpus 1.1 migration

Date: 2026-10-12. This is a researcher-facing prebuilt **corpus version update**, independent from the already merged Pseudepigrapha **converter/materializer** v1.1.0 pin. Do not rerun OCP conversion in Agora, mirror OCP, or silently revise prior explicitly pinned v1.0 user installations.

## Primary external release data (verified, not guessed)

- Public non-draft release: https://github.com/alexsosn/Pseudepigrapha-TF/releases/tag/v1.1.0 (2026-10-12), and immutable `refs/tags/v1.1.0` resolves to `39bd9fb895d1201e9cd9260170512fd8c399a3ac`.
- Native release asset `tf-1.1.zip`: **9,632,817 compressed bytes** and GitHub release-asset SHA256 **`88f23ac9106c6ea8b35f89b19d760cf5d4ee544a3f8d8262d6ed7e2092e447e9`**; another distinct `complete.zip` asset is for stock Text-Fabric and MUST NOT be used as Agora's flat TF archive.
- Other independent release assets: `dataset-manifest.json`, `conversion-report.json`. The upstream live publisher [38237268233](https://github.com/alexsosn/Pseudepigrapha-TF/actions/runs/38237268233) passed the published-byte and offline local load check according to source issue #278.
- The pinned upstream [DATA_LICENSE.md](https://github.com/alexsosn/Pseudepigrapha-TF/blob/39bd9fb895d1201e9cd9260170512fd8c399a3ac/DATA_LICENSE.md) explicitly retains CC BY 4.0 content from pinned OCP `c939dcbacad78c5d18d2c4282cad23c47e19ac07`, citing Scott/Penner and edition-level editors. The app GPL-3.0 licence and converter MIT licence are separate. Source-declared generated English/French versions remain distinct from historical textual witnesses.
- Release notes report manuscript apparatus refinements including previously missed TSol witnesses HI, L and VW; counts and sections need a *real* release-archive E2E check, not a speculative version-only success claim.

## Strict research / plan / RED / GREEN gates

1. Preserve old stable v1.0 pin in this research record, but change only the **current default resource** `id=pseudepigrapha` to the immutable release above. Existing user caches explicitly pinned to v1.0 must not be overwritten.
2. RED test: update `tests/test_pseudepigrapha_registration_226.py` pin SHA/asset/size/version, source ref and default versions, and add `tests/test_pseudepigrapha_corpus_278.py` asserting immutable v1.1 identity, licence evidence, converter-versus-corpus separation and exact catalog projection. Commit RED before canonical edits.
3. GREEN: update canonical `registry/resources.yaml`; regenerate `plugins/context-fabric/resources/catalog.yaml` losslessly via generator semantics (first 37 frozen v0.1 release resource IDs unchanged); keep generated researcher catalog in sync.
4. Update the existing [registered corpus consumer](https://github.com/alexsosn/Agora/blob/main/.github/workflows/pseudepigrapha-registered-corpus.yml) and its smoke script to demand v1.1 release SHA/source, **real public HTTPS download** and cold/warm offline TF semantics; retain release download SHA verification, citation, reading/witness, generated translation and CFM section-navigation checks. Where feasible assert TSol recovery on actual feature data, not without inspecting its encoding.
5. Full exact-head Foundation plus registered corpus consumer, license/source audit, generator/doc checks and logically independent skeptical review grounded in published bytes and actual Git diff. Do not merge without actual native TF load success.

Historic default v1.0 metadata: ref `7c4b757bb543a110ae9a252d1281835859136852`, tag `v1.0.0`, asset `tf-1.0.zip`, SHA256 `d2dfad7e643699617a9493b9f5d724868f8027dd5f2e88bd558451e3e7819b7a`, compressed bytes 9,632,449, version `1.0`.
