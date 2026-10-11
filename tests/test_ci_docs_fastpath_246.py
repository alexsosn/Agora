"""#246 RED: bounded docs fast path on real PR changed-file surfaces."""
from __future__ import annotations

import unittest
from pathlib import Path
from scripts.ci_change_scope import classify_changed_paths

ROOT = Path(__file__).resolve().parents[1]
DOC_PR_PATHS = {
    242: ("research/issue-171/RESEARCH_PLAN.md", "tests/test_compatibility_decisions_171.py", "wiki/guides/compatibility.md"),
    243: ("research/issue-169/RESEARCH_PLAN.md", "scripts/generate_plugin_docs.py",
          "scripts/generate_resource_catalog_docs.py", "tests/test_human_scholarly_guidance_169.py",
          "wiki/guides/README.md", "wiki/guides/plugins/context-fabric.md",
          "wiki/guides/plugins/perseus.md", "wiki/guides/plugins/sedra.md",
          "wiki/guides/plugins/sefaria.md", "wiki/guides/resources.md",
          "wiki/guides/scholarly-guidance.md"),
    244: ("CONTRIBUTING.md", "research/issue-172/RESEARCH_PLAN.md",
          "scripts/generate_plugin_docs.py", "tests/test_release_front_door.py",
          "tests/test_symptom_recovery_docs_172.py", "wiki/guides/README.md",
          "wiki/guides/compatibility.md", "wiki/guides/development-setup.md",
          "wiki/guides/installation.md", "wiki/guides/plugins/context-fabric.md",
          "wiki/guides/plugins/perseus.md", "wiki/guides/plugins/sedra.md",
          "wiki/guides/plugins/sefaria.md", "wiki/guides/troubleshooting.md"),
    245: ("research/issue-170/RESEARCH_PLAN.md", "scripts/generate_plugin_docs.py",
          "tests/test_first_success_tutorials_170.py", "wiki/guides/README.md",
          "wiki/guides/first-success/context-fabric.md", "wiki/guides/first-success/perseus.md",
          "wiki/guides/first-success/sedra.md", "wiki/guides/first-success/sefaria.md",
          "wiki/guides/plugins/context-fabric.md", "wiki/guides/plugins/perseus.md",
          "wiki/guides/plugins/sedra.md", "wiki/guides/plugins/sefaria.md"),
    247: ("research/issue-173/RESEARCH_PLAN.md", "scripts/generate_resource_catalog_docs.py",
          "tests/test_researcher_docs_integrity_173.py", "wiki/guides/README.md",
          "wiki/guides/cognitive-walkthroughs.md", "wiki/guides/resources.md"),
}
RUNTIME_PR_PATHS = {
    248: (".github/workflows/foundation.yml", "scripts/ci_change_scope.py", "tests/test_ci_change_scope_246.py"),
    249: ("scripts/agora_materialize.py", "tests/test_materialization_sparse_git.py"),
    253: ("plugins/context-fabric/src/agora_context_fabric/catalog.py", "registry/schema/resources.schema.json"),
    254: ("scripts/agora_materialize.py", "tests/test_git_cumulative_deadline_211.py"),
    255: (".github/workflows/pseudepigrapha-release-layout-probe.yml", "scripts/probe_tf_release_asset.py"),
    256: ("plugins/context-fabric/src/agora_context_fabric/release_archive.py",),
    257: ("plugins/context-fabric/src/agora_context_fabric/release_snapshots.py",),
    259: ("plugins/context-fabric/src/agora_context_fabric/release_download.py",),
    260: ("plugins/context-fabric/src/agora_context_fabric/resolver.py",),
    261: ("registry/resources.yaml", "plugins/context-fabric/src/agora_context_fabric/service.py"),
}


class ProportionalCiHistory246(unittest.TestCase):
    def test_five_actual_documentation_prs_qualify(self):
        for number, paths in DOC_PR_PATHS.items():
            with self.subTest(pr=number):
                self.assertEqual("docs", classify_changed_paths(paths))

    def test_ten_actual_runtime_or_ci_prs_remain_full(self):
        for number, paths in RUNTIME_PR_PATHS.items():
            with self.subTest(pr=number):
                self.assertEqual("full", classify_changed_paths(paths))

    def test_no_unreviewed_python_or_mixed_change_can_skip_full(self):
        for path in (
            "scripts/agora_materialize.py",
            "scripts/generate_context_fabric_catalog.py",
            "scripts/generate_marketplaces.py",
            "scripts/generate_release_status.py",
            "tests/test_mat_install_locks.py",
            "tests/test_unreviewed_docs_999.py",
            "registry/resources.yaml",
            "plugins/context-fabric/src/server.py",
            ".github/workflows/external-mcp-smoke.yml",
            "plugins/context-fabric/.codex-plugin/mcp.json",
            "registry/schema/plugins.schema.json",
            "requirements-dev.txt",
            "tests/test_ci_change_scope_246.py",
        ):
            with self.subTest(path=path):
                self.assertEqual("full", classify_changed_paths(["wiki/guides/README.md", path]))
        for broken in (
            [], ["scripts/generate_plugin_docs.py/../agora_materialize.py"],
            ["scripts/generate_plugin_docs.py\nregistry/resources.yaml"],
            ["./scripts/generate_plugin_docs.py"],
        ):
            self.assertEqual("full", classify_changed_paths(broken))

    def test_foundation_retains_full_main_and_docs_contract_checks(self):
        yaml = (ROOT / ".github/workflows/foundation.yml").read_text()
        self.assertIn("python scripts/ci_change_scope.py", yaml)
        self.assertIn("generate_plugin_docs.py --check", yaml)
        self.assertIn("generate_resource_catalog_docs.py --check", yaml)
        self.assertIn("Repository foundation, registry, and manifests", yaml)
        self.assertIn("context-fabric-cache-lifecycle:", yaml)
        self.assertIn("materializer-install-locks:", yaml)


if __name__ == "__main__":
    unittest.main()
