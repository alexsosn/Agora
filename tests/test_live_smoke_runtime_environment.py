from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/external-mcp-smoke.yml"
INTEL_JOB_MARKER = "  context-fabric-intel-macos:\n"


def _assert_intel_job_contract(testcase: unittest.TestCase, workflow: str) -> None:
    """Assert the Intel-macOS regression contract.

    Review RED intentionally starts with the original whole-workflow checks.
    The mutation regression below demonstrates why those checks are too broad:
    Ubuntu can satisfy assertions that are supposed to belong to the Intel job.
    """
    testcase.assertIn("context-fabric-intel-macos:", workflow)
    testcase.assertIn("runs-on: macos-15-intel", workflow)
    testcase.assertIn("platform.machine()", workflow)
    testcase.assertIn('"x86_64"', workflow)
    testcase.assertIn(
        "uv run --project verification/mcp-smoke --locked \\",
        workflow,
    )
    testcase.assertIn(
        "python scripts/smoke_mcp_plugin.py context-fabric --timeout 180",
        workflow,
    )
    testcase.assertIn("mcp-smoke-context-fabric-intel-macos.json", workflow)
    testcase.assertIn("if: always()", workflow)


class LiveSmokeRuntimeEnvironmentTests(unittest.TestCase):
    def test_live_smoke_runs_from_committed_harness_lock(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("version: \"0.12.10\"", workflow)
        self.assertIn(
            "uv run --project verification/mcp-smoke --locked \\",
            workflow,
        )
        self.assertIn("python scripts/smoke_mcp_plugin.py", workflow)
        self.assertNotIn('uv run --with "mcp>=2,<3"', workflow)
        self.assertNotIn('--with "PyYAML>=6,<7"', workflow)

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

        # Any change that can alter the packaged command or locked environment
        # must retrigger the Intel evidence lane.
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

    def test_intel_contract_rejects_harness_or_artifact_guarantees_satisfied_only_by_ubuntu(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        prefix, intel_job = workflow.split(INTEL_JOB_MARKER, 1)
        weakened_intel_job = intel_job.replace(
            "uv run --project verification/mcp-smoke --locked \\",
            "uv run --project verification/mcp-smoke \\",
            1,
        ).replace("        if: always()\n", "", 1)
        mutated = prefix + INTEL_JOB_MARKER + weakened_intel_job

        # The contract checker must reject this even though the unchanged
        # Ubuntu job still contains both '--locked' and 'if: always()'.
        with self.assertRaises(AssertionError):
            _assert_intel_job_contract(self, mutated)


if __name__ == "__main__":
    unittest.main()
