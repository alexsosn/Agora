#!/usr/bin/env python3
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SHARED_STATUS_DOCS = (
    "README.md",
    "wiki/README.md",
    "wiki/releases/v0.1-plan-active.md",
    "wiki/architecture/ref-implementation-details.md",
)
SHARED_BEGIN = "<!-- BEGIN AGORA V0.1 STATUS -->"
SHARED_END = "<!-- END AGORA V0.1 STATUS -->"


@dataclass(frozen=True)
class PluginVerificationFact:
    plugin_id: str
    name: str
    aggregate: str
    claude: str
    codex: str


@dataclass(frozen=True)
class ReleaseDocumentationFacts:
    plugins: tuple[PluginVerificationFact, ...]
    skills: tuple[str, ...]


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def derive_release_documentation_facts(root: Path = ROOT) -> ReleaseDocumentationFacts:
    root = Path(root)
    plugins_path = root / "registry/plugins.yaml"
    if not plugins_path.is_file():
        raise FileNotFoundError("registry/plugins.yaml")

    plugin_doc = _load_yaml(plugins_path)
    plugin_facts: list[PluginVerificationFact] = []
    for plugin in plugin_doc.get("plugins", []):
        clients = ((plugin.get("verification") or {}).get("clients") or {})
        plugin_facts.append(
            PluginVerificationFact(
                plugin_id=str(plugin["id"]),
                name=str(plugin.get("name") or plugin["id"]),
                aggregate=str(plugin["verification"]["status"]),
                claude=str(clients["claude"]["status"]),
                codex=str(clients["codex"]["status"]),
            )
        )

    skills = tuple(
        sorted(
            path.parent.name.join(("",))
            for path in []
        )
    )
    skill_ids = tuple(
        sorted(
            f"{path.parents[2].name}/{path.parent.name}"
            for path in (root / "plugins").glob("*/skills/*/SKILL.md")
        )
    )
    return ReleaseDocumentationFacts(
        plugins=tuple(plugin_facts),
        skills=skill_ids,
    )


def render_shared_status_block(facts: ReleaseDocumentationFacts) -> str:
    lines = [
        SHARED_BEGIN,
        "| v0.1 integration | Aggregate plugin status | Claude path | Codex path |",
        "| --- | --- | --- | --- |",
    ]
    for plugin in facts.plugins:
        lines.append(
            f"| {plugin.name} | `{plugin.aggregate}` | `{plugin.claude}` | `{plugin.codex}` |"
        )
    lines.extend(
        [
            "",
            (
                f"Phase 5 baseline: **{len(facts.skills)} implemented scholarly skills**. "
                "Additional resource-specific guidance is follow-up work, not an unstarted phase."
            ),
            SHARED_END,
        ]
    )
    return "\n".join(lines)


def _extract_block(text: str, begin: str, end: str) -> str | None:
    if text.count(begin) != 1 or text.count(end) != 1:
        return None
    start = text.index(begin)
    finish = text.index(end, start) + len(end)
    return text[start:finish]


def validate_release_documentation(root: Path = ROOT) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    try:
        facts = derive_release_documentation_facts(root)
    except (KeyError, TypeError, FileNotFoundError) as exc:
        return [f"release documentation facts: cannot derive canonical state: {exc}"]

    if not facts.plugins:
        errors.append("release documentation facts: no plugins found in registry/plugins.yaml")
        return errors

    expected = render_shared_status_block(facts)
    for relative in SHARED_STATUS_DOCS:
        path = root / relative
        if not path.is_file():
            errors.append(f"{relative}: missing high-level current-status document")
            continue
        actual = _extract_block(path.read_text(encoding="utf-8"), SHARED_BEGIN, SHARED_END)
        if actual is None:
            errors.append(
                f"{relative}: missing or ambiguous v0.1 status/skill summary block"
            )
        elif actual != expected:
            errors.append(
                f"{relative}: v0.1 status/skill summary block is stale relative to canonical registry/skill tree"
            )
    return errors


def main() -> int:
    errors = validate_release_documentation(ROOT)
    if errors:
        print("Release documentation consistency validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Release documentation status summaries match canonical registry and skill state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
