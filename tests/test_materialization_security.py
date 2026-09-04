from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.agora_materialize import build_sandbox_command, materialize


def _manifest(module: str) -> dict:
    return {
        "schema_version": 1,
        "plugin": {
            "id": "security-fixture",
            "name": "Security fixture",
            "version": "1.0.0",
        },
        "materializers": [
            {
                "id": "fixture",
                "description": "Security regression fixture.",
                "acquisition": [
                    {
                        "type": "user-local",
                        "path_type": "directory",
                        "prompt": "Select fixture source",
                    }
                ],
                "input": {
                    "type": "directory",
                    "required_globs": ["*.xml"],
                    "allow_symlinks": False,
                },
                "execution": {
                    "type": "python-module",
                    "module": module,
                    "args": ["{source}", "{output}"],
                    "network": "deny",
                },
                "output": {
                    "format": "text-fabric",
                    "required_paths": ["otype.tf", "oslots.tf"],
                },
            }
        ],
    }


class MaterializationSecurityTests(unittest.TestCase):
    def test_materializer_cannot_redirect_agora_provenance_write_outside_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "plugin"
            source = root / "source"
            output = root / "artifact"
            plugin.mkdir()
            source.mkdir()

            target = root / "outside.txt"
            target.write_text("do not overwrite", encoding="utf-8")
            (source / "book.xml").write_text("<book/>", encoding="utf-8")
            (source / "target.txt").write_text(str(target), encoding="utf-8")

            (plugin / "malicious_fixture.py").write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "source = Path(sys.argv[1])\n"
                "output = Path(sys.argv[2])\n"
                "target = (source / 'target.txt').read_text(encoding='utf-8')\n"
                "(output / 'otype.tf').write_text('otype', encoding='utf-8')\n"
                "(output / 'oslots.tf').write_text('oslots', encoding='utf-8')\n"
                "(output / 'agora-materialization.json').symlink_to(target)\n",
                encoding="utf-8",
            )
            manifest_path = plugin / "agora.materializer.json"
            manifest_path.write_text(
                json.dumps(_manifest("malicious_fixture")),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "reserved provenance"):
                materialize(
                    manifest_path=manifest_path,
                    materializer_id="fixture",
                    source=source,
                    output=output,
                    sandbox="off",
                )

            self.assertEqual(target.read_text(encoding="utf-8"), "do not overwrite")

    @mock.patch("scripts.agora_materialize.platform.system", return_value="Linux")
    @mock.patch("scripts.agora_materialize.shutil.which", return_value="/usr/bin/bwrap")
    def test_linux_sandbox_exposes_src_layout_without_host_path(self, _which, _system):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("plugin", "source", "output", "work"):
                (root / name).mkdir()
            command, _ = build_sandbox_command(
                plugin_root=root / "plugin",
                source=root / "source",
                output=root / "output",
                work_dir=root / "work",
                module="example.cli",
                args=["{source}", "{output}"],
            )

        py_path_index = command.index("PYTHONPATH") + 1
        self.assertEqual(command[py_path_index], "/plugin/src:/plugin")


if __name__ == "__main__":
    unittest.main()
