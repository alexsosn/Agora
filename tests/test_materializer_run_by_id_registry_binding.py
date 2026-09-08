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


PLUGIN = {
    "id": "example-converter",
    "name": "Example converter",
    "description": "Synthetic converter for registry binding tests.",
    "repository": "example/converter",
    "ref": "0123456789abcdef0123456789abcdef01234567",
    "version": "1.2.3",
    "manifest": "agora.materializer.json",
    "package": {
        "type": "python-project",
        "path": ".",
        "install_trust": "explicit-code-execution",
    },
    "materializers": ["allowed-to-tf"],
    "disciplines": ["digital-philology"],
    "licenses": {"software": "MIT", "data": "synthetic"},
    "verification": {"status": "experimental"},
}


def _materializer(materializer_id: str) -> dict:
    return {
        "id": materializer_id,
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


class RegisteredMaterializerRegistryBindingTests(unittest.TestCase):
    def test_removed_registry_materializer_cannot_execute_from_still_installed_manifest(self):
        manifest_doc = {
            "schema_version": 1,
            "plugin": {
                "id": PLUGIN["id"],
                "name": PLUGIN["name"],
                "version": PLUGIN["version"],
                "repository": PLUGIN["repository"],
            },
            "materializers": [
                _materializer("allowed-to-tf"),
                _materializer("removed-to-tf"),
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "environment"
            manifest = target / "runtime" / PLUGIN["manifest"]
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps(manifest_doc), encoding="utf-8")
            with (
                mock.patch.object(registered, "_registered_target", return_value=(PLUGIN, target)),
                mock.patch.object(registered, "resolve_installed_manifest", return_value=manifest),
                mock.patch.object(installer, "_lock", return_value=nullcontext()),
                mock.patch.object(host, "materialize") as materialize_mock,
            ):
                with self.assertRaisesRegex(
                    installer.MaterializerInstallError,
                    "registry|materializer|binding",
                ):
                    registered.materialize_registered(
                        plugin_id=PLUGIN["id"],
                        materializer_id="removed-to-tf",
                        output=root / "output",
                        source=root / "source",
                        sandbox="off",
                    )
            materialize_mock.assert_not_called()

    def test_not_installed_run_fails_before_creating_runtime_lock_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "missing-environment"
            with (
                mock.patch.object(registered, "_registered_target", return_value=(PLUGIN, target)),
                mock.patch.object(installer, "_lock", return_value=nullcontext()) as lock_mock,
                mock.patch.object(registered, "resolve_installed_manifest") as resolve_mock,
                mock.patch.object(host, "materialize") as materialize_mock,
            ):
                with self.assertRaisesRegex(installer.MaterializerInstallError, "not installed"):
                    registered.materialize_registered(
                        plugin_id=PLUGIN["id"],
                        materializer_id="allowed-to-tf",
                        output=root / "output",
                        source=root / "source",
                        sandbox="off",
                    )
            lock_mock.assert_not_called()
            resolve_mock.assert_not_called()
            materialize_mock.assert_not_called()
            self.assertFalse(target.parent.joinpath(f".{target.name}.lock").exists())


if __name__ == "__main__":
    unittest.main()
