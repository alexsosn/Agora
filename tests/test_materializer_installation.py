from __future__ import annotations

import json
import multiprocessing
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml
from jsonschema import Draft202012Validator

from scripts.agora_install_materializer import (
    ENVIRONMENT_MARKER,
    INSTALLATION_RECEIPT,
    MaterializerInstallError,
    fetch_materializer,
    install_materializer,
    load_registry,
    runtime_tag,
    select_plugin,
    _lock,
    _require_pip,
    _verify_execution_modules_static,
    _checkout,
)
from scripts.agora_materialize import materialize

ROOT = Path(__file__).resolve().parents[1]
PSEUDEPIGRAPHA_TF_COMMIT = "082c6aeae72df8c93c11d8b6bbb1b69ec2b1f544"


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
                "package": {
                    "type": "python-project",
                    "path": ".",
                    "install_trust": "explicit-code-execution",
                },
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
    (path / "src/example_converter/cli.py").write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "def main():\n"
        "    source = Path(sys.argv[1])\n"
        "    output = Path(sys.argv[2])\n"
        "    assert (source / 'book.xml').is_file()\n"
        "    (output / 'otype.tf').write_text('otype', encoding='utf-8')\n"
        "    (output / 'oslots.tf').write_text('oslots', encoding='utf-8')\n"
        "if __name__ == '__main__':\n"
        "    main()\n",
        encoding="utf-8",
    )
    (path / "pyproject.toml").write_text(
        "[build-system]\nrequires=['setuptools>=68']\nbuild-backend='setuptools.build_meta'\n"
        "[project]\nname='example-converter'\nversion='1.2.3'\n",
        encoding="utf-8",
    )
    (path / "agora.materializer.json").write_text(
        json.dumps(_manifest(repository=repository)), encoding="utf-8"
    )


def _fake_install(_plugin, build_source: Path, runtime_root: Path, report: Path) -> None:
    import shutil

    shutil.copytree(build_source / "src/example_converter", runtime_root / "example_converter")
    for name, version in (("example-converter", "1.2.3"), ("example-dependency", "4.5.6")):
        metadata = runtime_root / f"{name.replace('-', '_')}-{version}.dist-info/METADATA"
        metadata.parent.mkdir(parents=True)
        metadata.write_text(
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n", encoding="utf-8"
        )
    report.write_text(json.dumps({"version": "1", "install": []}), encoding="utf-8")


def _hold_install_lock(path: str, ready, release) -> None:
    with _lock(Path(path), timeout=5):
        ready.set()
        release.wait(10)


def _crash_holding_install_lock(path: str, ready) -> None:
    with _lock(Path(path), timeout=5):
        ready.set()
        os._exit(0)


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
        self.assertEqual(plugin["package"]["install_trust"], "explicit-code-execution")


