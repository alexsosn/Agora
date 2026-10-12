from __future__ import annotations

import argparse
import difflib
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "plugins.yaml"
OUTPUT_DIR = ROOT / "wiki" / "guides" / "plugins"


TROUBLESHOOTING_EXITS = {
    "context-fabric": "If a corpus load stalls, see [cold-load recovery](../troubleshooting.md#corpus-acquisition-or-compilation-appears-stuck); for result interpretation, see the [10,000-count cap](../troubleshooting.md#search-count-stops-at-10000) and [CUC text-format discovery](../troubleshooting.md#cuc-text-formats-appear-missing).",
    "perseus": "If passage retrieval works but legacy navigation fails, see [Perseus navigation recovery](../troubleshooting.md#perseus-passage-works-but-navigation-fails).",
    "sefaria": "For repeated search references, see [Sefaria duplicate-reference recovery](../troubleshooting.md#sefaria-search-repeats-a-reference).",
    "sedra": "For failed live word or lexeme lookup, see [remote lookup recovery](../troubleshooting.md#remote-lookup-fails)."
    "cal": "For HTTP 429, upstream outages, or CAL token/lexicon errors, see [remote lookup recovery](../troubleshooting.md#remote-lookup-fails); do not retry aggressively.",
} 

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
            "network access to the registered upstream source (Git metadata or a checksum-pinned GitHub Release ZIP), unless the exact required snapshots are "
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
    "cal": {
        "access": (
            "CAL-MCP is a local Python stdio MCP server installed from the published "
            "`cal-mcp==0.1.0` package. It queries remote Comprehensive Aramaic Lexicon (CAL) "
            "pages on demand; Agora never downloads or mirrors the CAL text database."
        ),
        "first_success": (
            "Use `cal_lexicon_lookup` with query `br` and lemma_key `br N`. Report the "
            "returned `found` status, exact entry and CAL provenance, or distinguish a "
            "genuine CAL upstream error. Do not expand this into a vocabulary crawl."
        ),
        "tasks": (
            "Use the published [CAL-MCP integration guide]"
            "(https://github.com/alexsosn/CAL-MCP/blob/v0.1.0/docs/integrations/standalone-mcp.md) "
            "and the [Agora CAL research handoff](../../../plugins/cal/README.md). "
            "Keep lexical ambiguity, citation, editorial status and remote service provenance visible."
        ),
        "cost_note": (
            "A successful lexicon lookup normally makes two real CAL requests: one browse GET "
            "and one entry GET. The upstream client enforces request pacing, rolling caps and "
            "a cooldown after CAL 429. Do not use multi-page sweeps or unchecked retries."
        ),
        "limitations": (
            "The `community` client verification describes proposed integration evidence, not "
            "a fully verified Agora install or guaranteed remote availability. CAL's textual "
            "and bibliographic data are upstream-dependent and are not relicensed by MIT. "
            "A single found lexeme never establishes exhaustive corpus coverage."
        ),
    },
}


