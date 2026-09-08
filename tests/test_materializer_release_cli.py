from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MaterializerReleaseCliTests(unittest.TestCase):
    def test_direct_script_help_works_from_repository_root(self):
        result = subprocess.run(
            [sys.executable, "scripts/check_materializer_releases.py", "--help"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Passively discover registered materializer releases", result.stdout)


if __name__ == "__main__":
    unittest.main()
