"""#239 RED: direct researcher CLI never bypasses catalog producer authorization."""
from __future__ import annotations

import contextlib
import io
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from scripts import agora_compose_feature_module as compose


class ManagedFeatureModuleCliRedTests(unittest.TestCase):
    def call_cli(self, argv):
        main = getattr(compose, "main", None)
        self.assertTrue(callable(main), "RED: managed materializer CLI missing")
        return main(argv)

    def test_cli_resolves_only_bundled_module_producer_and_runs_existing_host(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "workbooks"
            source.mkdir()
            output = root / "cache/local-modules/cuc-burns/tf/0.2.8"
            module = SimpleNamespace(
                kind="feature-module", acquisition_strategy="local-module",
                materializer={"plugin": "cuc-burns", "id": "cuc-burns-csv"},
            )
            catalog = mock.Mock()
            catalog.get.return_value = module
            resolver = SimpleNamespace(catalog=catalog)
            capture = io.StringIO()
            with (
                mock.patch.object(compose, "_bundled_context_fabric_resolver", return_value=resolver) as make,
                mock.patch.object(compose, "materialize_requested_feature_module", return_value=output) as produce,
                contextlib.redirect_stdout(capture),
            ):
                result = self.call_cli([
                    "--module", "cuc-burns", "--source", str(source),
                    "--cache-dir", str(root / "cache"),
                    "--install-root", str(root / "installed"),
                    "--parent-version", "0.2.8",
                ])
            self.assertEqual(result, 0)
            self.assertIn(str(output), capture.getvalue())
            make.assert_called_once_with(cache_dir=root / "cache")
            catalog.get.assert_called_once_with("cuc-burns")
            produce.assert_called_once_with(
                module_id="cuc-burns", plugin_id="cuc-burns",
                materializer_id="cuc-burns-csv", source=source,
                requested_version="0.2.8", cache_dir=root / "cache",
                install_root=root / "installed",
            )

    def test_missing_catalog_producer_refused_before_converter_execution(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "workbooks"
            source.mkdir()
            catalog = mock.Mock()
            catalog.get.return_value = SimpleNamespace(
                kind="feature-module", materializer=None,
                acquisition_strategy="local-module",
            )
            with (
                mock.patch.object(compose, "_bundled_context_fabric_resolver",
                                  return_value=SimpleNamespace(catalog=catalog)),
                mock.patch.object(compose, "materialize_requested_feature_module") as produce,
                contextlib.redirect_stderr(io.StringIO()),
            ):
                with self.assertRaises(SystemExit) as ex:
                    self.call_cli(["--module", "cuc-burns", "--source", str(source)])
            self.assertEqual(ex.exception.code, 2)
            produce.assert_not_called()

    def test_uninstalled_producer_has_actionable_cli_error_without_approval(self):
        from scripts.agora_install_materializer import MaterializerInstallError

        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "workbooks"
            source.mkdir()
            module = SimpleNamespace(
                kind="feature-module", acquisition_strategy="local-module",
                materializer={"plugin": "cuc-burns", "id": "cuc-burns-csv"},
            )
            catalog = mock.Mock()
            catalog.get.return_value = module
            stderr = io.StringIO()
            with (
                mock.patch.object(compose, "_bundled_context_fabric_resolver",
                                  return_value=SimpleNamespace(catalog=catalog)),
                mock.patch.object(
                    compose, "materialize_requested_feature_module",
                    side_effect=MaterializerInstallError("producer not installed")
                ) as produce,
                contextlib.redirect_stderr(stderr),
            ):
                with self.assertRaises(SystemExit) as ex:
                    self.call_cli(["--module", "cuc-burns", "--source", str(source)])
            self.assertEqual(ex.exception.code, 2)
            self.assertIn("producer not installed", stderr.getvalue())
            produce.assert_called_once()

    def test_unknown_or_unsafe_flags_refused_before_installer_or_converter(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "workbooks"
            source.mkdir()
            for extra in (
                ["--parent-path", "/tmp/foreign"],
                ["--resolver", "/tmp/foreign"],
                ["--trusted"],
                ["--registry-path", "/tmp/malicious.yaml"],
                ["--plugin", "unreviewed"],
                ["--materializer", "unreviewed"],
                ["--approve-code-execution"],
                ["--output", "/tmp/foreign"],
            ):
                with self.subTest(extra=extra), (
                    mock.patch.object(compose, "materialize_requested_feature_module") as produce,
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    with self.assertRaises(SystemExit) as ex:
                        self.call_cli(["--module", "cuc-burns", "--source", str(source), *extra])
                    self.assertEqual(ex.exception.code, 2)
                    produce.assert_not_called()

    def test_guide_explicit_approval_and_local_cuc_burns_query(self):
        guide = Path(__file__).resolve().parents[1] / "wiki/guides/cuc-burns-managed.md"
        content = guide.read_text(encoding="utf-8")
        for snippet in (
            "fetch cuc-burns",
            "install cuc-burns --approve-code-execution",
            "python -m scripts.agora_compose_feature_module",
            "--module cuc-burns --source",
            'modules=["cuc-burns"]',
            "0.2.8",
            "CC-BY-NC-ND",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, content)

    def test_real_burns_acceptance_exercises_the_public_command_not_only_internal_helper(self):
        script = (Path(__file__).resolve().parents[1] /
                  "tests/live_ctc_burns_registered_237.py").read_text(encoding="utf-8")
        self.assertIn("module_cli([", script)
        self.assertIn('"--module", "cuc-burns"', script)
        self.assertIn('"--parent-version", "0.2.8"', script)
        self.assertNotIn("materialize_requested_feature_module(", script)
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/materialization-sandbox.yml").read_text(encoding="utf-8")
        self.assertIn("'scripts/agora_compose_feature_module.py'", workflow)

    def test_nonexistent_source_refused_without_materializer_execution(self):
        with mock.patch.object(compose, "materialize_requested_feature_module") as produce, (
            contextlib.redirect_stderr(io.StringIO())
        ):
            with self.assertRaises(SystemExit) as ex:
                self.call_cli(["--module", "cuc-burns", "--source", "/absent/no-source"])
        self.assertEqual(ex.exception.code, 2)
        produce.assert_not_called()


if __name__ == "__main__":
    unittest.main()