# The ORACC paragraph is maintained here so the generated researcher page
# remains in sync with the pinned canonical resource contract.
GUIDANCE["context-fabric"]["module_note"] = "## Released Assyrian royal inscriptions (ORACC-TF)\n\nThe registered `assyrian-royal-inscriptions` corpus is the pinned RIAO+RINAP dataset from [ORACC-TF v1.0.0](https://github.com/alexsosn/ORACC-TF/releases/tag/v1.0.0). Agora downloads only the published standalone ZIP (41.3 MB), verifies its exact SHA-256 against the registry, validates native TF feature data and pins the bundled provenance manifest by the verified archive digest, then prepares an evictable managed snapshot. **No clone of the multi-GB builder repository and no converter execution are required.** Use:\n\n```text\ndescribe_available_corpus(resource_id=\"assyrian-royal-inscriptions\")\nprepare_corpus(resource_id=\"assyrian-royal-inscriptions\")\nload_corpus(resource_id=\"assyrian-royal-inscriptions\", features=[\"document_key\", \"line\", \"form\", \"utf8\", \"cf\", \"gw\", \"translation_text\", \"translation_line\", \"synthetic\"])\n```\n\nOnce the exact asset has been prepared, `source_mode=\"offline\"` allows repeat prepare/load without another download, provided the managed cache has not been pruned or altered. A `source_revision` for this acquisition is the **64-hex archive SHA-256** rather than a 40-hex Git commit; `acquisition.archive` metadata in resource discovery records the pinned release asset identity; the upstream Git tag target is recorded separately as `source.configured_ref`. The bundled ZIP's standalone Text-Fabric **web app and researcher manual** are upstream assets, not installed/executed through Agora's data-only MCP loader.\n\nFor research, select documents using the **qualified** `document_key` (e.g. `riao/ria1:Q001801`), not a bare Q-number. Sign-level `synthetic=1` nodes are empty technical anchors rather than written signs. Official TEI running translations have incomplete coverage, especially for `rinap5p1`; aligned TEI units may themselves contain untranslated editorial placeholders. See the [upstream query guide](https://github.com/alexsosn/ORACC-TF/blob/v1.0.0/docs/reference/query-guide.md) and [limitations](https://github.com/alexsosn/ORACC-TF/blob/v1.0.0/docs/reference/known-issues.md).\n\nRights remain **component-specific**: some ORACC corpusjson metadata state CC0 where the project/edition asserts CC BY-SA 3.0, and the official TEI translations require separate attribution/terms. The converter's MIT licence does not relicense the textual data; consult the [source licence scope](https://github.com/alexsosn/ORACC-TF/blob/v1.0.0/LICENSE_SCOPE.md)." + "\n\n" + GUIDANCE["context-fabric"]["module_note"]



# Published archive corpus guidance is authored once here, then rendered into the
# generated Context-Fabric researcher guide.
GUIDANCE["context-fabric"]["module_note"] = "## Published Online Critical Pseudepigrapha (Pseudepigrapha-TF)\n\nThe registered `pseudepigrapha` corpus is the native Text-Fabric **1.0** dataset from [Pseudepigrapha-TF v1.0.0](https://github.com/alexsosn/Pseudepigrapha-TF/releases/tag/v1.0.0). Agora fetches only checksum-pinned `tf-1.0.zip` (9.63 MB), installs source features lazily and permits later offline reload. No OCP clone or converter execution is needed; the `pseudepigrapha-tf` materializer remains separately available for explicit source rebuilding.\n\nUse `describe_available_corpus(resource_id=\"pseudepigrapha\")`, then `prepare_corpus(resource_id=\"pseudepigrapha\")` and `load_corpus(resource_id=\"pseudepigrapha\", features=[\"source_ref\", \"version_id\", \"version_kind\", \"reading_of\", \"witness\", \"is_primary\", \"translation_of\", \"translation_unit_of\"])`. Look up `(\"1En__Ethiopic\", \"1\", \"2\")` as a source-version-qualified section and inspect the literal `source_ref`. Multiple source versions are not automatically aligned; omitted and unattested witnesses are distinct. OCP-generated English/French translations use `version_kind=generated_translation` and explicit translation links. They are **not historical manuscript witnesses**.\n\nData rights are **CC BY 4.0** for the pinned OCP text/TEI scope, requiring OCP's general citation and per-work/editor attribution. The OCP application has GPL-3.0 terms and the converter is MIT; neither replaces corpus text rights. See the pinned [data licence and provenance](https://github.com/alexsosn/Pseudepigrapha-TF/blob/v1.0.0/DATA_LICENSE.md) and [feature reference](https://github.com/alexsosn/Pseudepigrapha-TF/blob/v1.0.0/docs/features/0_home.md)." + "\n\n" + GUIDANCE["context-fabric"]["module_note"]


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

Follow the [first-success walkthrough](../first-success/{plugin_id}.md) for a short post-installation workflow, expected success signal, and interpretation limits.

## Typical research tasks

{guidance['tasks']}

See the [human scholarly guidance](../scholarly-guidance.md) for direct links to source-specific research-method sections maintained with the agent skills.

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

Start from [symptom-based troubleshooting](../troubleshooting.md), with [compatibility and known limitations](../compatibility.md#current-upstream-limitations) for client and upstream boundaries.\n\n{TROUBLESHOOTING_EXITS[plugin_id]}

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
