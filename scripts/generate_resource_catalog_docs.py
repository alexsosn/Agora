from __future__ import annotations

import argparse
import difflib
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "registry" / "resources.yaml"
FEATURE_MODULES = ROOT / "registry" / "feature-modules.yaml"
RELEASE_SCOPE = ROOT / "registry" / "v0.1.yaml"
OUTPUT = ROOT / "wiki" / "guides" / "resources.md"


def _load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _humanize(value: str) -> str:
    text = value.replace("-", " ")
    return text[:1].upper() + text[1:]


def _cell(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _join(values: list[str]) -> str:
    return ", ".join(_humanize(value) for value in values) if values else "—"


def _rights(item: dict[str, Any]) -> str:
    licenses = item.get("licenses") or {}
    data = licenses.get("data", "unknown")
    redistribution = licenses.get("redistribution", "unknown")
    evidence = (licenses.get("evidence") or {}).get("status")
    parts = [f"`{_cell(data)}`", _cell(redistribution)]
    if evidence:
        parts.append(_cell(evidence))
    return " · ".join(parts)


def _upstream(item: dict[str, Any]) -> str:
    repository = (item.get("upstream") or {}).get("repository")
    if not repository:
        return "—"
    return f"[{repository}](https://github.com/{repository})"


def _access(item: dict[str, Any]) -> str:
    lazy = (item.get("acquisition") or {}).get("lazy")
    suffix = "lazy" if lazy else "eager/unspecified"
    if item.get("kind") == "collection":
        return f"Collection · {suffix} members"
    return f"Corpus · {suffix} acquisition"


def _resource_row(item: dict[str, Any]) -> str:
    resource_id = item["id"]
    name = _cell(item["name"])
    description = _cell(item.get("description"))
    resource = f"<!-- resource:{resource_id} --> **{name}** (`{resource_id}`)<br>{description}"
    return "| " + " | ".join(
        [
            resource,
            _join(item.get("languages") or []),
            _join(item.get("disciplines") or []),
            _cell(item.get("period")),
            _access(item),
            _rights(item),
            _humanize((item.get("verification") or {}).get("status", "unknown")),
            _upstream(item),
        ]
    ) + " |"


def _format_seconds(value: Any) -> str:
    if isinstance(value, dict):
        return f"{value.get('min', '?')}–{value.get('max', '?')} s"
    return f"{value} s"


def _load_observation(item: dict[str, Any]) -> str:
    cost = item["load_cost"]
    measurement = cost.get("measurement") or {}
    facts: list[str] = []
    for key, label in (
        ("source_size_mb", "source"),
        ("compiled_size_mb", "compiled"),
        ("total_cache_mb", "total cache"),
        ("peak_rss_mb", "peak RSS"),
        ("typical_member_cache_mb", "typical member cache"),
        ("discovery_cache_mb", "discovery cache"),
    ):
        if key in cost:
            facts.append(f"{label} {cost[key]} MB")
    if "first_load_seconds" in cost:
        facts.append(f"first load {_format_seconds(cost['first_load_seconds'])}")
    if "warm_load_seconds" in cost:
        facts.append(f"warm load {_format_seconds(cost['warm_load_seconds'])}")
    if "typical_member_first_load_seconds" in cost:
        facts.append(
            "typical member first load "
            + _format_seconds(cost["typical_member_first_load_seconds"])
        )
    if "discovery_seconds" in cost:
        facts.append(f"discovery {_format_seconds(cost['discovery_seconds'])}")

    measured = measurement.get("checked_at", "date not recorded")
    environment = _cell(measurement.get("environment"))
    notes = _cell(cost.get("notes"))
    return (
        f"- **{_cell(item['name'])}** (`{item['id']}`) — measured {measured}: "
        + "; ".join(facts)
        + f". Environment: {environment}. Notes: {notes}"
    )


def _known_issue_lines(resources: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in resources:
        for issue in (item.get("verification") or {}).get("known_issues") or []:
            lines.append(
                f"- **{_cell(item['name'])}** (`{item['id']}`), `{issue['id']}` — "
                f"{_cell(issue.get('summary'))}"
            )
    return lines


def _module_row(module: dict[str, Any]) -> str:
    module_id = module["id"]
    label = (
        f"<!-- feature-module:{module_id} --> **{_cell(module['name'])}** (`{module_id}`)"
        f"<br>{_cell(module.get('description'))}"
    )
    versions = (module.get("compatibility") or {}).get("parent_versions") or []
    status = (module.get("module") or {}).get("status", "unknown")
    return "| " + " | ".join(
        [
            label,
            f"`{module['parent']}`",
            _humanize(status),
            ", ".join(f"`{version}`" for version in versions) or "—",
            _join(module.get("languages") or []),
            _rights(module),
            _humanize((module.get("verification") or {}).get("status", "unknown")),
            _upstream(module),
        ]
    ) + " |"


def render() -> str:
    resource_doc = _load(RESOURCES)
    module_doc = _load(FEATURE_MODULES)
    scope = _load(RELEASE_SCOPE)

    by_id = {item["id"]: item for item in resource_doc["resources"]}
    required = scope["required_resources"]
    missing = [resource_id for resource_id in required if resource_id not in by_id]
    if missing:
        raise ValueError(f"Required resources missing from registry: {missing}")
    resources = [by_id[resource_id] for resource_id in required]
    modules = module_doc["resources"]

    lines = [
        "# Scholarly resource catalog",
        "",
        "This page is generated from Agora's canonical registry. It describes the resources currently selectable through the **Context-Fabric plugin**; installing the plugin does not download every resource.",
        "",
        "**Integration evidence** (`Experimental`, `Community`, `Verified`) describes Agora's integration/load evidence. It **does not certify scholarly quality** or suitability of an edition, annotation layer, or dataset.",
        "",
        "Rights are reported from the canonical data-licensing evidence. `component-specific`, `member-specific`, and `unresolved` are intentionally visible states; `unknown` is not silently treated as open data.",
        "",
        "Load-cost values below are **historical measurements** tied to the recorded machine, revision, and date. They are **not requirements or predictions** for another environment.",
        "",
        "## Resources",
        "",
        "| Resource | Languages | Disciplines | Period | Kind / access | Rights | Integration evidence | Upstream |",
        "|---|---|---|---|---|---|---|---|",
    ]
    lines.extend(_resource_row(item) for item in resources)

    collections = [item for item in resources if item.get("kind") == "collection"]
    lines.extend(
        [
            "",
            "## Collections",
            "",
            "Collection members are not enumerated on this page. Collection indexes are snapshot-specific and can contain many independently selectable corpora; after installing Context-Fabric, discover the selected collection's members and preserve the returned member ID and source revision in reproducible work.",
            "",
        ]
    )
    for item in collections:
        lines.append(f"- **{_cell(item['name'])}** (`{item['id']}`) — members are acquired lazily.")

    measured = [item for item in resources if item.get("load_cost")]
    lines.extend(
        [
            "",
            "## Historical load observations",
            "",
        ]
    )
    lines.extend(_load_observation(item) for item in measured)

    known_issues = _known_issue_lines(resources)
    if known_issues:
        lines.extend(["", "## Known integration limitations", ""])
        lines.extend(known_issues)

    lines.extend(
        [
            "",
            "## Annotation modules",
            "",
            "These are selectable feature modules attached to a parent corpus. They are not standalone plugins or corpora. A previously unseen module combination can require parent-scale compilation/cache work; inspect the Context-Fabric preflight before an expensive load.",
            "",
            "| Module | Parent | Status | Compatible parent versions | Languages | Rights | Integration evidence | Upstream |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    lines.extend(_module_row(module) for module in modules)
    lines.extend(
        [
            "",
            "For acquisition/compile limits and module-overlay cost behavior, see [Context-Fabric cache and cold-load safety](context-fabric-cache.md).",
            "",
            "For client/platform support and the meaning of integration evidence, see [Compatibility and verification](compatibility.md).",
            "",
        ]
    )
    return "\n".join(lines)


def check() -> bool:
    expected = render()
    if not OUTPUT.exists():
        print(f"Missing generated file: {OUTPUT.relative_to(ROOT)}")
        return False
    actual = OUTPUT.read_text(encoding="utf-8")
    if actual == expected:
        return True
    diff = difflib.unified_diff(
        actual.splitlines(),
        expected.splitlines(),
        fromfile=str(OUTPUT.relative_to(ROOT)),
        tofile="generated expectation",
        lineterm="",
    )
    print("\n".join(diff))
    return False


def write() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail when the committed catalog is stale")
    args = parser.parse_args()
    if args.check:
        return 0 if check() else 1
    write()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
