from __future__ import annotations

import contextlib
import importlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from scripts import agora_install_materializer as installer
from scripts import agora_materialize as host
from scripts import agora_materialize_registered as registered


REF = "0123456789abcdef0123456789abcdef01234567"
OTHER_REF = "89abcdef0123456789abcdef0123456789abcdef"
UNREVIEWED_EXECUTION_ID = "f" * 64
EVIDENCE_REF = "fedcba9876543210fedcba9876543210fedcba98"


def _plugin(*, cacheability: dict | None = None) -> dict:
    plugin = {
        "id": "example-converter",
        "name": "Example converter",
        "description": "Synthetic converter for cacheability authorization tests.",
        "repository": "example/converter",
        "ref": REF,
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
    if cacheability is not None:
        plugin["cacheability"] = cacheability
    return plugin


def _reusable(execution_identity: str) -> dict:
    return {
        "example-to-tf": {
            "mode": "reusable",
            "reviewed_ref": REF,
            "reviewed_environments": [
                {
                    "execution_identity_sha256": execution_identity,
                    "evidence": [
                        {
                            "type": "managed-replay",
                            "repository": "example/evidence",
                            "ref": EVIDENCE_REF,
                            "target": "tests/test_replay.py::test_repeatable",
                        }
                    ],
                }
            ],
        }
    }


def _manifest() -> dict:
    return {
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
                "description": "Convert synthetic source to TF.",
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


def _write_fixture_plugin(path: Path) -> None:
    package = path / "src/example_converter"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "cli.py").write_text(
        "def main():\n    return 0\n",
        encoding="utf-8",
    )
    (path / "pyproject.toml").write_text(
        "[build-system]\nrequires=['setuptools>=68']\nbuild-backend='setuptools.build_meta'\n"
        "[project]\nname='example-converter'\nversion='1.2.3'\n",
        encoding="utf-8",
    )
    (path / "agora.materializer.json").write_text(
        json.dumps(_manifest()),
        encoding="utf-8",
    )


def _fake_install(_plugin: dict, build_source: Path, runtime: Path, report: Path) -> None:
    import shutil

    shutil.copytree(build_source / "src/example_converter", runtime / "example_converter")
    metadata = runtime / "example_converter-1.2.3.dist-info/METADATA"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(
        "Metadata-Version: 2.1\nName: example-converter\nVersion: 1.2.3\n",
        encoding="utf-8",
    )
    report.write_text(json.dumps({"version": "1", "install": []}), encoding="utf-8")


def _write_registry(path: Path, plugin: dict) -> None:
    path.write_text(
        yaml.safe_dump({"schema_version": 1, "plugins": [plugin]}, sort_keys=False),
        encoding="utf-8",
    )


class MaterializerCacheabilityAuthorizationRedTests(unittest.TestCase):
    def _installed_fixture(self, root: Path) -> tuple[Path, Path, str]:
        registry_path = root / "materializers.yaml"
        _write_registry(registry_path, _plugin())

        def populate(_plugin_metadata: dict, destination: Path) -> str:
            _write_fixture_plugin(destination)
            return REF

        with mock.patch.object(installer, "_checkout", side_effect=populate), mock.patch.object(
            installer, "_install_python", side_effect=_fake_install
        ):
            target = installer.install_materializer(
                "example-converter",
                install_root=root / "installed",
                registry_path=registry_path,
                approve_code_execution=True,
            )
        receipt = json.loads(
            (target / installer.INSTALLATION_RECEIPT).read_text(encoding="utf-8")
        )
        return registry_path, target, receipt["execution_identity_sha256"]

    def test_authoritative_resolver_has_no_caller_execution_identity_parameter(self):
        resolver = registered.resolve_cacheability_authorization
        parameters = inspect.signature(resolver).parameters
        self.assertNotIn("execution_identity", parameters)
        self.assertNotIn("verified_execution_identity", parameters)
        self.assertNotIn("execution_identity_sha256", parameters)

    def test_authorization_uses_verified_installed_identity_not_a_caller_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path, _target, actual_identity = self._installed_fixture(root)

            _write_registry(registry_path, _plugin(cacheability=_reusable(UNREVIEWED_EXECUTION_ID)))
            rejected = registered.resolve_cacheability_authorization(
                "example-converter",
                "example-to-tf",
                install_root=root / "installed",
                registry_path=registry_path,
            )
            self.assertEqual(rejected["mode"], "unknown")
            self.assertFalse(rejected["reuse_allowed"])

            _write_registry(registry_path, _plugin(cacheability=_reusable(actual_identity)))
            accepted = registered.resolve_cacheability_authorization(
                "example-converter",
                "example-to-tf",
                install_root=root / "installed",
                registry_path=registry_path,
            )
            self.assertEqual(accepted["mode"], "reusable")
            self.assertTrue(accepted["reuse_allowed"])
            self.assertEqual(accepted["execution_identity_sha256"], actual_identity)
            self.assertEqual(accepted["plugin_id"], "example-converter")
            self.assertEqual(accepted["materializer_id"], "example-to-tf")
            self.assertEqual(accepted["plugin_ref"], REF)
            self.assertRegex(accepted["attestation_sha256"], r"^[0-9a-f]{64}$")

    def test_tampered_installation_receipt_cannot_authorize_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path, target, actual_identity = self._installed_fixture(root)
            _write_registry(registry_path, _plugin(cacheability=_reusable(actual_identity)))

            receipt_path = target / installer.INSTALLATION_RECEIPT
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["execution_identity_sha256"] = UNREVIEWED_EXECUTION_ID
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

            with self.assertRaisesRegex(
                installer.MaterializerInstallError,
                r"integrity verification",
            ):
                registered.resolve_cacheability_authorization(
                    "example-converter",
                    "example-to-tf",
                    install_root=root / "installed",
                    registry_path=registry_path,
                )

    def test_missing_installation_is_read_only_and_does_not_fetch_or_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = root / "materializers.yaml"
            _write_registry(
                registry_path,
                _plugin(cacheability=_reusable(UNREVIEWED_EXECUTION_ID)),
            )
            install_root = root / "installed"

            with mock.patch.object(installer, "fetch_materializer") as fetch, mock.patch.object(
                installer, "install_materializer"
            ) as install:
                with self.assertRaisesRegex(
                    installer.MaterializerInstallError,
                    r"not installed",
                ):
                    registered.resolve_cacheability_authorization(
                        "example-converter",
                        "example-to-tf",
                        install_root=install_root,
                        registry_path=registry_path,
                    )
            fetch.assert_not_called()
            install.assert_not_called()
            self.assertFalse(install_root.exists())

    def test_authorization_performs_no_fetch_install_repair_or_plugin_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path, _target, actual_identity = self._installed_fixture(root)
            _write_registry(registry_path, _plugin(cacheability=_reusable(actual_identity)))

            with mock.patch.object(installer, "fetch_materializer") as fetch, mock.patch.object(
                installer, "install_materializer"
            ) as install, mock.patch.object(importlib, "import_module") as import_module:
                result = registered.resolve_cacheability_authorization(
                    "example-converter",
                    "example-to-tf",
                    install_root=root / "installed",
                    registry_path=registry_path,
                )
            self.assertTrue(result["reuse_allowed"])
            fetch.assert_not_called()
            install.assert_not_called()
            import_module.assert_not_called()

    def test_registry_pin_change_while_waiting_for_runtime_lock_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path, _target, actual_identity = self._installed_fixture(root)
            _write_registry(registry_path, _plugin(cacheability=_reusable(actual_identity)))
            original_lock = installer._lock

            @contextlib.contextmanager
            def changing_lock(path: Path, *, timeout: float = installer.LOCK_WAIT_SECONDS):
                with original_lock(path, timeout=timeout):
                    changed = _plugin()
                    changed["ref"] = OTHER_REF
                    _write_registry(registry_path, changed)
                    yield

            with mock.patch.object(installer, "_lock", changing_lock):
                with self.assertRaisesRegex(
                    installer.MaterializerInstallError,
                    r"registry binding changed|integrity verification",
                ):
                    registered.resolve_cacheability_authorization(
                        "example-converter",
                        "example-to-tf",
                        install_root=root / "installed",
                        registry_path=registry_path,
                    )

    def test_integrity_verification_happens_inside_the_runtime_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path, _target, actual_identity = self._installed_fixture(root)
            _write_registry(registry_path, _plugin(cacheability=_reusable(actual_identity)))
            original_lock = installer._lock
            original_current = installer._environment_current
            lock_held = False

            @contextlib.contextmanager
            def observing_lock(path: Path, *, timeout: float = installer.LOCK_WAIT_SECONDS):
                nonlocal lock_held
                with original_lock(path, timeout=timeout):
                    lock_held = True
                    try:
                        yield
                    finally:
                        lock_held = False

            def observing_current(plugin: dict, target: Path) -> bool:
                self.assertTrue(lock_held, "runtime integrity must be verified while its lock is held")
                return original_current(plugin, target)

            with mock.patch.object(installer, "_lock", observing_lock), mock.patch.object(
                installer, "_environment_current", side_effect=observing_current
            ):
                result = registered.resolve_cacheability_authorization(
                    "example-converter",
                    "example-to-tf",
                    install_root=root / "installed",
                    registry_path=registry_path,
                )
            self.assertTrue(result["reuse_allowed"])

    def test_removed_materializer_cannot_receive_authorization_from_stale_installation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path, _target, _actual_identity = self._installed_fixture(root)
            current = _plugin()
            current["materializers"] = ["replacement-to-tf"]
            _write_registry(registry_path, current)
            with mock.patch.object(installer, "compare_cacheability_policy") as compare:
                with self.assertRaisesRegex(
                    installer.MaterializerInstallError,
                    r"not approved|binding|manifest materializer ids do not match registry",
                ):
                    registered.resolve_cacheability_authorization(
                        "example-converter",
                        "example-to-tf",
                        install_root=root / "installed",
                        registry_path=registry_path,
                    )
            compare.assert_not_called()

    def test_direct_execution_does_not_consult_cacheability_policy(self):
        plugin = _plugin()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "managed-environment"
            runtime = target / "runtime"
            runtime.mkdir(parents=True)
            manifest = runtime / plugin["manifest"]
            output = root / "out"
            with (
                mock.patch.object(registered, "_registered_target", return_value=(plugin, target)),
                mock.patch.object(registered, "resolve_installed_manifest", return_value=manifest),
                mock.patch.object(
                    installer,
                    "_lock",
                    return_value=mock.MagicMock(
                        __enter__=lambda self: None,
                        __exit__=lambda self, *args: False,
                    ),
                ),
                mock.patch.object(installer, "_validate_binding", return_value={}),
                mock.patch.object(installer, "compare_cacheability_policy") as compare,
                mock.patch.object(host, "materialize", return_value=output),
            ):
                result = registered.materialize_registered(
                    plugin_id="example-converter",
                    materializer_id="example-to-tf",
                    output=output,
                    install_root=root,
                )
            self.assertEqual(result, output)
            compare.assert_not_called()


if __name__ == "__main__":
    unittest.main()
