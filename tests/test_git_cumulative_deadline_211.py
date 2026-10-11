"""#211 RED: cumulative sparse/full Git deadline and transactional cleanup."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import agora_materialize as m


class GitCumulativeDeadline211Tests(unittest.TestCase):
    def test_expired_absolute_deadline_cannot_start_any_git_command(self):
        with (mock.patch.dict(os.environ, {"AGORA_GIT_PHASE_TIMINGS": "0"}),
              mock.patch.object(m.time, "monotonic", return_value=11.0),
              mock.patch.object(m.subprocess, "run") as execute,
              mock.patch.object(m.subprocess, "check_output") as capture):
            with self.assertRaisesRegex(m.AcquisitionError, "cumulative"):
                m._run_git(["git", "fetch"], env={}, deadline=10.0)
            execute.assert_not_called()
            capture.assert_not_called()

    def test_all_subprocess_paths_get_minimum_of_per_command_and_remaining(self):
        with (mock.patch.dict(os.environ, {"AGORA_GIT_PHASE_TIMINGS": "0"}),
              mock.patch.object(m.time, "monotonic", return_value=45.0),
              mock.patch.object(m.subprocess, "run") as execute,
              mock.patch.object(m.subprocess, "check_output", return_value="abc\n") as capture):
            execute.return_value.stderr = ""
            self.assertIsNone(m._run_git(["git", "fetch"], env={}, deadline=49.0))
            self.assertEqual(4.0, execute.call_args.kwargs["timeout"])
            self.assertIsNone(m._run_git(
                ["git", "fetch", "--filter=blob:none"],
                env={}, require_filter_support=True, deadline=49.0,
            ))
            self.assertEqual(4.0, execute.call_args.kwargs["timeout"])
            self.assertEqual(
                "abc",
                m._run_git(["git", "rev-parse", "HEAD"], env={}, capture=True, deadline=49.0),
            )
            self.assertEqual(4.0, capture.call_args.kwargs["timeout"])
            m._run_git(["git", "status"], env={}, deadline=1000.0)
            self.assertEqual(m.GIT_TIMEOUT_SECONDS, execute.call_args.kwargs["timeout"])

    def test_deadline_limited_subprocess_timeout_is_not_reported_as_local_120s(self):
        with (mock.patch.dict(os.environ, {"AGORA_GIT_PHASE_TIMINGS": "0"}),
              mock.patch.object(m.time, "monotonic", return_value=10.0),
              mock.patch.object(m.subprocess, "run",
                                side_effect=subprocess.TimeoutExpired(["git", "checkout"], 5))):
            with self.assertRaisesRegex(m.AcquisitionError, "cumulative"):
                m._run_git(["git", "checkout"], env={}, deadline=15.0)

    def test_shared_deadline_reaches_every_phase_and_failure_cleans_source_root(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir) / "temporary-acquired-source"
            root.mkdir()
            recorded = []

            def fail_second(command, **kwargs):
                recorded.append((command, kwargs))
                if len(recorded) == 2:
                    raise m.AcquisitionError("synthetic network failure")

            strategy = {
                "url": "https://example.invalid/pinned.git",
                "ref": "a" * 40, "subpath": ".",
                "sparse_patterns": ["/*/*_TT/**"],
            }
            with (mock.patch.object(m.shutil, "which", return_value="git"),
                  mock.patch.object(m.tempfile, "mkdtemp", return_value=str(root)),
                  mock.patch.object(m.time, "monotonic", return_value=123.0),
                  mock.patch.object(m, "_run_git", side_effect=fail_second)):
                with self.assertRaisesRegex(m.AcquisitionError, "synthetic"):
                    m.acquire_git_source(strategy, {"input": {"allow_symlinks": False, "required_globs": []}})

            self.assertEqual(2, len(recorded))
            self.assertTrue(all(
                args.get("deadline") == 123.0 + m.GIT_MAX_TOTAL_SECONDS
                for _, args in recorded
            ))
            self.assertFalse(root.exists(), "expired/error acquisition must remove all scratch")


if __name__ == "__main__":
    unittest.main()
