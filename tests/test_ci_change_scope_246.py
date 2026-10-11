"""#246: classifier must fail closed before any CI jobs may be skipped."""
from __future__ import annotations

import unittest
from pathlib import Path

from scripts.ci_change_scope import classify_changed_paths, classify_raw_git_diff, classify_pr_checkout


class CiChangeScopeContracts(unittest.TestCase):
    def test_real_docs_workstreams_with_python_tests_and_generators_require_full(self):
        docs_prs = (
            ("research/issue-169/RESEARCH_PLAN.md", "scripts/generate_plugin_docs.py",
             "scripts/generate_resource_catalog_docs.py", "tests/test_human_scholarly_guidance_169.py",
             "wiki/guides/scholarly-guidance.md", "wiki/guides/plugins/context-fabric.md",
             "wiki/guides/resources.md", "wiki/guides/README.md"),
            ("CONTRIBUTING.md", "research/issue-172/RESEARCH_PLAN.md",
             "scripts/generate_plugin_docs.py", "tests/test_release_front_door.py",
             "tests/test_symptom_recovery_docs_172.py", "wiki/guides/compatibility.md",
             "wiki/guides/installation.md", "wiki/guides/development-setup.md",
             "wiki/guides/troubleshooting.md", "wiki/guides/plugins/sefaria.md"),
            ("research/issue-170/RESEARCH_PLAN.md", "scripts/generate_plugin_docs.py",
             "tests/test_first_success_tutorials_170.py", "wiki/guides/README.md",
             "wiki/guides/first-success/context-fabric.md",
             "wiki/guides/first-success/perseus.md",
             "wiki/guides/first-success/sefaria.md",
             "wiki/guides/first-success/sedra.md",
             "wiki/guides/plugins/context-fabric.md"),
            ("research/issue-173/RESEARCH_PLAN.md", "scripts/generate_resource_catalog_docs.py",
             "tests/test_researcher_docs_integrity_173.py", "wiki/guides/README.md",
             "wiki/guides/resources.md", "wiki/guides/cognitive-walkthroughs.md"),
        )
        for paths in docs_prs:
            with self.subTest(paths=paths):
                self.assertEqual("full", classify_changed_paths(paths))
        self.assertEqual(
            "docs",
            classify_changed_paths(
                ["README.md", "wiki/guides/README.md",
                 "wiki/guides/first-success/sedra.md",
                 "research/issue-246/RESEARCH_PLAN.md"]
            ),
        )

    def test_any_runtime_or_metadata_change_overrides_doc_fast_path(self):
        critical = (
            "scripts/agora_materialize.py",
            "scripts/generate_marketplaces.py",
            "registry/resources.yaml",
            "registry/plugins.yaml",
            "registry/schema/plugins.schema.json",
            "plugins/context-fabric/src/mcp_server.py",
            "plugins/sedra/uv.lock",
            ".github/workflows/foundation.yml",
            ".github/workflows/external-mcp-smoke.yml",
            ".agents/plugins/marketplace.json",
            "requirements-dev.txt",
            "tests/test_materializer_installation.py",
            "tests/test_context_fabric_cache_lifecycle.py",
            "plugins/context-fabric/skills/bhsa-research/SKILL.md",
            "registry/README.md",
        )
        for path in critical:
            with self.subTest(path=path):
                self.assertEqual("full", classify_changed_paths(["wiki/guides/README.md", path]))
                self.assertEqual("full", classify_changed_paths([path]))

    def test_unknown_or_unsafe_path_forces_full_suite(self):
        bad = (None, (), [], [""], ["./wiki/guides/README.md"],
               ["wiki//guides/README.md"], ["wiki/guides/../README.md"],
               ["../../registry/plugins.yaml"], ["/tmp/wiki/guides/README.md"],
               ["wiki\\guides\\README.md"], ["wiki/guides/x.md\n.github/workflows/a.yml"],
               ["Wiki/guides/README.md"], ["docs/random.md"],
               ["tests/test_unreviewed_docs_999.py"], ["research/issues/plan.md"])
        for paths in bad:
            with self.subTest(paths=paths):
                self.assertEqual("full", classify_changed_paths(paths))

    def test_adversarial_python_changes_never_qualify_for_docs_only(self):
        # Documentation generator/test files execute arbitrary Python: never let
        # a PR containing those files skip behavioral checks in a future gate.
        for path in (
            "scripts/generate_plugin_docs.py",
            "scripts/generate_resource_catalog_docs.py",
            "tests/test_compatibility_decisions_171.py",
            "tests/test_human_scholarly_guidance_169.py",
            "tests/test_symptom_recovery_docs_172.py",
            "tests/test_first_success_tutorials_170.py",
            "tests/test_researcher_docs_integrity_173.py",
            "tests/test_plugin_detail_docs.py",
            "tests/test_resource_catalog_docs.py",
            "tests/test_user_docs_landing.py",
            "tests/test_user_docs_mental_model.py",
            "tests/test_release_front_door.py",
        ):
            with self.subTest(path=path):
                self.assertEqual("full", classify_changed_paths([path]))
                self.assertEqual(
                    "full", classify_changed_paths(["README.md", path])
                )

    def test_report_only_in_foundation_cannot_silently_skip_required_matrix_jobs(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/foundation.yml").read_text(encoding="utf-8")
        self.assertIn("fetch-depth: 2", workflow)
        self.assertIn("python scripts/ci_change_scope.py --git-report", workflow)
        self.assertLess(
            workflow.index("uses: actions/setup-python@v5"),
            workflow.index("python scripts/ci_change_scope.py --git-report"),
            "Scope reporter must run using the repository's pinned Python.",
        )
        self.assertIn("continue-on-error: true", workflow)
        self.assertIn("python -m unittest discover -s tests -v", workflow)
        self.assertIn("context-fabric-cache-lifecycle:", workflow)
        self.assertIn("materializer-install-locks:", workflow)
        self.assertNotIn("needs: changed-files", workflow)

    def test_docs_only_sources_are_explicit_and_nonexecutable(self):
        self.assertEqual("docs", classify_changed_paths(["README.md"]))
        self.assertEqual("docs", classify_changed_paths(["wiki/guides/README.md"]))
        self.assertEqual("full", classify_changed_paths(["tests/test_plugin_detail_docs.py"]))
        self.assertEqual("full", classify_changed_paths(["scripts/check_runtime_environment_freshness.py"]))
        self.assertEqual("full", classify_changed_paths(["tests/test_doc_runtime_escape.py"]))


    def test_git_raw_diff_accepts_only_ordinary_regular_file_changes(self):
        hash1 = b"1" * 40
        hash2 = b"2" * 40
        def record(old_mode, new_mode, status, name):
            return (b":" + old_mode + b" " + new_mode + b" " + hash1
                    + b" " + hash2 + b" " + status + b"\x00"
                    + name + b"\x00")
        m = record(b"100644", b"100644", b"M", b"wiki/guides/README.md")
        a = record(b"000000", b"100644", b"A", b"wiki/guides/example.md")
        d = record(b"100644", b"000000", b"D", b"wiki/guides/obsolete.md")
        self.assertEqual("docs", classify_raw_git_diff(m + a + d))
        self.assertEqual("full", classify_raw_git_diff(m + record(
            b"100644", b"100644", b"M", b"plugins/sedra/src/server.py"
        )))
        for unsafe in (
            record(b"100644", b"100755", b"M", b"wiki/guides/README.md"),
            record(b"100644", b"120000", b"T", b"wiki/guides/README.md"),
            record(b"000000", b"120000", b"A", b"wiki/guides/link.md"),
            record(b"120000", b"000000", b"D", b"wiki/guides/link.md"),
            record(b"100644", b"100644", b"R100", b"wiki/guides/README.md"),
            record(b"100644", b"100644", b"M", b"wiki/guides/README.md\n.github/evil.yml"),
            b"",
            b"nonsense\x00wiki/guides/README.md\x00",
            m[:-1],
        ):
            with self.subTest(unsafe=unsafe):
                self.assertEqual("full", classify_raw_git_diff(unsafe))

    def test_untrusted_or_nonmerge_checkout_cannot_claim_docs_scope(self):
        from unittest.mock import Mock
        doc_raw = (b":100644 100644 " + b"a" * 40
                   + b" " + b"b" * 40 + b" M\x00README.md\x00")
        def cmd_result(payload, code=0):
            return Mock(stdout=payload, returncode=code)
        git = Mock(side_effect=[
            cmd_result(b"1" * 40 + b" " + b"2" * 40 + b" " + b"3" * 40 + b"\n"),
            cmd_result(doc_raw),
        ])
        self.assertEqual("docs", classify_pr_checkout(git_runner=git))
        self.assertEqual(2, git.call_count)
        self.assertIn("--no-renames", git.call_args.args[0])
        self.assertIn("-z", git.call_args.args[0])
        for bad_head in (b"one-parent\n", b"first second\n",
                         b"one two three four\n"):
            with self.subTest(head=bad_head):
                self.assertEqual("full", classify_pr_checkout(
                    git_runner=Mock(return_value=cmd_result(bad_head))
                ))
        self.assertEqual("full", classify_pr_checkout(git_runner=Mock(
            side_effect=OSError("git not available")
        )))
        self.assertEqual("full", classify_pr_checkout(git_runner=Mock(
            return_value=cmd_result(b"", 128)
        )))


if __name__ == "__main__":
    unittest.main()
