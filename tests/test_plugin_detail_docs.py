from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PSEUDEPIGRAPHA_HEADING = "## Published Online Critical Pseudepigrapha (Pseudepigrapha-TF)"
PLUGIN_REGISTRY = ROOT / "registry" / "plugins.yaml"
PLUGIN_DIR = ROOT / "wiki" / "guides" / "plugins"
GENERATOR = ROOT / "scripts" / "generate_plugin_docs.py"
README = ROOT / "README.md"
USER_GUIDE = ROOT / "wiki" / "guides" / "README.md"

REQUIRED_HEADINGS = (
    "## Use this plugin for",
    "## Access and resources",
    "## What connects or runs",
    "## Local and remote behavior",
    "## Prerequisites",
    "## Install",
    "## First success",
    "## Typical research tasks",
    "## Important limitations",
    "## Disk, memory, and network",
    "## Provenance and licensing",
    "## Troubleshooting",
    "## Upstream",
)


def _pseudepigrapha_guide() -> tuple[dict, str]:
    """Scope the corpus-specific assertion to its own tests, not every plugin check."""
    resources = yaml.safe_load(
        (ROOT / "registry/resources.yaml").read_text(encoding="utf-8")
    )["resources"]
    resource = next(row for row in resources if row["id"] == "pseudepigrapha")
    guide = (PLUGIN_DIR / "context-fabric.md").read_text(encoding="utf-8")
    section = guide.split(PSEUDEPIGRAPHA_HEADING, 1)[1].split("\n## ", 1)[0]
    return resource, section


def _registry() -> list[dict]:
    with PLUGIN_REGISTRY.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["plugins"]


class PluginDetailDocumentationTests(unittest.TestCase):
    def test_generator_and_all_five_pages_exist_and_are_fresh(self):
        plugins = _registry()
        self.assertEqual(
            ["context-fabric", "perseus", "sefaria", "sedra", "cal"],
            [plugin["id"] for plugin in plugins],
        )
        self.assertTrue(GENERATOR.is_file(), "Missing plugin-page generator")
        self.assertTrue(PLUGIN_DIR.is_dir(), "Missing generated plugin-page directory")
        self.assertEqual(
            {f"{plugin['id']}.md" for plugin in plugins},
            {path.name for path in PLUGIN_DIR.glob("*.md")},
        )
        proc = subprocess.run(
            [sys.executable, str(GENERATOR), "--check"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, proc.returncode, proc.stderr or proc.stdout)

    def test_pages_share_one_anatomy_and_render_canonical_plugin_facts(self):
        for plugin in _registry():
            page = (PLUGIN_DIR / f"{plugin['id']}.md").read_text(encoding="utf-8")
            self.assertIn(f"# {plugin['name']}", page)
            self.assertIn(plugin["description"], page)
            for heading in REQUIRED_HEADINGS:
                self.assertEqual(1, page.count(heading), f"{plugin['id']}: {heading}")

            self.assertIn(f"Runtime mode: `{plugin['runtime']['mode']}`", page)
            self.assertIn(f"Data mode: `{plugin['data_mode']}`", page)
            for capability in plugin["capabilities"]:
                self.assertIn(f"`{capability}`", page)
            for key, value in plugin.get("licenses", {}).items():
                self.assertIn(f"`{key}`: `{value}`", page)

            upstream = plugin.get("upstream") or {}
            for key in ("repository", "homepage", "endpoint"):
                if upstream.get(key):
                    self.assertIn(str(upstream[key]), page)

            for issue in (plugin.get("verification") or {}).get("known_issues") or []:
                self.assertIn(f"`{issue['id']}`", page)
                self.assertIn(issue["summary"], page)

    def test_context_fabric_page_routes_resource_and_expensive_load_decisions(self):
        page = (PLUGIN_DIR / "context-fabric.md").read_text(encoding="utf-8")
        self.assertIn("../resources.md", page)
        self.assertIn("../context-fabric-cache.md", page)
        self.assertIn("describe", page)
        self.assertIn("prepare", page)
        self.assertIn("load", page)
        self.assertIn("network access", page)
        self.assertIn("offline", page)

    def test_perseus_page_preserves_current_navigation_boundaries(self):
        plugin = next(item for item in _registry() if item["id"] == "perseus")
        self.assertNotIn("cts-navigation", plugin["capabilities"])
        page = (PLUGIN_DIR / "perseus.md").read_text(encoding="utf-8")
        self.assertIn("Scaife", page)
        self.assertIn("Provider-wide CTS navigation", page)
        self.assertIn("passage retrieval", page.lower())
        self.assertIn("exact discovered URN and service path", page)
        self.assertNotIn("search or morphology", page)

    def test_sefaria_page_exposes_hosted_remote_and_duplicate_search_advisory(self):
        page = (PLUGIN_DIR / "sefaria.md").read_text(encoding="utf-8")
        self.assertIn("Runtime mode: `hosted`", page)
        self.assertIn("Data mode: `remote`", page)
        self.assertIn("duplicate", page.lower())
        self.assertIn("exact occurrence", page.lower())

    def test_sedra_page_distinguishes_word_form_and_lexeme_with_network_boundary(self):
        page = (PLUGIN_DIR / "sedra.md").read_text(encoding="utf-8")
        self.assertIn("Runtime mode: `local`", page)
        self.assertIn("Data mode: `remote`", page)
        self.assertIn("word-form", page)
        self.assertIn("lexeme", page)
        self.assertIn("network", page.lower())

    def test_pages_are_reachable_from_front_door_and_researcher_landing(self):
        readme = README.read_text(encoding="utf-8")
        guide = USER_GUIDE.read_text(encoding="utf-8")
        for plugin in _registry():
            root_link = f"wiki/guides/plugins/{plugin['id']}.md"
            landing_link = f"plugins/{plugin['id']}.md"
            self.assertIn(root_link, readme)
            self.assertIn(landing_link, guide)


    def test_registered_archive_version_and_source_links_are_current(self):
        resource, section = _pseudepigrapha_guide()
        archive = resource["acquisition"]["archive"]
        release = archive["release_tag"]
        repository = resource["upstream"]["repository"]
        self.assertEqual(archive["version"], "1.1")
        self.assertEqual(resource["verification"]["status"], "community")
        self.assertIn(f"**{archive['version']}**", section)
        self.assertIn(f"[Pseudepigrapha-TF {release}]", section)
        self.assertIn(
            f"https://github.com/{repository}/releases/tag/{release}",
            section,
        )
        self.assertIn(f"`{archive['asset_name']}`", section)
        self.assertIn(f"{repository}/blob/{release}/DATA_LICENSE.md", section)
        self.assertIn(
            f"{repository}/blob/{release}/docs/features/0_home.md",
            section,
        )
        for outdated in ("v1.0.0", "tf-1.0.zip", "**1.0**"):
            self.assertNotIn(outdated, section)

    def test_verification_and_local_corpus_boundary_are_not_overstated(self):
        _, section = _pseudepigrapha_guide()
        self.assertIn("**community**", section)
        self.assertIn("Agora", section)
        self.assertIn("end-to-end", section)
        self.assertIn("38258712121", section)
        self.assertIn("actual-client", section)
        self.assertIn("offline", section)
        self.assertIn("`pseudepigrapha-tf` materializer", section)
        self.assertIn("not historical manuscript witnesses", section)

if __name__ == "__main__":
    unittest.main()
