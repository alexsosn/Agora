# SEDRA

Syriac lexical and morphological lookup against Beth Mardutho's Syriac Electronic Data Research Archive.

## Use this plugin for

- **Dictionary lookup** (`dictionary-lookup`)
- **Lexeme lookup** (`lexeme-lookup`)

## Access and resources

Agora's local read-only adapter queries Beth Mardutho's remote SEDRA IV word-form and lexeme endpoints. No SEDRA lexical data are vendored.

## What connects or runs

Agora ships a small read-only FastMCP adapter over Beth Mardutho's public SEDRA IV JSON word and lexeme endpoints; no SEDRA data is vendored.

## Local and remote behavior

Runtime mode: `local`.
Data mode: `remote`.
Runtime type: `python`.

## Prerequisites

Use the [installation guide](../installation.md) for current host prerequisites and supported installation paths. Keep client/platform support decisions separate from the plugin's scholarly capabilities; consult the [compatibility guide](../compatibility.md).

## Install

Install `sedra@agora` through a supported Agora host. Follow the [short installation path](../installation.md) rather than copying host UI steps from this page.

## First success

> Look up the Syriac word form ܡܠܟܐ, distinguish returned word-form data from lexeme data, and preserve ambiguous analyses rather than choosing one silently.

This is a bounded starting request, not a full tutorial. The first-success tutorial workstream can expand it without changing this page's capability contract.

## Typical research tasks

For agent-side morphology and ambiguity guidance, see the [SEDRA research skill](../../../plugins/sedra/skills/sedra-research/SKILL.md).

Canonical capabilities:

- **Dictionary lookup** (`dictionary-lookup`)
- **Lexeme lookup** (`lexeme-lookup`)

## Important limitations

Word-form results and lexeme records answer different questions. Preserve multiple returned analyses when the service is ambiguous instead of silently selecting one.

Registered plugin-level advisories:

No structured plugin-level known issues are currently registered.

## Disk, memory, and network

The canonical runtime is local while scholarly data are remote; normal provider operations require network access.

## Provenance and licensing

The plugin registry records:

- `software`: `MIT`
- `data`: `upstream-dependent`
- `service_terms`: `upstream-dependent`

These fields describe the plugin/software/service boundary. Corpus, edition, annotation, or hosted-data rights can remain resource- or upstream-specific.

## Troubleshooting

Start from the observed symptom in [installation troubleshooting](../installation.md#troubleshooting). For current client/platform evidence and structured advisories, use [compatibility and known limitations](../compatibility.md#current-upstream-limitations).

## Upstream

- Homepage/docs: https://sedra.bethmardutho.org/
