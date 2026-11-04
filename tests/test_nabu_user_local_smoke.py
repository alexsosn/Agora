"""The nabu user-local startup smoke's two paths.

The error path runs everywhere (it launches nothing); the live path runs only
on an operator's machine that sets NABU_HOME, because a user-local
environment exists nowhere else — CI stays offline and skips it visibly.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "scripts/smoke_nabu_user_local.py"


class NabuSmokeErrorPathTests(unittest.TestCase):
    def test_refuses_fast_without_nabu_home(self):
        environment = {
            key: value for key, value in os.environ.items() if key != "NABU_HOME"
        }
        completed = subprocess.run(
            [sys.executable, str(SMOKE)],
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("NABU_HOME is not set", completed.stderr)
        self.assertIn("user-local", completed.stderr)


@unittest.skipUnless(
    os.environ.get("NABU_HOME"),
    "user-local live smoke: set NABU_HOME to a built Nabu checkout to run it",
)
class NabuSmokeLivePathTests(unittest.TestCase):
    def test_bounded_startup_smoke_passes(self):
        completed = subprocess.run(
            [sys.executable, str(SMOKE)],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("startup smoke passed", completed.stdout)
        self.assertIn("nabu_status: ok", completed.stdout)


if __name__ == "__main__":
    unittest.main()
