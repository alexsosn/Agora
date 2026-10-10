from __future__ import annotations

import argparse
import difflib
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "plugins.yaml"
OUTPUT_DIR = ROOT / "wiki" / "guides" / "plugins"

GUIDANCE: dict[str, dict[str, Any]] = {
    "context-fabric": {
        "access": (
            "Browse the [generated scholarly resource catalog](../resources.md) for registered "
            "corpora and collections. Resources are selected lazily; installing the plugin does "
            "not download the full catalog. Use `install_local_corpus` for "
            "[user-supplied native TF corpora and feature modules](../context-fabric-local-import.md)."
        ),
        "first_success": (
            "Using BHSA, inspect the available word features, then find a small set of occurrences "
            "of the lexeme MLK and report the exact features used."
        ),
        "tasks": (
            "Before constructing a corpus query, inspect the selected schema and annotation. "
            "Agent-side workflow guidance lives in the "
            "[generic Context-Fabric research skill]"
            "(../../../plugins/context-fabric/skills/context-fabric-research/SKILL.md); "
            "resource-specific BHSA, Ugaritic, Hittite, and Greek-collection skills remain alongside it."
        ),
        "cost_note": (
            "Historical load observations live in the resource catalog. First acquisition normally needs "
            "network access to the registered upstream Git source unless the exact required snapshots are "
            "already resident for offline use. For an unfamiliar resource, use "
            "`describe_available_corpus` → `prepare_corpus` → `load_corpus`, and inspect the "
            "[cache and cold-load guide](../context-fabric-cache.md) before an expensive load."
        ),
        "limitations": (
            "A plugin-level verification result does not promote every corpus or annotation layer. "
            "Use the resource catalog and compatibility evidence for the specific resource/path."
        ),
        "module_note": """## Registered BHSA cantillation module

The optional `bhsa-cantillation-trees` feature module attaches verse-level cantillation annotations to the **existing BHSA 2021** parent. It is not a separate corpus and does not require another BHSA download. Inspect `describe_available_corpus(resource_id="bhsa")`, then use the same parent and module selection for both preparation and load:

```text
prepare_corpus(resource_id="bhsa", version="2021", modules=["bhsa-cantillation-trees"])
load_corpus(resource_id="bhsa", version="2021", modules=["bhsa-cantillation-trees"], features=["g_cons", "cantillation_system", "cantillation_depth", "cantillation_alignment"])
```

Inspect the loaded schema and actual feature values before interpreting them. The live 10 October 2026 acceptance verified BHSA Genesis 1:1 words and cantillation `system=prose`, `depth=2`, and `alignment=exact` on BHSA verse node `1414389`; these are representative checks, **not** an audit of all verse alignments. The module's `sources.json` records the BHSA source commit `4db00e2157915495e1a4d3d57e41223df24775da`; the tested module source revision is `445413fa5267b5c1c637d523f07f8a4cf0b3dded`. Registry acquisition currently follows upstream refs, so review the resolved `source_revision` fields on each load; the version label alone does not establish node identity when upstream changes.

The BHSA parent corpus is listed under **CC BY-NC 4.0** in Agora, while the cantillation feature files declare **CC BY 4.0** and cite MorphHB provenance. Preserve attribution, source revisions, and the rights of *each* layer; loading the module does not relax the BHSA noncommercial restriction. The acceptance workflow downloads source data into runner-local caches and does not distribute converted corpora.""",
    },
    "perseus": {
        "access": (
            "The local plugin connects to remote Perseus and Scaife scholarly text services. "
            "There is no Agora-managed local corpus catalog for this plugin."
        ),
        "first_success": (
            "Discover Homer, resolve an Iliad edition in the service that exposes it, retrieve "
            "Iliad 1.1, and report the exact discovered URN and service path."
        ),
        "tasks": (
            "For agent-side source and routing guidance, see the "
            "[Perseus research skill](../../../plugins/perseus/skills/perseus-research/SKILL.md)."
        ),
        "limitations": (
            "Passage retrieval and Scaife-backed discovery/search remain separate supported paths. "
            "Provider-wide CTS navigation is not advertised: legacy CTS metadata/navigation can fail, "
            "and merged discovery can include Scaife-only works that CTS resource lookup does not resolve."
        ),
    },
    "sefaria": {
        "access": (
            "The plugin connects to Sefaria's official hosted Texts MCP and remote Sefaria Library. "
            "It does not install a local copy of the library."
        ),
        "first_success": (
            "Retrieve Genesis 1:1 in Hebrew and English and show linked classical commentaries for the verse."
        ),
        "tasks": (
            "For agent-side reference, search, and linked-text guidance, see the "
            "[Sefaria research skill](../../../plugins/sefaria/skills/sefaria-research/SKILL.md)."
        ),
        "limitations": (
            "Search can return duplicate references from separately indexed versions. Treat them as "
            "ambiguous search hits, not as an exact occurrence count; retrieve the selected reference/version "
            "before quantitative interpretation."
        ),
    },
    "sedra": {
        "access": (
            "Agora's local read-only adapter queries Beth Mardutho's remote SEDRA IV word-form and lexeme "
            "endpoints. No SEDRA lexical data are vendored."
        ),
        "first_success": (
            "Look up the Syriac word form ܡܠܟܐ, distinguish returned word-form data from lexeme data, "
            "and preserve ambiguous analyses rather than choosing one silently."
        ),
        "tasks": (
            "For agent-side morphology and ambiguity guidance, see the "
            "[SEDRA research skill](../../../plugins/sedra/skills/sedra-research/SKILL.md)."
        ),
        "limitations": (
            "Word-form results and lexeme records answer different questions. Preserve multiple returned "
            "analyses when the service is ambiguous instead of silently selecting one."
        ),
    },
}


