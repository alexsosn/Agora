from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import agora_install_materializer as installer
from scripts import agora_materialize as host

try:
    from scripts import agora_materialize_registered as registered
except ImportError:  # RED: module is intentionally absent before implementation.
    registered = None


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
        self.assertIsNotNone(
            registered,
            "RED contract: scripts.agora_materialize_registered must exist",
        )
        resolver = getattr(registered, "resolve_installed_manifest", None)
        self.assertTrue(
            callable(resolver),
            "RED contract: registered runner must expose resolve_installed_manifest()",
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


class RegisteredMaterializerExecutionRed2Tests(unittest.TestCase):
    def _runner(self):
        self.assertIsNotNone(registered)
        runner = getattr(registered, "materialize_registered", None)
        self.assertTrue(
            callable(runner),
            "RED 2: registered runner must expose materialize_registered()",
        )
        return runner

    def test_registered_execution_resolves_then_delegates_unchanged_to_host(self):
        runner = self._runner()
        manifest = Path("/managed/runtime/agora.materializer.json")
        output = Path("/tmp/out")
        source = Path("/tmp/source")
        install_root = Path("/managed")
        registry_path = Path("/registry/materializers.yaml")
        with (
            mock.patch.object(registered, "resolve_installed_manifest", return_value=manifest) as resolve_mock,
            mock.patch.object(host, "materialize", return_value=output) as materialize_mock,
            mock.patch.object(installer, "fetch_materializer") as fetch_mock,
            mock.patch.object(installer, "install_materializer") as install_mock,
        ):
            result = runner(
                plugin_id="example-converter",
                materializer_id="example-to-tf",
                output=output,
                source=source,
                sandbox="off",
                install_root=install_root,
                registry_path=registry_path,
            )
        self.assertEqual(result, output)
        resolve_mock.assert_called_once_with(
            "example-converter",
            install_root=install_root,
            registry_path=registry_path,
        )
        materialize_mock.assert_called_once_with(
            manifest_path=manifest,
            materializer_id="example-to-tf",
            output=output,
            source=source,
            sandbox="off",
        )
        fetch_mock.assert_not_called()
        install_mock.assert_not_called()

    def test_resolution_failure_prevents_converter_host_invocation(self):
        runner = self._runner()
        with (
            mock.patch.object(
                registered,
                "resolve_installed_manifest",
                side_effect=installer.MaterializerInstallError("integrity failure"),
            ),
            mock.patch.object(host, "materialize") as materialize_mock,
        ):
            with self.assertRaisesRegex(installer.MaterializerInstallError, "integrity"):
                runner(
                    plugin_id="example-converter",
                    materializer_id="example-to-tf",
                    output=Path("/tmp/out"),
                )
        materialize_mock.assert_not_called()

    def test_registered_cli_has_one_unambiguous_registry_trust_source(self):
        self.assertIsNotNone(registered)
        parser_factory = getattr(registered, "_parser", None)
        self.assertTrue(callable(parser_factory), "RED 2: registered runner must expose its CLI parser")
        parser = parser_factory()
        args = parser.parse_args(
            [
                "--plugin",
                "example-converter",
                "--materializer",
                "example-to-tf",
                "--output",
                "/tmp/out",
                "--source",
                "/tmp/source",
                "--install-root",
                "/managed",
                "--registry",
                "/registry/materializers.yaml",
                "--sandbox",
                "off",
            ]
        )
        self.assertEqual(args.plugin, "example-converter")
        self.assertEqual(args.materializer, "example-to-tf")
        self.assertEqual(args.output, Path("/tmp/out"))
        self.assertEqual(args.source, Path("/tmp/source"))
        self.assertEqual(args.install_root, Path("/managed"))
        self.assertEqual(args.registry, Path("/registry/materializers.yaml"))
        self.assertEqual(args.sandbox, "off")

    def test_explicit_manifest_cli_remains_unchanged_and_separate(self):
        parser = host._parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "--materializer",
                    "example-to-tf",
                    "--output",
                    "/tmp/out",
                ]
            )
        args = parser.parse_args(
            [
                "--manifest",
                "/trusted/agora.materializer.json",
                "--materializer",
                "example-to-tf",
                "--output",
                "/tmp/out",
            ]
        )
        self.assertEqual(args.manifest, Path("/trusted/agora.materializer.json"))


if __name__ == "__main__":
    unittest.main()
