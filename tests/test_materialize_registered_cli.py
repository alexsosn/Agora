from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import agora_materialize as host
from scripts import agora_materialize_registered as registered


class RegisteredMaterializationTests(unittest.TestCase):
    def _runner(self):
        runner = getattr(registered, "materialize_registered", None)
        self.assertTrue(
            callable(runner),
            "RED contract: registered runner must expose materialize_registered()",
        )
        return runner

    def test_programmatic_runner_resolves_verified_manifest_then_delegates(self):
        runner = self._runner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "managed" / "agora.materializer.json"
            source = root / "source"
            output = root / "output"
            registry = root / "registry.yaml"
            with (
                mock.patch.object(
                    registered,
                    "resolve_installed_manifest",
                    return_value=manifest,
                ) as resolve_mock,
                mock.patch.object(
                    registered,
                    "materialize",
                    return_value=output,
                    create=True,
                ) as materialize_mock,
            ):
                result = runner(
                    "example-converter",
                    "example-to-tf",
                    output=output,
                    source=source,
                    install_root=root / "installs",
                    registry_path=registry,
                    sandbox="required",
                )

        self.assertEqual(result, output)
        resolve_mock.assert_called_once_with(
            "example-converter",
            install_root=root / "installs",
            registry_path=registry,
        )
        materialize_mock.assert_called_once_with(
            manifest_path=manifest,
            materializer_id="example-to-tf",
            output=output,
            source=source,
            sandbox="required",
        )

    def test_unknown_materializer_id_fails_before_source_acquisition(self):
        runner = self._runner()
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
            manifest = root / "agora.materializer.json"
            manifest.write_text(json.dumps(manifest_doc), encoding="utf-8")
            with (
                mock.patch.object(
                    registered,
                    "resolve_installed_manifest",
                    return_value=manifest,
                ),
                mock.patch.object(host, "acquire_source") as acquire_mock,
            ):
                with self.assertRaisesRegex(KeyError, "unknown materializer"):
                    runner(
                        "example-converter",
                        "missing-materializer",
                        output=root / "output",
                        source=root / "source",
                        sandbox="off",
                    )
            acquire_mock.assert_not_called()

    def test_registered_cli_exposes_plugin_and_materializer_ids_without_manifest_path(self):
        parser_factory = getattr(registered, "_parser", None)
        self.assertTrue(
            callable(parser_factory),
            "RED contract: registered runner must expose its CLI parser",
        )
        parser = parser_factory()
        args = parser.parse_args(
            [
                "example-converter",
                "example-to-tf",
                "--source",
                "/tmp/source",
                "--output",
                "/tmp/output",
                "--install-root",
                "/tmp/installs",
                "--registry",
                "/tmp/registry.yaml",
                "--sandbox",
                "off",
            ]
        )
        self.assertEqual(args.plugin_id, "example-converter")
        self.assertEqual(args.materializer_id, "example-to-tf")
        self.assertFalse(hasattr(args, "manifest"))

    def test_registered_cli_main_delegates_without_installing(self):
        main = getattr(registered, "main", None)
        self.assertTrue(callable(main), "RED contract: registered runner must expose main()")
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(registered, "materialize_registered", return_value=Path(tmp) / "out") as run_mock,
            mock.patch("scripts.agora_install_materializer.install_materializer") as install_mock,
            mock.patch("scripts.agora_install_materializer.fetch_materializer") as fetch_mock,
        ):
            result = main(
                [
                    "example-converter",
                    "example-to-tf",
                    "--source",
                    str(Path(tmp) / "source"),
                    "--output",
                    str(Path(tmp) / "out"),
                    "--install-root",
                    str(Path(tmp) / "installs"),
                    "--sandbox",
                    "off",
                ]
            )
        self.assertEqual(result, 0)
        self.assertEqual(run_mock.call_count, 1)
        install_mock.assert_not_called()
        fetch_mock.assert_not_called()

    def test_existing_explicit_manifest_cli_contract_is_unchanged(self):
        args = host._parser().parse_args(
            [
                "--manifest",
                "/trusted/plugin/agora.materializer.json",
                "--materializer",
                "example-to-tf",
                "--source",
                "/tmp/source",
                "--output",
                "/tmp/output",
                "--sandbox",
                "off",
            ]
        )
        self.assertEqual(args.manifest, Path("/trusted/plugin/agora.materializer.json"))
        self.assertEqual(args.materializer, "example-to-tf")


if __name__ == "__main__":
    unittest.main()
