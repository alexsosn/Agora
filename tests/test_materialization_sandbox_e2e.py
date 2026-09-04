from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
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


def _manifest(module: str, args: list[str], required_paths: list[str]) -> dict:
    return {
        "schema_version": 1,
        "plugin": {
            "id": "sandbox-fixture",
            "name": "Sandbox fixture",
            "version": "1.0.0",
        },
        "materializers": [
            {
                "id": "fixture",
                "description": "Exercise the real OS sandbox.",
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
                    "module": module,
                    "args": args,
                    "network": "deny",
                },
                "output": {
                    "format": "text-fabric",
                    "required_paths": required_paths,
                },
            }
        ],
    }


class RealSandboxMaterializationTests(unittest.TestCase):
    def test_real_sandbox_materialization_reads_source_and_rereads_output(self):
        _require_sandbox()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "plugin"
            source = root / "source"
            output = root / "artifact"
            plugin.mkdir()
            source.mkdir()
            (source / "book.xml").write_text("<book/>", encoding="utf-8")

            (plugin / "sandbox_fixture.py").write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "source = Path(sys.argv[1])\n"
                "output = Path(sys.argv[2])\n"
                "assert (source / 'book.xml').read_text(encoding='utf-8') == '<book/>'\n"
                "otype = output / 'otype.tf'\n"
                "otype.write_text('otype', encoding='utf-8')\n"
                "assert otype.read_text(encoding='utf-8') == 'otype'\n"
                "otype.write_text(otype.read_text(encoding='utf-8') + '-reread', encoding='utf-8')\n"
                "(output / 'oslots.tf').write_text('oslots', encoding='utf-8')\n",
                encoding="utf-8",
            )
            manifest_path = plugin / "agora.materializer.json"
            manifest_path.write_text(
                json.dumps(
                    _manifest(
                        "sandbox_fixture",
                        ["{source}", "{output}"],
                        ["otype.tf", "oslots.tf"],
                    )
                ),
                encoding="utf-8",
            )

            result = materialize(
                manifest_path=manifest_path,
                materializer_id="fixture",
                source=source,
                output=output,
                sandbox="required",
            )

            self.assertEqual(result, output.resolve())
            self.assertEqual((output / "otype.tf").read_text(encoding="utf-8"), "otype-reread")
            provenance = json.loads((output / "agora-materialization.json").read_text(encoding="utf-8"))
            expected_backend = "bubblewrap" if platform.system() == "Linux" else "sandbox-exec"
            self.assertEqual(provenance["sandbox"], expected_backend)

    def test_real_sandbox_denies_network(self):
        _require_sandbox()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "plugin"
            source = root / "source"
            output = root / "artifact"
            plugin.mkdir()
            source.mkdir()
            (source / "book.xml").write_text("<book/>", encoding="utf-8")

            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            listener.settimeout(0.25)

            (plugin / "network_fixture.py").write_text(
                "from pathlib import Path\n"
                "import socket\n"
                "import sys\n"
                "output = Path(sys.argv[1])\n"
                "port = int(sys.argv[2])\n"
                "try:\n"
                "    sock = socket.create_connection(('127.0.0.1', port), timeout=0.25)\n"
                "except OSError:\n"
                "    (output / 'network.txt').write_text('denied', encoding='utf-8')\n"
                "else:\n"
                "    sock.close()\n"
                "    (output / 'network.txt').write_text('connected', encoding='utf-8')\n",
                encoding="utf-8",
            )
            manifest_path = plugin / "agora.materializer.json"
            manifest_path.write_text(
                json.dumps(
                    _manifest(
                        "network_fixture",
                        ["{output}", str(port)],
                        ["network.txt"],
                    )
                ),
                encoding="utf-8",
            )

            try:
                try:
                    result = materialize(
                        manifest_path=manifest_path,
                        materializer_id="fixture",
                        source=source,
                        output=output,
                        sandbox="required",
                    )
                except subprocess.CalledProcessError:
                    # Some sandbox backends terminate the process on a prohibited
                    # network operation instead of returning EPERM to Python.
                    result = None

                if result is not None:
                    self.assertEqual(
                        (output / "network.txt").read_text(encoding="utf-8"),
                        "denied",
                    )

                with self.assertRaises(socket.timeout):
                    listener.accept()
            finally:
                listener.close()


if __name__ == "__main__":
    unittest.main()
