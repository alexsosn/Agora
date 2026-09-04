from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml
from jsonschema import Draft202012Validator

from scripts.agora_install_materializer import (
    INSTALLATION_RECEIPT,
    MaterializerInstallError,
    install_materializer,
    load_registry,
    select_plugin,
)

ROOT = Path(__file__).resolve().parents[1]
PSEUDEPIGRAPHA_TF_COMMIT = "a2300b3c5b1a5e859d82691dc28bd53967053a8d"


def _registry() -> dict:
    return {
        "schema_version": 1,
        "plugins": [
            {
                "id": "example-converter",
                "name": "Example converter",
                "description": "Example registered converter.",
                "repository": "example/converter",
                "ref": "0123456789abcdef0123456789abcdef01234567",
                "version": "1.2.3",
                "manifest": "agora.materializer.json",
                "package": {"type": "python-project", "path": "."},
                "materializers": ["example-to-tf"],
                "disciplines": ["digital-philology"],
                "licenses": {"software": "MIT", "data": "upstream-dependent"},
                "verification": {"status": "experimental"},
            }
        ],
    }


def _manifest(*, repository: str = "example/converter") -> dict:
    return {
        "schema_version": 1,
        "plugin": {
            "id": "example-converter",
            "name": "Example converter",
            "version": "1.2.3",
            "repository": repository,
        },
        "materializers": [
            {
                "id": "example-to-tf",
                "description": "Convert example XML to TF.",
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


def _write_fixture_plugin(path: Path, *, repository: str = "example/converter") -> None:
    (path / "src/example_converter").mkdir(parents=True)
    (path / "src/example_converter/__init__.py").write_text("", encoding="utf-8")
    (path / "src/example_converter/cli.py").write_text("def main(): return 0\n", encoding="utf-8")
    (path / "pyproject.toml").write_text(
        "[build-system]\nrequires=['setuptools>=68']\nbuild-backend='setuptools.build_meta'\n"
        "[project]\nname='example-converter'\nversion='1.2.3'\n",
        encoding="utf-8",
    )
    (path / "agora.materializer.json").write_text(
        json.dumps(_manifest(repository=repository)), encoding="utf-8"
    )


class MaterializerRegistryTests(unittest.TestCase):
    def test_canonical_registry_matches_schema(self):
        document = yaml.safe_load((ROOT / "registry/materializers.yaml").read_text(encoding="utf-8"))
        schema = json.loads(
            (ROOT / "registry/schema/materializers.schema.json").read_text(encoding="utf-8")
        )
        errors = sorted(Draft202012Validator(schema).iter_errors(document), key=str)
        self.assertEqual(errors, [])

    def test_pseudepigrapha_tf_is_registered_at_immutable_commit(self):
        plugin = select_plugin(load_registry(), "pseudepigrapha-tf")
        self.assertEqual(plugin["repository"], "alexsosn/Pseudepigrapha-TF")
        self.assertEqual(plugin["ref"], PSEUDEPIGRAPHA_TF_COMMIT)
        self.assertEqual(plugin["version"], "0.1.0")
        self.assertEqual(plugin["manifest"], "agora.materializer.json")
        self.assertEqual(plugin["materializers"], ["ocp-text-fabric"])


class MaterializerInstallerTests(unittest.TestCase):
    def _registry_path(self, root: Path) -> Path:
        path = root / "materializers.yaml"
        path.write_text(yaml.safe_dump(_registry(), sort_keys=False), encoding="utf-8")
        return path

    @mock.patch("scripts.agora_install_materializer._verify_execution_modules")
    @mock.patch("scripts.agora_install_materializer._install_python_project")
    @mock.patch("scripts.agora_install_materializer._checkout_repository")
    def test_install_downloads_validates_installs_and_writes_receipt(
        self, checkout, install_python, verify_modules
    ):
        def populate(_plugin, destination):
            _write_fixture_plugin(destination)
            return _registry()["plugins"][0]["ref"]

        checkout.side_effect = populate
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = install_materializer(
                "example-converter",
                install_root=root / "installed",
                registry_path=self._registry_path(root),
            )
            receipt = json.loads((target / INSTALLATION_RECEIPT).read_text(encoding="utf-8"))

        self.assertEqual(receipt["plugin"]["id"], "example-converter")
        self.assertEqual(receipt["plugin"]["repository"], "example/converter")
        self.assertEqual(receipt["plugin"]["commit"], _registry()["plugins"][0]["ref"])
        self.assertEqual(receipt["manifest"]["path"], "agora.materializer.json")
        self.assertRegex(receipt["manifest"]["sha256"], r"^[0-9a-f]{64}$")
        install_python.assert_called_once()
        verify_modules.assert_called_once()

    @mock.patch("scripts.agora_install_materializer._verify_execution_modules")
    @mock.patch("scripts.agora_install_materializer._install_python_project")
    @mock.patch("scripts.agora_install_materializer._checkout_repository")
    def test_manifest_identity_must_match_registry(self, checkout, install_python, verify_modules):
        def populate(_plugin, destination):
            _write_fixture_plugin(destination, repository="attacker/replacement")
            return _registry()["plugins"][0]["ref"]

        checkout.side_effect = populate
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(MaterializerInstallError, "does not match registry"):
                install_materializer(
                    "example-converter",
                    install_root=root / "installed",
                    registry_path=self._registry_path(root),
                )
        install_python.assert_not_called()
        verify_modules.assert_not_called()

    @mock.patch("scripts.agora_install_materializer._verify_execution_modules")
    @mock.patch("scripts.agora_install_materializer._install_python_project")
    @mock.patch("scripts.agora_install_materializer._checkout_repository")
    def test_current_installation_is_idempotent(self, checkout, install_python, verify_modules):
        def populate(_plugin, destination):
            _write_fixture_plugin(destination)
            return _registry()["plugins"][0]["ref"]

        checkout.side_effect = populate
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = self._registry_path(root)
            first = install_materializer(
                "example-converter",
                install_root=root / "installed",
                registry_path=registry_path,
            )
            checkout.reset_mock()
            install_python.reset_mock()
            verify_modules.reset_mock()
            second = install_materializer(
                "example-converter",
                install_root=root / "installed",
                registry_path=registry_path,
            )

        self.assertEqual(first, second)
        checkout.assert_not_called()
        install_python.assert_not_called()
        verify_modules.assert_not_called()

    @mock.patch("scripts.agora_install_materializer._checkout_repository")
    def test_wrong_downloaded_commit_is_rejected(self, checkout):
        checkout.return_value = "f" * 40
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(MaterializerInstallError, "does not match registered commit"):
                install_materializer(
                    "example-converter",
                    install_root=root / "installed",
                    registry_path=self._registry_path(root),
                )


if __name__ == "__main__":
    unittest.main()
