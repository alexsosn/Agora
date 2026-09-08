from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest import mock

from scripts import agora_install_materializer as installer
from scripts import agora_materialize as host
from scripts import agora_materialize_registered as registered


class RegisteredMaterializerEdgeCaseTests(unittest.TestCase):
    def test_unknown_materializer_id_fails_before_source_acquisition(self):
        manifest_doc = {
            "schema_version": 1,
            "plugin": {
                "id": "example-converter",
                "name": "Example converter",
                "version": "1.2.3",
                "repository": "example/converter",
            },
            "materializers": [
                {
                    "id": "example-to-tf",
                    "description": "Synthetic converter.",
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
                        "module": "example_converter.cli",
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
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "environment"
            manifest = target / "runtime" / "agora.materializer.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps(manifest_doc), encoding="utf-8")
            with (
                mock.patch.object(
                    registered,
                    "_registered_target",
                    return_value=({"id": "example-converter"}, target),
                ),
                mock.patch.object(
                    registered,
                    "resolve_installed_manifest",
                    return_value=manifest,
                ),
                mock.patch.object(installer, "_lock", return_value=nullcontext()),
                mock.patch.object(host, "acquire_source") as acquire_mock,
            ):
                with self.assertRaisesRegex(KeyError, "unknown materializer"):
                    registered.materialize_registered(
                        plugin_id="example-converter",
                        materializer_id="missing-materializer",
                        output=root / "output",
                        source=root / "source",
                        sandbox="off",
                    )
            acquire_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