def _load() -> list[dict[str, Any]]:
    with REGISTRY.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["plugins"]


def _humanize(value: str) -> str:
    text = value.replace("-", " ")
    return text[:1].upper() + text[1:]


def _capabilities(plugin: dict[str, Any]) -> str:
    return "\n".join(
        f"- **{_humanize(capability)}** (`{capability}`)"
        for capability in plugin.get("capabilities") or []
    )


def _licenses(plugin: dict[str, Any]) -> str:
    return "\n".join(
        f"- `{key}`: `{value}`" for key, value in (plugin.get("licenses") or {}).items()
    )


def _issues(plugin: dict[str, Any]) -> str:
    issues = (plugin.get("verification") or {}).get("known_issues") or []
    if not issues:
        return "No structured plugin-level known issues are currently registered."
    return "\n".join(
        f"- `{issue['id']}` — {issue['summary']}" for issue in issues
    )


def _cost_boundary(plugin: dict[str, Any], guidance: dict[str, Any]) -> str:
    runtime_mode = (plugin.get("runtime") or {}).get("mode", "unknown")
    data_mode = plugin.get("data_mode", "unknown")
    if runtime_mode == "local" and data_mode == "local":
        base = (
            "The canonical runtime and data mode are local; disk and memory use depend on "
            "the selected corpus and cache state."
        )
    elif runtime_mode == "local" and data_mode == "remote":
        base = (
            "The canonical runtime is local while scholarly data are remote; normal provider "
            "operations require network access."
        )
    elif runtime_mode == "hosted" and data_mode == "remote":
        base = (
            "The canonical runtime is hosted and scholarly data are remote; normal provider "
            "operations require network access."
        )
    else:
        base = (
            f"Runtime mode is `{runtime_mode}` and data mode is `{data_mode}`; "
            "consult the installation and compatibility guides for operational constraints."
        )
    note = guidance.get("cost_note")
    return f"{base} {note}" if note else base


