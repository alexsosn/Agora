from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _plugins() -> dict[str, dict]:
    with (ROOT / "registry/plugins.yaml").open("r", encoding="utf-8") as fh:
        return {item["id"]: item for item in yaml.safe_load(fh)["plugins"]}


def _known_issue_ids(plugin: dict) -> set[str]:
    return {
        item["id"]
        for item in plugin.get("verification", {}).get("known_issues", [])
    }


class TruthfulReleaseCapabilityTests(unittest.TestCase):
    def test_unfixed_upstream_limitations_are_structured(self):
        plugins = _plugins()

        self.assertIn(
            "sefaria/search-version-duplicates",
            _known_issue_ids(plugins["sefaria"]),
        )
        self.assertIn(
            "context-fabric/search-count-cache-cap",
            _known_issue_ids(plugins["context-fabric"]),
        )
        self.assertIn(
            "context-fabric/cuc-text-format-discovery",
            _known_issue_ids(plugins["context-fabric"]),
        )
        self.assertIn(
            "perseus/legacy-cts-malformed-navigation",
            _known_issue_ids(plugins["perseus"]),
        )

    def test_perseus_does_not_advertise_unreliable_cts_navigation(self):
        plugins = _plugins()
        self.assertNotIn("cts-navigation", plugins["perseus"]["capabilities"])

    def test_provider_skills_warn_on_known_unsafe_interpretations(self):
        context_fabric = (
            ROOT / "plugins/context-fabric/skills/context-fabric-research/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("10,000", context_fabric)
        self.assertIn("sign", context_fabric)
        self.assertIn("usign", context_fabric)

        sefaria = (
            ROOT / "plugins/sefaria/skills/sefaria-research/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("duplicate", sefaria.lower())
        self.assertIn("version", sefaria.lower())

        perseus = (
            ROOT / "plugins/perseus/skills/perseus-research/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("legacy CTS", perseus)
        self.assertIn("malformed", perseus.lower())

    def test_compatibility_guide_surfaces_provider_limitations(self):
        guide = (ROOT / "wiki/guides/compatibility.md").read_text(encoding="utf-8")
        for issue_id in (
            "sefaria/search-version-duplicates",
            "context-fabric/search-count-cache-cap",
            "context-fabric/cuc-text-format-discovery",
            "perseus/legacy-cts-malformed-navigation",
        ):
            self.assertIn(issue_id, guide)


if __name__ == "__main__":
    unittest.main()
