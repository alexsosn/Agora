from __future__ import annotations

import json
import os
import platform
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.agora_materialize import materialize


def _sandbox_available() -> bool:
    system = platform.system()
    if system == "Linux":
        return shutil.which("bwrap") is not None
    if system == "Darwin":
        return shutil.which("sandbox-exec") is not None
    return False


def _require_sandbox() -> None:
    if _sandbox_available():
        return
    if os.environ.get("AGORA_REQUIRE_SANDBOX_E2E") == "1":
        raise AssertionError(f"required sandbox backend unavailable on {platform.system()}")
    raise unittest.SkipTest("real sandbox backend not installed on this runner")


class AtomicSiblingSandboxMaterializationTests(unittest.TestCase):
    def test_real_sandbox_supports_sibling_stage_and_atomic_replace(self):
        _require_sandbox()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "plugin"
            source = root / "source"
            output = root / "artifact"
            plugin.mkdir()
            source.mkdir()
            (source / "book.xml").write_text("<book/>", encoding="utf-8")

            (plugin / "atomic_fixture.py").write_text(
                "from pathlib import Path\n"
                "import os\n"
                "import sys\n"
                "output = Path(sys.argv[1])\n"
                "stage = output.parent / '.fixture-stage'\n"
                "stage.mkdir()\n"
                "(stage / 'otype.tf').write_text('otype', encoding='utf-8')\n"
                "(stage / 'oslots.tf').write_text('oslots', encoding='utf-8')\n"
                "os.replace(stage / 'otype.tf', output / 'otype.tf')\n"
                "os.replace(stage / 'oslots.tf', output / 'oslots.tf')\n"
                "stage.rmdir()\n",
                encoding="utf-8",
            )
            manifest = {
                "schema_version": 1,
                "plugin": {
                    "id": "atomic-fixture",
                    "name": "Atomic fixture",
                    "version": "1.0.0",
                },
                "materializers": [
                    {
                        "id": "fixture",
                        "description": "Exercise sibling staging under the real sandbox.",
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
                            "module": "atomic_fixture",
                            "args": ["{output}"],
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

            result = materialize(
                manifest_path=manifest_path,
                materializer_id="fixture",
                source=source,
                output=output,
                sandbox="required",
            )

            self.assertEqual(result, output.resolve())
            self.assertEqual((output / "otype.tf").read_text(encoding="utf-8"), "otype")
            self.assertEqual((output / "oslots.tf").read_text(encoding="utf-8"), "oslots")
            self.assertEqual(list(root.glob(".artifact.agora-stage-*")), [])


if __name__ == "__main__":
    unittest.main()
