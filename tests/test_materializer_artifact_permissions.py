from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

from scripts.agora_materialize import _create_staging_output


@unittest.skipUnless(os.name == "posix", "POSIX permission bits are the contract under test")
class MaterializerArtifactPermissionTests(unittest.TestCase):
    def test_staging_root_and_publishable_output_are_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            final = parent / "artifact"
            previous_umask = os.umask(0o022)
            staging = None
            try:
                staging = _create_staging_output(final)
            finally:
                os.umask(previous_umask)

            try:
                self.assertEqual(stat.S_IMODE(staging.root.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE(staging.output.stat().st_mode), 0o700)
            finally:
                staging.cleanup()


if __name__ == "__main__":
    unittest.main()