def _upstream(plugin: dict[str, Any]) -> str:
    upstream = plugin.get("upstream") or {}
    lines: list[str] = []
    if upstream.get("repository"):
        repository = upstream["repository"]
        lines.append(f"- Repository: https://github.com/{repository}")
    if upstream.get("homepage"):
        lines.append(f"- Homepage/docs: {upstream['homepage']}")
    if upstream.get("endpoint"):
        lines.append(f"- Service endpoint: {upstream['endpoint']}")
    return "\n".join(lines) or "- No upstream link is registered."


def render(plugin: dict[str, Any]) -> str:
    plugin_id = plugin["id"]
    guidance = GUIDANCE[plugin_id]
    runtime = plugin.get("runtime") or {}
    runtime_type = runtime.get("type")
    runtime_type_line = f"\nRuntime type: `{runtime_type}`." if runtime_type else ""
    return f"""# {plugin['name']}

{plugin['description']}

## Use this plugin for

{_capabilities(plugin)}

## Access and resources

{guidance['access']}

## What connects or runs

{runtime.get('notes', 'See the canonical plugin registry for runtime details.')}

## Local and remote behavior

Runtime mode: `{runtime.get('mode', 'unknown')}`.
Data mode: `{plugin.get('data_mode', 'unknown')}`.{runtime_type_line}

## Prerequisites

Use the [installation guide](../installation.md) for current host prerequisites and supported installation paths. Keep client/platform support decisions separate from the plugin's scholarly capabilities; consult the [compatibility guide](../compatibility.md).

## Install

Install `{plugin_id}@agora` through a supported Agora host. Follow the [short installation path](../installation.md) rather than copying host UI steps from this page.

## First success

> {guidance['first_success']}

This is a bounded starting request, not a full tutorial. The first-success tutorial workstream can expand it without changing this page's capability contract.

## Typical research tasks

{guidance['tasks']}

Canonical capabilities:

{_capabilities(plugin)}

{guidance.get('module_note', '').strip() + chr(10) * 2 if guidance.get('module_note') else ''}## Important limitations

{guidance['limitations']}

Registered plugin-level advisories:

{_issues(plugin)}

## Disk, memory, and network

{_cost_boundary(plugin, guidance)}

## Provenance and licensing

The plugin registry records:

{_licenses(plugin)}

These fields describe the plugin/software/service boundary. Corpus, edition, annotation, or hosted-data rights can remain resource- or upstream-specific.

## Troubleshooting

Start from the observed symptom in [installation troubleshooting](../installation.md#troubleshooting). For current client/platform evidence and structured advisories, use [compatibility and known limitations](../compatibility.md#current-upstream-limitations).

## Upstream

{_upstream(plugin)}
"""


def expected_pages() -> dict[Path, str]:
    return {OUTPUT_DIR / f"{plugin['id']}.md": render(plugin) for plugin in _load()}


def check() -> bool:
    expected = expected_pages()
    actual_paths = set(OUTPUT_DIR.glob("*.md")) if OUTPUT_DIR.is_dir() else set()
    ok = True
    if actual_paths != set(expected):
        missing = sorted(path.name for path in set(expected) - actual_paths)
        extra = sorted(path.name for path in actual_paths - set(expected))
        if missing:
            print(f"Missing generated plugin pages: {', '.join(missing)}")
        if extra:
            print(f"Unexpected generated plugin pages: {', '.join(extra)}")
        ok = False

    for path, wanted in expected.items():
        if not path.exists():
            continue
        actual = path.read_text(encoding="utf-8")
        if actual == wanted:
            continue
        ok = False
        diff = difflib.unified_diff(
            actual.splitlines(),
            wanted.splitlines(),
            fromfile=str(path.relative_to(ROOT)),
            tofile="generated expectation",
            lineterm="",
        )
        print("\n".join(diff))
    return ok


def write() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path, content in expected_pages().items():
        path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail when generated pages are stale")
    args = parser.parse_args()
    if args.check:
        return 0 if check() else 1
    write()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
