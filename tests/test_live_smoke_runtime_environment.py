from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/external-mcp-smoke.yml"
GITATTRIBUTES = ROOT / ".gitattributes"


def _assert_intel_job_contract(testcase: unittest.TestCase, workflow: str) -> None:
    """Assert the historical Context-Fabric Intel-macOS guarantee in the matrix."""
    document = yaml.safe_load(workflow)
    testcase.assertIsInstance(document, dict)
    jobs = document.get("jobs")
    testcase.assertIsInstance(jobs, dict)
    testcase.assertIn("local-runtime-platform", jobs)

    job = jobs["local-runtime-platform"]
    testcase.assertEqual(job.get("runs-on"), "${{ matrix.runner }}")
    testcase.assertEqual(job.get("timeout-minutes"), 10)
    include = ((job.get("strategy") or {}).get("matrix") or {}).get("include")
    testcase.assertIsInstance(include, list)
    testcase.assertIn(
        {
            "plugin": "context-fabric",
            "runner": "macos-15-intel",
            "platform_os": "macos",
            "platform_arch": "x86_64",
        },
        include,
    )

    steps = job.get("steps")
    testcase.assertIsInstance(steps, list)
    run_text = "\n".join(
        step.get("run", "")
        for step in steps
        if isinstance(step, dict) and isinstance(step.get("run", ""), str)
    )
    testcase.assertIn("platform.machine()", run_text)
    testcase.assertIn("platform.system()", run_text)
    testcase.assertIn("uv run --project verification/mcp-smoke --locked \\", run_text)
    testcase.assertIn("python scripts/smoke_mcp_plugin.py", run_text)
    testcase.assertIn("--startup-only", run_text)
    testcase.assertIn("--client codex", run_text)

    upload_steps = [
        step
        for step in steps
        if isinstance(step, dict)
        and step.get("uses") == "actions/upload-artifact@v4"
    ]
    testcase.assertEqual(len(upload_steps), 1)
    upload = upload_steps[0]
    testcase.assertEqual(upload.get("if"), "always()")
    testcase.assertIn("${{ matrix.plugin }}", upload.get("with", {}).get("name", ""))
    testcase.assertIn("${{ matrix.platform_os }}", upload.get("with", {}).get("name", ""))
    testcase.assertIn("${{ matrix.platform_arch }}", upload.get("with", {}).get("name", ""))
    testcase.assertEqual(upload.get("with", {}).get("if-no-files-found"), "warn")


class LiveSmokeRuntimeEnvironmentTests(unittest.TestCase):
    def test_live_smoke_runs_from_committed_harness_lock(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("version: \"0.12.10\"", workflow)
        self.assertIn("uv run --project verification/mcp-smoke --locked \\", workflow)
        self.assertIn("python scripts/smoke_mcp_plugin.py", workflow)
        self.assertNotIn('uv run --with "mcp>=2,<3"', workflow)
        self.assertNotIn('--with "PyYAML>=6,<7"', workflow)

    def test_digest_bound_environment_text_has_platform_stable_line_endings(self):
        """Windows checkout must not rewrite bytes used as canonical SHA-256 evidence."""
        self.assertTrue(GITATTRIBUTES.is_file(), "digest-bound text needs repository EOL policy")
        attributes = GITATTRIBUTES.read_text(encoding="utf-8").splitlines()
        self.assertIn("*.lock text eol=lf", attributes)
        self.assertIn("*constraints.txt text eol=lf", attributes)

    def test_all_dependency_environment_changes_retrigger_live_verification(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        required_paths = (
            "plugins/context-fabric/pyproject.toml",
            "plugins/context-fabric/uv.lock",
            "plugins/perseus/runtime-requirements.in",
            "plugins/perseus/runtime-constraints.txt",
            "plugins/sefaria/runtime-requirements.in",
            "plugins/sefaria/runtime-constraints.txt",
            "plugins/sedra/pyproject.toml",
            "plugins/sedra/uv.lock",
            "verification/mcp-smoke/pyproject.toml",
            "verification/mcp-smoke/uv.lock",
        )
        for path in required_paths:
            with self.subTest(path=path):
                self.assertIn(f'- "{path}"', workflow)

    def test_context_fabric_has_intel_macos_packaged_launch_regression_lane(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        _assert_intel_job_contract(self, workflow)
        for path in (
            "plugins/context-fabric/.codex-plugin/mcp.json",
            "plugins/context-fabric/pyproject.toml",
            "plugins/context-fabric/uv.lock",
            "verification/mcp-smoke/pyproject.toml",
            "verification/mcp-smoke/uv.lock",
            "scripts/smoke_mcp_plugin.py",
            ".github/workflows/external-mcp-smoke.yml",
        ):
            with self.subTest(path=path):
                self.assertIn(f'- "{path}"', workflow)

    def test_intel_contract_rejects_guarantees_satisfied_only_by_ubuntu(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        mutations = {
            "Intel cell removed": workflow.replace(
                "          - plugin: context-fabric\n"
                "            runner: macos-15-intel\n"
                "            platform_os: macos\n"
                "            platform_arch: x86_64\n",
                "",
                1,
            ),
            "unlocked platform harness": workflow.replace(
                "uv run --project verification/mcp-smoke --locked \\",
                "uv run --project verification/mcp-smoke \\",
                1,
            ),
            "platform artifact not uploaded on failure": workflow.replace(
                "      - name: Upload platform startup report\n        if: always()\n",
                "      - name: Upload platform startup report\n",
                1,
            ),
        }
        for label, mutated in mutations.items():
            with self.subTest(label=label):
                with self.assertRaises(AssertionError):
                    _assert_intel_job_contract(self, mutated)


if __name__ == "__main__":
    unittest.main()
