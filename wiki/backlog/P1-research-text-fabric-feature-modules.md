# Text-Fabric Feature/Data Modules Backlog

## Purpose

Agora's current Context-Fabric catalog is primarily a catalog of **main Text-Fabric corpora**. Text-Fabric also supports versioned **data modules**: additional `.tf` feature sets that are loaded alongside a parent corpus with `mod=...`. Some are declared by the parent app as standard modules in `provenanceSpec.moduleSpecs`; others are optional modules maintained in separate repositories or subdirectories.

This page records feature/data modules that are absent from the current Agora resource catalog or need explicit parent/child modelling. It is a discovery and integration backlog. Agora should describe, install, and expose upstream modules; it should not fork them, repair their scholarly data, redesign their behaviour, or add capabilities to third-party modules.

Research date: **2026-08-31**.

## What counts as a feature/data module

A candidate belongs here when all of the following are true:

- it is intended to extend an existing TF corpus rather than replace it;
- it contains loadable TF feature files, normally under a versioned `tf/<version>/` path;
- the module uses the node identity/versioning of a parent corpus;
- the upstream documentation, TF app configuration, or a working example treats it as loadable through Text-Fabric's `mod=` mechanism.

Do not infer modules from arbitrary repository directories. Notebooks, generated exports, `ner/`, teaching exercises, and preprocessing data are not marketplace feature modules unless there is a documented/versioned TF module surface.

## Discovery rules Agora should eventually automate

1. Inspect each parent corpus's `app/config.yaml`, especially `provenanceSpec.moduleSpecs`. These are the strongest signal for standard modules.
2. Search the repository for versioned `*/tf/<version>/*.tf` directories outside the core `tf/` dataset.
3. Search upstream documentation for `use(..., mod="...")` and CLI `--mod=...` examples.
4. Follow canonical successor repositories when old TF documentation points to an archived monorepo/subdirectory.
5. Record the **parent corpus version constraint**. TF modules are not generally version-independent just because the repository path is stable.
6. Record whether a module is `standard`, `optional`, `community`, `narrow-scope`, `legacy`, or `demo` separately from the parent corpus's status.
7. Treat a repository containing many feature files as one module bundle unless the upstream exposes independently meaningful installable bundles. Individual `.tf` files should not become dozens of Agora plugins.

