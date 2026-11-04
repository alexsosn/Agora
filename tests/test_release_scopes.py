"""Release-scope contracts: the frozen v0.1 scope stays untouched while
prospective scopes (registry/v1.1.yaml and onward) extend it, and marketplace
generation targets the newest scope.

These back the review requirement that new plugins become discoverable
through a separate future-scope plan instead of mutating the frozen v0.1
release, and that concurrent prospective candidates (such as the in-flight
CAL-MCP record) can land in the same scope file without either overwriting
the other's inclusion.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.generate_marketplaces import render_outputs
from scripts.validate_registry import (
    ROOT,
    latest_release_scope,
    release_scope_paths,
)

FROZEN_PLUGINS = ["context-fabric", "perseus", "sefaria", "sedra"]


def _scope(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class ReleaseScopeFileTests(unittest.TestCase):
    def test_scope_paths_sort_by_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp)
            for name in ("v1.1.yaml", "v0.1.yaml", "v1.2.yaml"):
                (registry / name).write_text("schema_version: 1\n", encoding="utf-8")
            names = [path.name for path in release_scope_paths(registry)]
            self.assertEqual(names, ["v0.1.yaml", "v1.1.yaml", "v1.2.yaml"])
            self.assertEqual(latest_release_scope(registry).name, "v1.2.yaml")

    def test_frozen_scope_is_untouched(self):
        scope = _scope(ROOT / "registry/v0.1.yaml")
        self.assertEqual(scope["release"], "v0.1")
        self.assertEqual(scope["required_plugins"], FROZEN_PLUGINS)
        self.assertEqual(len(scope["required_resources"]), 37)

    def test_prospective_scope_extends_the_frozen_plugins(self):
        scope = _scope(ROOT / "registry/v1.1.yaml")
        self.assertEqual(scope["release"], "v1.1")
        plugins = scope["required_plugins"]
        # The frozen four stay first, in their v0.1 order, so the generated
        # marketplaces keep their existing entries' positions; prospective
        # plugins append after them.
        self.assertEqual(plugins[: len(FROZEN_PLUGINS)], FROZEN_PLUGINS)
        self.assertIn("nabu", plugins)
        # Resources are unchanged by this scope: Nabu brings no
        # Context-Fabric resource, and the CAL candidate brings none either.
        frozen = _scope(ROOT / "registry/v0.1.yaml")
        self.assertEqual(
            scope["required_resources"], frozen["required_resources"]
        )


class ProspectiveGenerationTests(unittest.TestCase):
    def test_generation_targets_the_newest_scope(self):
        outputs = {path.relative_to(ROOT) for path in render_outputs()}
        for client_dir, manifest in (
            (".claude-plugin", "plugin.json"),
            (".codex-plugin", "plugin.json"),
            (".claude-plugin", "mcp.json"),
            (".codex-plugin", "mcp.json"),
        ):
            self.assertIn(Path(f"plugins/nabu/{client_dir}/{manifest}"), outputs)

    def test_marketplaces_list_prospective_plugins_after_the_frozen_four(self):
        import json

        with (ROOT / ".claude-plugin/marketplace.json").open("r", encoding="utf-8") as fh:
            claude = json.load(fh)
        with (ROOT / ".agents/plugins/marketplace.json").open("r", encoding="utf-8") as fh:
            codex = json.load(fh)
        scope = _scope(ROOT / "registry/v1.1.yaml")
        expected = scope["required_plugins"]
        self.assertEqual([item["name"] for item in claude["plugins"]], expected)
        self.assertEqual([item["name"] for item in codex["plugins"]], expected)


if __name__ == "__main__":
    unittest.main()
