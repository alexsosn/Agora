# Materialize the CUC Burns feature module locally

Agora registers **CTC-TF** (Duncan Burns's *Contents, Texts and Contexts*) as a feature-only Text-Fabric producer over the immutable **Copenhagen Ugaritic Corpus (CUC) 0.2.8**. This is a *local* workflow, not a ChatGPT web-hosted action. The resulting annotations attach to **existing CUC nodes** and never replace `otype.tf`, `oslots.tf`, or `otext.tf`.

## Before running

Use a local Agora checkout with Python 3.13 for the Context-Fabric integration, a supported OS sandbox (Bubblewrap on Linux or `sandbox-exec` on macOS), and a directory of Burns Workbook **CSV** files organized in workbook subdirectories (matching `*/*.csv`). Obtain/prepare these source files lawfully using CTC-TF's upstream instructions. Agora **does not** download the restricted Burns Workbooks or publish any of their annotations.

The materializer is third-party Python code. Review its pinned manifest and package before approving execution. Passive acquisition is separate from an explicit installation:

```bash
python scripts/agora_install_materializer.py fetch cuc-burns
python scripts/agora_install_materializer.py install cuc-burns --approve-code-execution
```

No converter is imported, installed, or approved by `prepare_corpus` or by the materialization command below. If the materializer is not already installed and verified, the command fails closed.

## Produce the feature module

```bash
python -m scripts.agora_compose_feature_module --module cuc-burns --source /absolute/path/to/burns-csv
```

Optional flags are `--parent-version 0.2.8`, `--cache-dir /path/to/context-fabric-cache`, and `--install-root /path/to/approved-materializers`. Use the **same** installation root for the two installer commands and the materialization command when overriding the default; similarly use one Context-Fabric cache across materialization and loading.

Agora derives the producer (`cuc-burns-csv` from the reviewed, immutable CTC-TF pin) and the parent (`cuc`, version `0.2.8`) from its bundled catalog. It prepares the CUC source snapshot, keeps the parent read-only and leased while running the network-denied materializer, and publishes the feature files under:

```text
<AGORA_CORPUS_CACHE>/local-modules/cuc-burns/tf/0.2.8/
```

The default root follows Context-Fabric's cache configuration. A receipt named `agora-materialization.json` records the resolved parent version, immutable commit and sandbox. The command does **not** accept a raw parent path, arbitrary producer, forged `trusted` flag, or permission to install/execute unreviewed code. It refuses to replace an already published module; use a fresh cache or separately manage your old local result rather than overwriting it.

## Load/query with Context-Fabric

Start the Context-Fabric plugin using the same cache and request the CUC module explicitly:

```python
prepare_corpus(resource_id="cuc", version="0.2.8")
load_corpus(resource_id="cuc", modules=["cuc-burns"])
```

Then inspect the loaded Text-Fabric feature inventory before querying. Burns' modern native module uses lane-numbered features such as `burns_headword_1` and `burns_category_1`; these annotate already-existing CUC word IDs. A local module is snapshotted by content hash when Context-Fabric composes it, without copying or altering the CUC warp.

**Licensing and limitations:** Burns source material has the upstream restrictions currently recorded by Agora as **CC-BY-NC-ND-2.5**, with no authorization in this workflow to redistribute original Workbooks, generated CSV or derived Text-Fabric artifacts. This is an explicitly requested, local producer and consumer path; it is **not** automatic materialization on ordinary corpus discovery. Only the reviewed CUC parent release 0.2.8 is supported. Windows lacks the required network-denied sandbox and fails closed.