The relevant Text-Fabric documentation is [Data Sharing](https://annotation.github.io/text-fabric/tf/about/datasharing.html), which describes data modules and `mod=`, and the app configuration convention documented through `moduleSpecs`. The Context-Fabric [corpora catalog](https://context-fabric.ai/docs/corpora) remains the baseline for parent corpora.

---

# P1 — current/high-value modules

## BHSA official pipeline family

The ETCBC pipeline documentation explicitly identifies `phono`, `parallels`, `valence`, `trees`, and `bridging` as repositories that derive additional data from BHSA core data and deliver it as Text-Fabric data modules. This is the canonical BHSA feature-module family and should be represented as children of `bhsa`, not as unrelated corpora.

Source: [`ETCBC/pipeline`](https://github.com/ETCBC/pipeline#bhsa-family).

### `ETCBC/phono/tf`

- **Parent:** `ETCBC/bhsa`
- **Adds:** phonological/phonetic transcriptions of Hebrew words.
- **Upstream class:** ETCBC official pipeline module.
- **Current app status:** declared in the current BHSA `app/config.yaml` `moduleSpecs` as **Phonetic Transcriptions**.
- **Agora action:** if already implicitly available through the parent app, still represent it in metadata so discovery can tell users that the module exists and whether it is loaded automatically.

### `ETCBC/parallels/tf`

- **Parent:** `ETCBC/bhsa`
- **Adds:** links between similar/parallel passages.
- **Upstream class:** ETCBC official pipeline module.
- **Current app status:** declared in the current BHSA `moduleSpecs` as **Parallel Passages**.
- **Agora action:** same modelling rule as `phono`; preserve it as a child module even if Text-Fabric treats it as standard.

### `ETCBC/trees/tf`

- **Parent:** `ETCBC/bhsa`
- **Adds:** tree structures for BHSA sentences.
- **Upstream class:** ETCBC official pipeline module.
- **Evidence:** listed in the BHSA family and pipeline as a module-producing repository.
- **Status nuance:** older Text-Fabric release documentation called `trees` a standard BHSA module; the current BHSA app configuration no longer lists it in `moduleSpecs`. Treat it as an official **optional** module unless runtime verification shows current automatic loading.
- **Agora action:** add as a discoverable optional BHSA feature module. This is the motivating omission for this audit.

### `ETCBC/valence/tf`

- **Parent:** `ETCBC/bhsa`
- **Adds:** verbal valence annotations for occurrences of selected verbs.
- **Upstream class:** ETCBC official pipeline module.
- **Evidence:** Text-Fabric's data-sharing documentation uses `tf bhsa --mod=etcbc/valence/tf` as an explicit module example.
- **Agora action:** add as an optional BHSA module and preserve corpus-version compatibility.

### `ETCBC/bridging/tf`

- **Parent:** `ETCBC/bhsa`
- **Adds:** Open Scriptures morphology ported/aligned to BHSA.
- **Upstream class:** ETCBC official pipeline module.
- **Agora action:** add as an optional BHSA module; record the third-party-data provenance separately from the ETCBC conversion code.

## BHSA additional maintained/community modules

### `ETCBC/heads/tf`

- **Parent:** `ETCBC/bhsa`
- **Adds:** phrase/clause head information and related head features.
- **Upstream:** [`ETCBC/heads`](https://github.com/ETCBC/heads).
- **Legacy path:** older Text-Fabric documentation uses `ETCBC/lingo/heads/tf`; `ETCBC/lingo` is archived and the standalone `ETCBC/heads` repository is the canonical target to investigate now.
- **Agora action:** add the standalone repository as the canonical candidate and retain the old path only as an alias/provenance note.

### `ETCBC/genre_synvar/tf`

- **Parent:** `ETCBC/bhsa`
- **Adds:** coarse verse-level genre labels from the Syntactic Variation project: `prose`, `poetry`, `prophetic`, `instruction`, and `list`.
- **Upstream:** [`ETCBC/genre_synvar`](https://github.com/ETCBC/genre_synvar).
- **TF data:** `tf/c/genre.tf` maps BHSA verse nodes to genre labels.
- **Agora action:** add as an optional BHSA annotation module. Verify how the `c` module version should be resolved against the currently supported BHSA versions before promotion.

### `CenterBLC/BHSaddons/tf`

- **Parent:** `ETCBC/bhsa`
- **Adds:** a bundle of additional BHSA features. The current repository contains versioned TF data for BHSA 2017/2021 and includes dictionary/gloss features, unaccented forms, word-order/interlinear data, Strong's data, BHS5-related data, and MT/LXX alignment/reference features among others.
- **Upstream:** [`CenterBLC/BHSaddons`](https://github.com/CenterBLC/BHSaddons).
- **Agora action:** catalog it as one feature bundle, not one marketplace entry per `.tf` file. Audit the provenance and data license of each feature family because the bundle combines several sources.

### `mr-martian/bhsa-ud-tf/tf`

- **Parent:** `ETCBC/bhsa` version `2021`.
- **Adds:** Universal Dependencies/MACULA-derived dependency relations and heads, UPOS, MACULA IDs, Strong's IDs, SDBH IDs/domains, and corresponding pronominal-suffix features.
- **Upstream:** [`mr-martian/bhsa-ud-tf`](https://github.com/mr-martian/bhsa-ud-tf).
- **Load example:** `use("ETCBC/bhsa", mod="mr-martian/bhsa-ud-tf/tf")` is documented by the repository.
- **License note:** the repository states that the treebank data are CC BY-SA 4.0; verify the provenance/licensing of all imported MACULA/SDBH/Strong's-derived fields separately.
- **Agora action:** strong community candidate because it exposes a substantially different syntactic annotation layer without modifying BHSA core.

## Nestle 1904 add-on bundle

### `CenterBLC/N1904/BOLcomplement/tf`

- **Parent:** `CenterBLC/N1904` version `1.0.0`.
- **Adds:** approximately 40 optional word-node features, grouped around Bible Online Learner, Aland Synoptics, lexical/morphological and teaching-oriented enrichments.
- **Upstream:** [`CenterBLC/N1904`](https://github.com/CenterBLC/N1904).
- **Documentation:** [`docs/additions/README.md`](https://github.com/CenterBLC/N1904/blob/main/docs/additions/README.md) explicitly documents loading with `mod="CenterBLC/N1904/BOLcomplement/tf/"`.
- **Agora action:** add as a first-class child module of `n1904`. Do not create a duplicate marketplace entry for `CenterBLC/N1904addons/AlandSynopsis`; those Aland features are represented in the documented `BOLcomplement` bundle and the separate repository is better treated as an upstream/incubator source unless runtime testing demonstrates a materially independent supported module.

## Dead Sea Scrolls parallels

### `ETCBC/dss/parallels/tf`

- **Parent:** `ETCBC/dss`.
- **Adds:** parallel/similar passage links.
- **Current app status:** the current DSS `app/config.yaml` declares **Parallel Passages** in `provenanceSpec.moduleSpecs` with `relative: parallels/tf`.
- **Agora action:** represent the standard child module explicitly even if Text-Fabric auto-loads it with DSS.

---

# P2 — narrower/community modules

These are real TF extensions, but they need more provenance/version/licensing work or cover only a restricted portion of the parent corpus.

## BHSA participant/coreference module

### `ch-jensen/participants/actor/tf`

- **Parent:** `ETCBC/bhsa`.
- **Scope:** Leviticus 17–26 rather than the whole Hebrew Bible.
- **Adds:** `actor`, `prs_actor`, and `coref` features for participant reference tracking and network analysis.
- **Upstream:** [`ch-jensen/participants`](https://github.com/ch-jensen/participants).
- **Evidence:** Text-Fabric's official data-sharing documentation uses this path as an example of an external data module; the repository itself describes the three features as extra TF modules.
- **License:** CC BY-NC 4.0 according to the repository README.
- **Agora action:** include as a narrow-scope community annotation module with an explicit passage coverage field so users do not infer whole-corpus coverage.

## BHSA Strong's feature

### `cbop-dev/tf-bhsa-strongs/tf`

- **Parent:** `ETCBC/bhsa` version `2021`.
- **Adds:** `strongs` references on word nodes.
- **Upstream:** [`cbop-dev/tf-bhsa-strongs`](https://github.com/cbop-dev/tf-bhsa-strongs).
- **Evidence:** the README documents `mod="cbop-dev/tf-bhsa-strongs/tf"`; the repository contains `tf/2021/strongs.tf`.
- **Caveat:** no repository license file was found in this audit. It also overlaps with Strong's-related features in `BHSaddons` and `bhsa-ud-tf`.
- **Agora action:** verify licensing and choose whether it offers a reason to expose it separately from broader bundles.

## BHSA BDB/Strong's feature bundle

### `cbop-dev/bhsa-bdb/tf`

- **Parent:** `ETCBC/bhsa` version `2021`.
- **Adds:** `bdb_entry` plus `strongs` features.
- **Upstream:** [`cbop-dev/bhsa-bdb`](https://github.com/cbop-dev/bhsa-bdb).
- **Evidence:** versioned `tf/2021/bdb_entry.tf` and `tf/2021/strongs.tf` are present; the README describes it as an additional BHSA Text-Fabric feature.
- **Caveat:** no repository license file was found in this audit, and redistribution rights for the lexicon-derived content need explicit review.
- **Agora action:** keep in backlog pending rights/provenance verification. Do not bundle or redistribute the data merely because it is technically loadable.

---

# P2 — legacy/archived but genuine TF modules

These matter for completeness and for users of the corresponding parent corpora, but they should be visibly marked as archived/legacy rather than presented as current defaults.

## Descartes similar sentences

### `CLARIAH/descartes-tf/parallels/tf`

- **Parent:** `CLARIAH/descartes-tf`.
- **Adds:** similar-sentence links.
- **Evidence:** the parent app declares `moduleSpecs` with corpus `Similar Sentences` and `relative: parallels/tf`.
- **Status:** parent repository is archived on GitHub.
- **Agora action:** retain as an archived standard child module if the Descartes corpus remains catalogued.

## Cuneiform/Qur'an similarity modules

The following parent repositories contain a versioned `parallels/tf` data module even though their current app configurations do not declare it in `moduleSpecs`:

- [`Nino-cunei/oldassyrian/parallels/tf`](https://github.com/Nino-cunei/oldassyrian/tree/master/parallels/tf) — Old Assyrian; contains a versioned `sim.tf` feature.
- [`Nino-cunei/oldbabylonian/parallels/tf`](https://github.com/Nino-cunei/oldbabylonian/tree/master/parallels/tf) — Old Babylonian letters.
- [`Nino-cunei/ninmed/parallels/tf`](https://github.com/Nino-cunei/ninmed/tree/master/parallels/tf) — Nineveh Medical Encyclopedia.
- [`q-ran/quran/parallels/tf`](https://github.com/q-ran/quran/tree/master/parallels/tf) — Qur'anic Arabic corpus.

The parent repositories are archived. Agora should catalog these only as legacy optional children, with exact parent-version compatibility verified before offering installation.

## Banks similarity demo module

### `annotation/banks/sim/tf`

- **Parent:** `annotation/banks`.
- **Adds:** similarity data used in Text-Fabric's module-sharing examples.
- **Evidence:** Text-Fabric's official data-sharing documentation demonstrates `use("annotation/banks", mod="annotation/banks/sim/tf")`.
- **Agora action:** keep as a demo/reference module rather than a scholarly marketplace priority. It is useful for testing generic feature-module support.

---

# Explicit non-candidates / deduplication notes

## `ETCBC/lingo/heads/tf`

Older TF documentation points here, but `ETCBC/lingo` is archived. Prefer the standalone [`ETCBC/heads`](https://github.com/ETCBC/heads) repository and retain the legacy path only for compatibility/provenance research.

## `CenterBLC/N1904addons/AlandSynopsis`

This repository contains standalone Aland synopsis feature files, but the current N1904 documentation exposes the Aland-related additions inside `CenterBLC/N1904/BOLcomplement/tf`. Avoid duplicate marketplace entries unless testing establishes a separately supported use case/version line.

## `ETCBC/dss/exercises/tf`

The repository contains versioned exercise TF files such as `cert.tf`, but this audit found no current app declaration or product documentation treating the directory as a reusable DSS feature module. Do not catalog it without stronger upstream evidence.

## `dtrlanz/bhsa-misc`

GitHub search surfaces this repository for BHSA/Text-Fabric, but it consists of notebooks and has no versioned TF module directory. It is not a feature module.

## `ETCBC/bhsa-min`

This is a separately loadable reduced corpus, not an extension module of BHSA core. Keep it in corpus/variant modelling if Agora wants it; do not classify it as a feature module.

---

# Proposed Agora metadata model

The existing Context-Fabric catalog currently represents parent resources such as `bhsa`, `dss`, `n1904`, `oldassyrian`, and `quran` as corpora. Feature modules need an explicit relationship to those resources. A minimal candidate shape is:

```yaml
- id: bhsa-trees
  name: BHSA sentence trees
  plugin: context-fabric
  provider: context-fabric
  kind: feature-module
  parent: bhsa
  upstream:
    repository: ETCBC/trees
    module: ETCBC/trees/tf
  compatibility:
    parent_versions: [2021]
  module:
    status: optional
    load_strategy: text-fabric-mod
```

The exact schema can differ, but the following information should be representable:

- stable module ID;
- parent resource ID;
- exact Text-Fabric `mod` specification;
- parent corpus version(s);
- module version if independently versioned;
- standard vs optional vs community vs archived/demo status;
- feature names or a short feature-group description;
- scope/coverage when partial;
- upstream repository and canonical/legacy aliases;
- data provenance and data license independently of software license;
- lazy acquisition/install behaviour;
- verification status.

A feature module should remain owned by its upstream repository. Agora's implementation should add discovery/install metadata and generic loading support, not copy module logic or data into Agora.

# Acceptance criteria for eventual implementation

1. Agora can represent a feature module as a child of an existing TF corpus without pretending it is a standalone corpus.
2. The catalog records the exact `mod=` path and compatible parent version(s).
3. Standard modules from `provenanceSpec.moduleSpecs` can be discovered or reconciled automatically.
4. Optional modules can be installed/selected independently without modifying upstream code.
5. Archived/demo/community status is visible to users and agents.
6. License/provenance status belongs to the module and is not inherited blindly from the parent corpus.
7. Partial-coverage modules expose their coverage limits.
8. Duplicate/legacy aliases resolve to one canonical catalog entry when appropriate.
9. Tests load the parent corpus plus the selected module and verify that expected additional features become available.
10. The feature-module mechanism remains generic; no BHSA-specific code should be needed beyond metadata and tests for known modules.

# Sources checked

Primary documentation and upstream repositories used in this audit:

- Context-Fabric corpus catalog: <https://context-fabric.ai/docs/corpora>
- Text-Fabric data sharing/module documentation: <https://annotation.github.io/text-fabric/tf/about/datasharing.html>
- ETCBC BHSA pipeline/family: <https://github.com/ETCBC/pipeline>
- BHSA app configuration: <https://github.com/ETCBC/bhsa/blob/master/app/config.yaml>
- DSS app configuration: <https://github.com/ETCBC/dss/blob/master/app/config.yaml>
- Descartes TF app configuration: <https://github.com/CLARIAH/descartes-tf/blob/main/app/config.yaml>
- N1904 add-on documentation: <https://github.com/CenterBLC/N1904/blob/main/docs/additions/README.md>
- `ETCBC/heads`: <https://github.com/ETCBC/heads>
- `ETCBC/genre_synvar`: <https://github.com/ETCBC/genre_synvar>
- `CenterBLC/BHSaddons`: <https://github.com/CenterBLC/BHSaddons>
- `ch-jensen/participants`: <https://github.com/ch-jensen/participants>
- `mr-martian/bhsa-ud-tf`: <https://github.com/mr-martian/bhsa-ud-tf>
- `cbop-dev/tf-bhsa-strongs`: <https://github.com/cbop-dev/tf-bhsa-strongs>
- `cbop-dev/bhsa-bdb`: <https://github.com/cbop-dev/bhsa-bdb>
- `annotation/banks`: <https://github.com/annotation/banks>

## Audit result

The current Agora Context-Fabric catalog contains the parent corpora but no `kind: feature-module` entries. The highest-confidence omissions are the official BHSA pipeline modules (especially `trees`, `valence`, and `bridging`), BHSA `heads`, N1904 `BOLcomplement`, DSS parallels, and the maintained/community BHSA enrichment modules listed above. The archived `parallels/tf` families should be retained only with explicit legacy status.
