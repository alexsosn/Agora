from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.agora_materialize import materialize


class StagingOutputSecurityTests(unittest.TestCase):
    def test_materializer_cannot_replace_designated_output_with_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "plugin"
            source = root / "source"
            outside = root / "outside"
            final = root / "artifact"
            plugin.mkdir()
            source.mkdir()
            outside.mkdir()
            (source / "book.xml").write_text("<book/>", encoding="utf-8")
            (outside / "otype.tf").write_text("outside", encoding="utf-8")
            (outside / "oslots.tf").write_text("outside", encoding="utf-8")

            (plugin / "replace_output_fixture.py").write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "output = Path(sys.argv[1])\n"
                "outside = Path(sys.argv[2])\n"
                "output.rmdir()\n"
                "output.symlink_to(outside, target_is_directory=True)\n",
                encoding="utf-8",
            )
            manifest = {
                "schema_version": 1,
                "plugin": {
                    "id": "replace-output-fixture",
                    "name": "Replace output fixture",
                    "version": "1.0.0",
                },
                "materializers": [
                    {
                        "id": "fixture",
                        "description": "Attempt to replace Agora's designated staging output root.",
                        "acquisition": [
                            {
                                "type": "user-local",
                                "path_type": "directory",
                                "prompt": "Select source",
                            }
                        ],
                        "input": {
                            "type": "directory",
                            "required_globs": ["*.xml"],
                            "allow_symlinks": False,
                        },
                        "execution": {
                            "type": "python-module",
                            "module": "replace_output_fixture",
                            "args": ["{output}", str(outside)],
                            "network": "deny",
                        },
                        "output": {
                            "format": "text-fabric",
                            "required_paths": ["otype.tf", "oslots.tf"],
                        },
                    }
                ],
            }
            manifest_path = plugin / "agora.materializer.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "designated output directory"):
                materialize(
                    manifest_path=manifest_path,
                    materializer_id="fixture",
                    source=source,
                    output=final,
                    sandbox="off",
                )

            self.assertFalse(final.exists())
            self.assertFalse((outside / "agora-materialization.json").exists())
            self.assertEqual(list(root.glob(".artifact.agora-stage-*")), [])


if __name__ == "__main__":
    unittest.main()
