from __future__ import annotations

import asyncio
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.smoke_mcp_plugin as smoke


class LiveSmokeEnvironmentBindingTests(unittest.TestCase):
    def make_root(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        shutil.copytree(smoke.ROOT / "registry", root / "registry")
        for relative_path in (
            "plugins/perseus/runtime-constraints.txt",
            "verification/mcp-smoke/uv.lock",
        ):
            source = smoke.ROOT / relative_path
            target = root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return root

    def test_trace_records_independently_observed_environment_digests(self):
        trace = smoke.build_trace_metadata(
            "perseus",
            launch=smoke.load_plugin_launch("perseus"),
        )
        inputs = trace["verification_inputs"]
        for field in ("environment", "harness_environment"):
            identity = inputs[field]
            target = smoke.ROOT / identity["path"]
            expected = hashlib.sha256(target.read_bytes()).hexdigest()
            self.assertEqual(identity["sha256"], expected)
            self.assertEqual(identity["actual_sha256"], expected)

    def test_mutated_snapshot_is_rejected_before_smoke_runtime_initialization(self):
        root = self.make_root()
        constraint = root / "plugins/perseus/runtime-constraints.txt"
        constraint.write_bytes(constraint.read_bytes() + b"\n# mutation\n")

        binder = getattr(smoke, "bind_live_verification_inputs", None)
        self.assertTrue(callable(binder), "live smoke must expose a pre-launch environment binder")

        with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
            binder("perseus", root=root)

        # The smoke entry point must invoke the binder before importing/starting
        # the MCP runtime. Foundation deliberately does not install the MCP SDK,
        # so this sentinel proves ordering without spawning a child process.
        with patch.object(
            smoke,
            "bind_live_verification_inputs",
            side_effect=RuntimeError("pre-launch binding sentinel"),
        ):
            with self.assertRaisesRegex(RuntimeError, "pre-launch binding sentinel"):
                asyncio.run(
                    smoke.smoke_plugin(
                        "perseus",
                        launch=smoke.load_plugin_launch("perseus"),
                        root=root,
                    )
                )


if __name__ == "__main__":
    unittest.main()
