from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/external-mcp-smoke.yml"


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

        # #20 was an Intel-macOS cold-start failure. macos-latest is ARM64,
        # so the regression lane must name an Intel runner explicitly and
        # fail closed if the actual runner architecture ever changes.
        self.assertIn("context-fabric-intel-macos:", workflow)
        self.assertIn("runs-on: macos-15-intel", workflow)
        self.assertIn("platform.machine()", workflow)
        self.assertIn('"x86_64"', workflow)

        # Reuse the evidence-producing packaged-launch harness rather than
        # inventing a second synthetic MCP startup path for macOS.
        self.assertIn(
            "uv run --project verification/mcp-smoke --locked \\",
            workflow,
        )
        self.assertIn(
            "python scripts/smoke_mcp_plugin.py context-fabric --timeout 180",
            workflow,
        )
        self.assertIn("mcp-smoke-context-fabric-intel-macos.json", workflow)
        self.assertIn("if: always()", workflow)

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


if __name__ == "__main__":
    unittest.main()