class MaterializerInstallerTests(unittest.TestCase):
    def _registry_path(self, root: Path) -> Path:
        path = root / "materializers.yaml"
        path.write_text(yaml.safe_dump(_registry(), sort_keys=False), encoding="utf-8")
        return path

    @staticmethod
    def _populate_checkout(_plugin, destination):
        _write_fixture_plugin(destination)
        return _registry()["plugins"][0]["ref"]

    def test_install_requires_explicit_code_execution_approval(self):
        with self.assertRaisesRegex(MaterializerInstallError, "approve-code-execution"):
            install_materializer("example-converter")

    @mock.patch("scripts.agora_install_materializer._install_python")
    @mock.patch("scripts.agora_install_materializer._checkout")
    def test_fetch_downloads_and_validates_without_packaging_execution(self, checkout, install_python):
        checkout.side_effect = self._populate_checkout
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = fetch_materializer(
                "example-converter",
                install_root=root / "installed",
                registry_path=self._registry_path(root),
            )
            self.assertTrue((source / "agora.materializer.json").is_file())
        install_python.assert_not_called()

    @mock.patch("scripts.agora_install_materializer._install_python", side_effect=_fake_install)
    @mock.patch("scripts.agora_install_materializer._checkout")
    def test_install_records_source_runtime_and_dependency_identity(self, checkout, _install_python):
        checkout.side_effect = self._populate_checkout
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = install_materializer(
                "example-converter",
                install_root=root / "installed",
                registry_path=self._registry_path(root),
                approve_code_execution=True,
            )
            receipt = json.loads((target / INSTALLATION_RECEIPT).read_text(encoding="utf-8"))
            marker = json.loads((target / "runtime" / ENVIRONMENT_MARKER).read_text(encoding="utf-8"))

        self.assertEqual(receipt["schema_version"], 2)
        self.assertEqual(receipt["plugin"]["id"], "example-converter")
        self.assertEqual(receipt["environment"]["install_trust"], "explicit-code-execution")
        self.assertRegex(receipt["source"]["tree_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(receipt["environment"]["tree_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(receipt["environment"]["descriptor_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(marker["descriptor_sha256"], receipt["environment"]["descriptor_sha256"])
        self.assertEqual(
            receipt["environment"]["distributions"],
            [
                {"name": "example-converter", "version": "1.2.3"},
                {"name": "example-dependency", "version": "4.5.6"},
            ],
        )

    @mock.patch("scripts.agora_install_materializer._install_python", side_effect=_fake_install)
    @mock.patch("scripts.agora_install_materializer._checkout")
    def test_current_installation_is_idempotent(self, checkout, install_python):
        checkout.side_effect = self._populate_checkout
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = self._registry_path(root)
            first = install_materializer(
                "example-converter",
                install_root=root / "installed",
                registry_path=registry_path,
                approve_code_execution=True,
            )
            checkout.reset_mock()
            install_python.reset_mock()
            second = install_materializer(
                "example-converter",
                install_root=root / "installed",
                registry_path=registry_path,
                approve_code_execution=True,
            )
        self.assertEqual(first, second)
        checkout.assert_not_called()
        install_python.assert_not_called()

    @mock.patch("scripts.agora_install_materializer._install_python", side_effect=_fake_install)
    @mock.patch("scripts.agora_install_materializer._checkout")
    def test_source_modification_invalidates_managed_installation(self, checkout, _install_python):
        checkout.side_effect = self._populate_checkout
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = self._registry_path(root)
            target = install_materializer(
                "example-converter",
                install_root=root / "installed",
                registry_path=registry_path,
                approve_code_execution=True,
            )
            source = target.parent.parent / "source"
            (source / "src/example_converter/cli.py").write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(MaterializerInstallError, "fetched source integrity failed"):
                install_materializer(
                    "example-converter",
                    install_root=root / "installed",
                    registry_path=registry_path,
                    approve_code_execution=True,
                )

    @mock.patch("scripts.agora_install_materializer._install_python", side_effect=_fake_install)
    @mock.patch("scripts.agora_install_materializer._checkout")
    def test_dependency_or_runtime_modification_invalidates_installation(self, checkout, _install_python):
        checkout.side_effect = self._populate_checkout
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = self._registry_path(root)
            target = install_materializer(
                "example-converter",
                install_root=root / "installed",
                registry_path=registry_path,
                approve_code_execution=True,
            )
            (target / "runtime/example_dependency.py").write_text("tampered = True\n", encoding="utf-8")
            with self.assertRaisesRegex(MaterializerInstallError, "installed environment integrity failed"):
                install_materializer(
                    "example-converter",
                    install_root=root / "installed",
                    registry_path=registry_path,
                    approve_code_execution=True,
                )

    @mock.patch("scripts.agora_install_materializer._install_python", side_effect=_fake_install)
    @mock.patch("scripts.agora_install_materializer._checkout")
    def test_build_cannot_mutate_validated_source_unnoticed(self, checkout, _install_python):
        checkout.side_effect = self._populate_checkout
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = self._registry_path(root)
            source = fetch_materializer(
                "example-converter",
                install_root=root / "installed",
                registry_path=registry_path,
            )

            def mutate_source(plugin, build_source, runtime_root, report):
                _fake_install(plugin, build_source, runtime_root, report)
                (source / "src/example_converter/cli.py").write_text("mutated\n", encoding="utf-8")

            with mock.patch(
                "scripts.agora_install_materializer._install_python",
                side_effect=mutate_source,
            ):
                with self.assertRaisesRegex(
                    MaterializerInstallError, "installation mutated immutable fetched source"
                ):
                    install_materializer(
                        "example-converter",
                        install_root=root / "installed",
                        registry_path=registry_path,
                        approve_code_execution=True,
                    )

    def test_static_module_verification_does_not_import_parent_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "example_converter"
            package.mkdir()
            sentinel = root / "imported"
            (package / "__init__.py").write_text(
                f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('executed')\n",
                encoding="utf-8",
            )
            (package / "cli.py").write_text("VALUE = 1\n", encoding="utf-8")
            _verify_execution_modules_static(_manifest(), root)
            self.assertFalse(sentinel.exists())

    def test_runtime_tag_separates_python_patch_abi_and_platform(self):
        base = {
            "implementation": "cpython",
            "version": "3.12.10",
            "cache_tag": "cpython-312",
            "abi": "cpython-312-x86_64-linux-gnu",
            "platform": "linux-x86_64",
            "system": "Linux",
            "machine": "x86_64",
        }
        changed = dict(base, version="3.12.11")
        self.assertNotEqual(runtime_tag(base), runtime_tag(changed))
        self.assertNotEqual(runtime_tag(base), runtime_tag(dict(base, platform="macosx-14-arm64")))

    @mock.patch("scripts.agora_install_materializer.shutil.which", return_value="/usr/bin/git")
    @mock.patch("scripts.agora_install_materializer._git")
    def test_wrong_downloaded_commit_is_rejected(self, run_git, _which):
        run_git.side_effect = lambda _command, _env, capture=False: "f" * 40 if capture else None
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "checkout"
            destination.mkdir()
            with self.assertRaisesRegex(MaterializerInstallError, "does not match registered commit"):
                _checkout(_registry()["plugins"][0], destination)

    @mock.patch("scripts.agora_install_materializer._install_python", side_effect=_fake_install)
    @mock.patch("scripts.agora_install_materializer._checkout")
    def test_managed_environment_hash_is_artifact_code_provenance(self, checkout, _install_python):
        checkout.side_effect = self._populate_checkout
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = self._registry_path(root)
            target = install_materializer(
                "example-converter",
                install_root=root / "installed",
                registry_path=registry_path,
                approve_code_execution=True,
            )
            input_root = root / "input"
            input_root.mkdir()
            (input_root / "book.xml").write_text("<book/>", encoding="utf-8")
            artifact = root / "artifact"
            materialize(
                manifest_path=target / "runtime/agora.materializer.json",
                materializer_id="example-to-tf",
                source=input_root,
                output=artifact,
                sandbox="off",
            )
            receipt = json.loads((target / INSTALLATION_RECEIPT).read_text(encoding="utf-8"))
            provenance = json.loads((artifact / "agora-materialization.json").read_text(encoding="utf-8"))
            self.assertEqual(
                provenance["plugin"]["code_sha256"],
                receipt["environment"]["tree_sha256"],
            )


class MaterializerInstallLockTests(unittest.TestCase):
    """Installation locks must be owned by the OS, not by a lock file's existence."""

    def test_live_holder_blocks_and_process_death_releases_install_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".environment.lock"
            ctx = multiprocessing.get_context("spawn")

            ready, release = ctx.Event(), ctx.Event()
            holder = ctx.Process(target=_hold_install_lock, args=(str(path), ready, release))
            holder.start()
            try:
                self.assertTrue(ready.wait(10))
                with self.assertRaisesRegex(MaterializerInstallError, "another materializer operation"):
                    with _lock(path, timeout=0.1):
                        pass
            finally:
                release.set()
                holder.join(10)
            self.assertEqual(holder.exitcode, 0)

            ready = ctx.Event()
            crashed = ctx.Process(target=_crash_holding_install_lock, args=(str(path), ready))
            crashed.start()
            self.assertTrue(ready.wait(10))
            crashed.join(10)
            self.assertEqual(crashed.exitcode, 0)

            # The lock file outlives the dead holder; the lock itself must not.
            self.assertTrue(path.exists())
            with _lock(path, timeout=0.5):
                pass

    @mock.patch("scripts.agora_install_materializer._install_python", side_effect=_fake_install)
    @mock.patch("scripts.agora_install_materializer._checkout")
    def test_leftover_lock_file_does_not_wedge_installation(self, checkout, _install_python):
        checkout.side_effect = MaterializerInstallerTests._populate_checkout
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = root / "materializers.yaml"
            registry_path.write_text(yaml.safe_dump(_registry(), sort_keys=False), encoding="utf-8")
            install_root = root / "installed"
            commit = _registry()["plugins"][0]["ref"]
            base = install_root / "example-converter" / commit
            base.mkdir(parents=True)
            (base / ".source.lock").write_text("", encoding="utf-8")

            target = install_materializer(
                "example-converter",
                install_root=install_root,
                registry_path=registry_path,
                approve_code_execution=True,
            )
            self.assertTrue((target / INSTALLATION_RECEIPT).is_file())


class MaterializerPipPreflightTests(unittest.TestCase):
    def test_interpreter_without_pip_is_reported_actionably(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="No module named pip\n"
        )
        with mock.patch("scripts.agora_install_materializer.subprocess.run", return_value=completed):
            with self.assertRaises(MaterializerInstallError) as caught:
                _require_pip()
        message = str(caught.exception)
        self.assertIn("no usable pip", message)
        self.assertIn("ensurepip", message)
        self.assertIn("No module named pip", message)

    def test_usable_pip_passes_preflight(self):
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="pip 24.0\n", stderr="")
        with mock.patch("scripts.agora_install_materializer.subprocess.run", return_value=completed):
            _require_pip()


if __name__ == "__main__":
    unittest.main()
