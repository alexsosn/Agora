from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import agora_install_materializer as installer


PLUGIN = {
    "id": "example-converter",
    "name": "Example converter",
    "description": "Synthetic converter for resolver tests.",
    "repository": "example/converter",
    "ref": "0123456789abcdef0123456789abcdef01234567",
    "version": "1.2.3",
    "manifest": "agora.materializer.json",
    "package": {
        "type": "python-project",
        "path": ".",
        "install_trust": "explicit-code-execution",
    },
    "materializers": ["example-to-tf"],
    "disciplines": ["digital-philology"],
    "licenses": {"software": "MIT", "data": "synthetic"},
    "verification": {"status": "experimental"},
}
REGISTRY = {"schema_version": 1, "plugins": [PLUGIN]}


class RegisteredMaterializerResolverTests(unittest.TestCase):
    def _resolver(self):
        resolver = getattr(installer, "resolve_installed_manifest", None)
        self.assertTrue(
            callable(resolver),
            "RED contract: installer must expose resolve_installed_manifest()",
        )
        return resolver

    def test_unknown_plugin_fails_without_fetch_or_install(self):
        resolver = self._resolver()
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(installer, "load_registry", return_value=REGISTRY),
            mock.patch.object(installer, "fetch_materializer") as fetch_mock,
            mock.patch.object(installer, "install_materializer") as install_mock,
        ):
            with self.assertRaisesRegex(installer.MaterializerInstallError, "unknown.*plugin"):
                resolver("missing-plugin", install_root=Path(tmp))
        fetch_mock.assert_not_called()
        install_mock.assert_not_called()

    def test_registered_but_not_installed_is_actionable_and_has_no_side_effect(self):
        resolver = self._resolver()
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(installer, "load_registry", return_value=REGISTRY),
            mock.patch.object(installer, "fetch_materializer") as fetch_mock,
            mock.patch.object(installer, "install_materializer") as install_mock,
        ):
            with self.assertRaisesRegex(installer.MaterializerInstallError, "not installed") as caught:
                resolver("example-converter", install_root=Path(tmp))
        self.assertIn("install example-converter", str(caught.exception))
        fetch_mock.assert_not_called()
        install_mock.assert_not_called()

    def test_tampered_installation_fails_integrity_without_repair_or_install(self):
        resolver = self._resolver()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = installer.installation_path(PLUGIN, root)
            (target / "runtime").mkdir(parents=True)
            (target / "runtime" / PLUGIN["manifest"]).write_text("{}", encoding="utf-8")
            with (
                mock.patch.object(installer, "load_registry", return_value=REGISTRY),
                mock.patch.object(installer, "_environment_current", return_value=False) as current_mock,
                mock.patch.object(installer, "fetch_materializer") as fetch_mock,
                mock.patch.object(installer, "install_materializer") as install_mock,
            ):
                with self.assertRaisesRegex(installer.MaterializerInstallError, "integrity"):
                    resolver("example-converter", install_root=root)
            current_mock.assert_called_once_with(PLUGIN, target)
            fetch_mock.assert_not_called()
            install_mock.assert_not_called()

    def test_valid_current_installation_resolves_exact_managed_manifest(self):
        resolver = self._resolver()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = installer.installation_path(PLUGIN, root)
            manifest = target / "runtime" / PLUGIN["manifest"]
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{}", encoding="utf-8")
            with (
                mock.patch.object(installer, "load_registry", return_value=REGISTRY),
                mock.patch.object(installer, "_environment_current", return_value=True) as current_mock,
                mock.patch.object(installer, "fetch_materializer") as fetch_mock,
                mock.patch.object(installer, "install_materializer") as install_mock,
            ):
                resolved = resolver("example-converter", install_root=root)
            self.assertEqual(resolved, manifest.resolve())
            current_mock.assert_called_once_with(PLUGIN, target)
            fetch_mock.assert_not_called()
            install_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
