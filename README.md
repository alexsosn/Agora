# Agora

**Agora is a plugin marketplace that brings scholarly corpora, lexica, textual databases, and research services into AI-assisted philological workflows.**

It lets Claude Code and ChatGPT/Codex use research tools for Biblical Studies, Classics, Syriac, Ugaritic, Hittite, and related fields without requiring every resource to use the same backend or corpus format.

Agora currently includes four plugin families:

- **Context-Fabric** — structured local querying of registered Text-Fabric corpora, including BHSA, Ugaritic and Hittite corpora, and large Greek collections.
- **Perseus** — live access to Perseus/Scaife for text discovery, CTS navigation, passage retrieval, and search.
- **Sefaria** — Jewish texts, translations, links and commentaries, dictionaries, topics, and manuscript resources through the official Sefaria MCP.
- **SEDRA** — Syriac word-form and lexeme lookup against SEDRA IV.

Agora plugins can also include **scholarly skills**: source-specific guidance that tells the agent how to interpret corpus features, avoid common mistakes, and produce more reproducible research queries.

## What you can do

With the current v0.1 plugins you can, for example:

- query morphology and syntax in the **BHSA Hebrew Bible**;
- work with **Ugaritic** and **Hittite** Text-Fabric corpora through the same provider interface;
- discover and load individual works from large **Greek Text-Fabric collections** without installing one plugin per text;
- retrieve passages and search Classical texts through **Perseus/Scaife**;
- fetch source texts, translations, linked commentaries, and other resources from **Sefaria**;
- look up **Syriac** word forms and lexemes in SEDRA;
- ask the agent to inspect corpus schema and annotation before constructing a query instead of guessing feature names;
- keep corpus-specific research guidance alongside the tools that use it.

The current Context-Fabric catalog contains **37 registered upstream resources**. Corpora are acquired lazily, so installing the plugin does not download all of them.

## Installation

Agora currently targets **Claude Code** and **ChatGPT/Codex**. You only need to install the plugins relevant to your research.

### Claude Code

Inside Claude Code:

```text
/plugin marketplace add alexsosn/Agora
/plugin install context-fabric@agora
/plugin install perseus@agora
/plugin install sefaria@agora
/plugin install sedra@agora
/reload-plugins
```

You can install only one or two of these if that is all you need.

### ChatGPT / Codex

If your workspace supports GitHub marketplace import:

1. Open **Workspace settings → Plugins**.
2. Choose **Add → Import marketplace**.
3. Use `https://github.com/alexsosn/Agora` as the source.
4. Leave the path empty; Agora's marketplace file is at the repository root.
5. Import the marketplace and enable the plugins you need.

For local Codex development/testing:

```bash
git clone https://github.com/alexsosn/Agora.git
cd Agora
codex plugin marketplace add /absolute/path/to/Agora
codex plugin add context-fabric@agora
```

Replace `context-fabric` with `perseus`, `sefaria`, or `sedra` as needed.

Most local launch paths use [`uv`](https://docs.astral.sh/uv/). Context-Fabric currently requires Python 3.13; the SEDRA adapter requires Python 3.11 or later.

See the [full installation guide](wiki/guides/installation.md) for platform-specific details, updating, prerequisites, and validation.

## Example prompts

After installing the relevant plugin, you can ask the agent research questions directly. For example:

```text
Using BHSA, find the distribution of verbal stems for the lexeme MLK and show representative passages. Check the corpus feature names before querying and report the exact features you used.
```

```text
Find Iliad 1.1 in Perseus, retrieve the passage, and show what search or morphological information the current Perseus integration exposes for the first word.
```

```text
Using Sefaria, retrieve Genesis 1:1 in Hebrew and English and show the linked classical commentaries available for that verse.
```

```text
Look up this Syriac word in SEDRA, distinguish the returned word-form data from lexeme data, and preserve ambiguous analyses rather than choosing one silently: ܡܠܟܐ
```

For corpus research, Agora's bundled skills encourage the agent to inspect the selected resource's schema, annotation conventions, and limitations before interpreting results.

## Choosing a plugin

| Research task | Plugin |
|---|---|
| Hebrew Bible morphology and syntax | **Context-Fabric** |
| Ugaritic or Hittite corpus analysis | **Context-Fabric** |
| Structured Greek Text-Fabric corpora | **Context-Fabric** |
| Perseus/Scaife texts and CTS navigation | **Perseus** |
| Jewish texts, translations, commentaries, dictionaries | **Sefaria** |
| Syriac word and lexeme lookup | **SEDRA** |

Agora is designed to add more providers without forcing them into Text-Fabric or any other single data model.

## Verification scope

Agora verification covers installation, launch, transport, resource resolution, and representative integration operations. It does not assess whether an upstream corpus is suitable for a particular research use or maintain a parallel account of upstream data quality.

Use the resolved source revision to consult the original repository or corpus publisher's current documentation for semantics, limitations, and suitability. The four v0.1 integrations currently have live **Codex-path** verification; their aggregate plugin status remains `community` because the Claude paths currently have deterministic configuration evidence rather than equivalent live client-path evidence.

Plugin/client verification claims are bound to stable executable check IDs in `registry/verification-checks.yaml`. Live smoke artifacts record the check ID, exact Agora revision, timestamp, GitHub Actions run, runtime/platform, generated launch command, and configured dependency inputs, so a `verified` client claim can be traced to an actual executable check and run rather than a prose test name. See [`registry/README.md`](registry/README.md) for the evidence model.

For the detailed verification model and current implementation status, see [implementation details](wiki/architecture/ref-implementation-details.md).

## Documentation

- [Installation guide](wiki/guides/installation.md)
- [Wiki index](wiki/README.md)
- [v0.1 scope](wiki/releases/v0.1-scope-frozen.md)
- [Implementation details](wiki/architecture/ref-implementation-details.md)
- [Marketplace architecture](wiki/architecture/ref-marketplace-architecture.md)
- [Greek/Context-Fabric collection handling](wiki/architecture/ref-context-fabric-collections.md)
- [Current implementation plan](wiki/releases/v0.1-plan-active.md)
- [Contributing](CONTRIBUTING.md)

## Contributing

Agora follows an upstream-first model: where a good scholarly MCP or API already exists, the marketplace should normally integrate it rather than fork or vendor it.

A straightforward new philological integration should usually need canonical metadata, launch configuration, scholarly guidance, and smoke tests rather than changes throughout the core.

See [CONTRIBUTING.md](CONTRIBUTING.md) for repository conventions and contribution guidance.
