from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator

from scripts.agora_materialize import (
    ManifestError,
    build_sandbox_command,
    load_manifest,
    materialize,
    prepare_user_source,
    validate_output,
)

ROOT = Path(__file__).resolve().parents[1]


def _manifest() -> dict:
    return {
        "schema_version": 1,
        "plugin": {
            "id": "example-converter",
            "name": "Example converter",
            "version": "1.0.0",
        },
        "materializers": [
            {
                "id": "example-to-tf",
                "description": "Convert example source files to Text-Fabric.",
                "acquisition": [
                    {
                        "type": "git",
                        "url": "https://github.com/example/example-data.git",
                        "ref": "0123456789abcdef",
                        "subpath": "data",
                    },
                    {
                        "type": "user-local",
                        "path_type": "directory",
                        "prompt": "Select the source data directory",
                    },
                ],
                "input": {
                    "type": "directory",
                    "required_globs": ["*.xml"],
                    "allow_symlinks": False,
                },
                "execution": {
                    "type": "python-module",
                    "module": "example_converter.cli",
                    "args": ["convert", "{source}", "--output", "{output}"],
                    "network": "deny",
                },
                "output": {
                    "format": "text-fabric",
                    "required_paths": ["otype.tf", "oslots.tf"],
                },
            }
        ],
    }


def _write_manifest(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc), encoding="utf-8")


class MaterializerManifestTests(unittest.TestCase):
    def test_schema_accepts_reference_contract(self):
        schema = json.loads(
            (ROOT / "registry/schema/materializer-plugin.schema.json").read_text(encoding="utf-8")
        )
        errors = sorted(Draft202012Validator(schema).iter_errors(_manifest()), key=str)
        self.assertEqual(errors, [])

    def test_runtime_accepts_reference_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agora.materializer.json"
            _write_manifest(path, _manifest())
            manifest = load_manifest(path)
        self.assertEqual(manifest["plugin"]["id"], "example-converter")
        self.assertEqual(manifest["materializers"][0]["output"]["format"], "text-fabric")

    def test_runtime_uses_schema_for_plugin_repository(self):
        doc = _manifest()
        doc["plugin"]["repository"] = ["not", "a", "string"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agora.materializer.json"
            _write_manifest(path, doc)
            with self.assertRaisesRegex(ManifestError, "violates schema"):
                load_manifest(path)

    def test_runtime_rejects_shell_execution(self):
        doc = _manifest()
        doc["materializers"][0]["execution"]["type"] = "shell"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agora.materializer.json"
            _write_manifest(path, doc)
            with self.assertRaisesRegex(ManifestError, "violates schema"):
                load_manifest(path)

    def test_runtime_rejects_unknown_argument_placeholder(self):
        doc = _manifest()
        doc["materializers"][0]["execution"]["args"].append("{home}")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agora.materializer.json"
            _write_manifest(path, doc)
            with self.assertRaisesRegex(ManifestError, "violates schema"):
                load_manifest(path)

    def test_runtime_accepts_source_revision_placeholder(self):
        doc = _manifest()
        doc["materializers"][0]["execution"]["args"].extend(
            ["--upstream-commit", "{source_revision}"]
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agora.materializer.json"
            _write_manifest(path, doc)
            manifest = load_manifest(path)
        self.assertIn(
            "{source_revision}", manifest["materializers"][0]["execution"]["args"]
        )


class MaterializerFilesystemTests(unittest.TestCase):
    def test_user_source_must_match_declared_input(self):
        spec = _manifest()["materializers"][0]
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            with self.assertRaisesRegex(ValueError, "required input pattern"):
                prepare_user_source(source, spec)
            (source / "book.xml").write_text("<book/>", encoding="utf-8")
            prepared = prepare_user_source(source, spec)
            self.assertEqual(prepared.path, source.resolve())
            self.assertEqual(prepared.provenance["type"], "user-local")
            self.assertRegex(prepared.provenance["tree_sha256"], r"^[0-9a-f]{64}$")

    def test_user_source_digest_changes_with_contents(self):
        spec = _manifest()["materializers"][0]
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            xml = source / "book.xml"
            xml.write_text("<book>A</book>", encoding="utf-8")
            first = prepare_user_source(source, spec).provenance["tree_sha256"]
            xml.write_text("<book>B</book>", encoding="utf-8")
            second = prepare_user_source(source, spec).provenance["tree_sha256"]
            self.assertNotEqual(first, second)

    def test_user_source_rejects_symlinks_by_default(self):
        spec = _manifest()["materializers"][0]
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            source.mkdir()
            (source / "book.xml").write_text("<book/>", encoding="utf-8")
            outside = Path(tmp) / "outside.txt"
            outside.write_text("secret", encoding="utf-8")
            (source / "link").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "symlink"):
                prepare_user_source(source, spec)

    def test_output_must_contain_declared_paths(self):
        spec = _manifest()["materializers"][0]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "otype.tf").write_text("x", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "oslots.tf"):
                validate_output(output, spec)
            (output / "oslots.tf").write_text("x", encoding="utf-8")
            validate_output(output, spec)


class MaterializerExecutionTests(unittest.TestCase):
    def _fixture(self, root: Path, *, fail: bool = False, revision_arg: bool = False):
        plugin = root / "plugin"
        source = root / "source"
        output = root / "artifact"
        plugin.mkdir()
        source.mkdir()
        (source / "book.xml").write_text("<book/>", encoding="utf-8")
        body = [
            "from pathlib import Path",
            "import sys",
            "source = Path(sys.argv[1])",
            "output = Path(sys.argv[2])",
            "assert (source / 'book.xml').is_file()",
            "(output / 'otype.tf').write_text('otype', encoding='utf-8')",
        ]
        if fail:
            body.append("raise RuntimeError('fixture failure')")
        else:
            body.append("(output / 'oslots.tf').write_text('oslots', encoding='utf-8')")
            if revision_arg:
                body.append("(output / 'revision.txt').write_text(sys.argv[3], encoding='utf-8')")
        (plugin / "fixture_converter.py").write_text("\n".join(body) + "\n", encoding="utf-8")

        doc = _manifest()
        args = ["{source}", "{output}"]
        if revision_arg:
            args.append("{source_revision}")
        doc["materializers"][0]["execution"] = {
            "type": "python-module",
            "module": "fixture_converter",
            "args": args,
            "network": "deny",
        }
        manifest_path = plugin / "agora.materializer.json"
        _write_manifest(manifest_path, doc)
        return plugin, source, output, manifest_path

    def test_materialize_runs_declared_module_and_writes_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, source, output, manifest_path = self._fixture(root)
            result = materialize(
                manifest_path=manifest_path,
                materializer_id="example-to-tf",
                source=source,
                output=output,
                sandbox="off",
            )

            self.assertEqual(result, output.resolve())
            provenance = json.loads((output / "agora-materialization.json").read_text(encoding="utf-8"))
            self.assertEqual(provenance["plugin"]["id"], "example-converter")
            self.assertRegex(provenance["plugin"]["code_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(provenance["materializer"], "example-to-tf")
            self.assertEqual(provenance["source"]["type"], "user-local")
            self.assertRegex(provenance["source"]["tree_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(provenance["output"]["format"], "text-fabric")
            self.assertEqual(provenance["sandbox"], "none-explicit")

    def test_materialization_is_transactional_on_converter_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, source, output, manifest_path = self._fixture(root, fail=True)
            output.mkdir()
            with self.assertRaises(subprocess.CalledProcessError):
                materialize(
                    manifest_path=manifest_path,
                    materializer_id="example-to-tf",
                    source=source,
                    output=output,
                    sandbox="off",
                )
            self.assertTrue(output.is_dir())
            self.assertEqual(list(output.iterdir()), [])
            self.assertEqual(list(root.glob(".artifact.agora-stage-*")), [])

    def test_materializer_code_digest_changes_when_code_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin, source, output, manifest_path = self._fixture(root)
            materialize(
                manifest_path=manifest_path,
                materializer_id="example-to-tf",
                source=source,
                output=output,
                sandbox="off",
            )
            first = json.loads((output / "agora-materialization.json").read_text(encoding="utf-8"))[
                "plugin"
            ]["code_sha256"]

            output2 = root / "artifact-2"
            (plugin / "fixture_converter.py").write_text(
                (plugin / "fixture_converter.py").read_text(encoding="utf-8") + "# changed\n",
                encoding="utf-8",
            )
            materialize(
                manifest_path=manifest_path,
                materializer_id="example-to-tf",
                source=source,
                output=output2,
                sandbox="off",
            )
            second = json.loads((output2 / "agora-materialization.json").read_text(encoding="utf-8"))[
                "plugin"
            ]["code_sha256"]
            self.assertNotEqual(first, second)

    @mock.patch("scripts.agora_materialize.acquire_source")
    def test_preflight_rejects_bad_output_before_acquisition(self, acquire_source):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, source, output, manifest_path = self._fixture(root)
            output.mkdir()
            (output / "occupied").write_text("x", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be empty"):
                materialize(
                    manifest_path=manifest_path,
                    materializer_id="example-to-tf",
                    source=source,
                    output=output,
                    sandbox="off",
                )
            acquire_source.assert_not_called()

    @mock.patch("scripts.agora_materialize._detect_local_git_revision", return_value="deadbeef")
    def test_source_revision_is_passed_to_materializer(self, _revision):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, source, output, manifest_path = self._fixture(root, revision_arg=True)
            materialize(
                manifest_path=manifest_path,
                materializer_id="example-to-tf",
                source=source,
                output=output,
                sandbox="off",
            )
            self.assertEqual((output / "revision.txt").read_text(encoding="utf-8"), "deadbeef")


class MaterializerSandboxConstructionTests(unittest.TestCase):
    @mock.patch("scripts.agora_materialize.platform.system", return_value="Linux")
    @mock.patch("scripts.agora_materialize.shutil.which", return_value="/usr/bin/bwrap")
    def test_linux_sandbox_denies_network_and_maps_input_read_only(self, _which, _system):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            output = root / "output"
            plugin_root = root / "plugin"
            work = root / "work"
            for path in (source, output, plugin_root, work):
                path.mkdir()
            command, backend = build_sandbox_command(
                plugin_root=plugin_root,
                source=source,
                output=output,
                work_dir=work,
                module="example_converter.cli",
                args=["convert", "{source}", "--output", "{output}"],
            )
        self.assertEqual(backend, "bubblewrap")
        self.assertIn("--unshare-all", command)
        self.assertIn("--ro-bind", command)
        self.assertIn(str(source.resolve()), command)
        self.assertIn("/input", command)
        self.assertIn(str(output.resolve()), command)
        self.assertIn("/output", command)
        self.assertNotIn("sh", command[:2])

    @mock.patch("scripts.agora_materialize.platform.system", return_value="Darwin")
    @mock.patch("scripts.agora_materialize.shutil.which", return_value="/usr/bin/sandbox-exec")
    def test_macos_profile_grants_output_read_and_write(self, _which, _system):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("source", "output", "plugin", "work"):
                (root / name).mkdir()
            command, backend = build_sandbox_command(
                plugin_root=root / "plugin",
                source=root / "source",
                output=root / "output",
                work_dir=root / "work",
                module="example.cli",
                args=["{source}", "{output}"],
            )
            profile = (root / "work" / "materializer.sb").read_text(encoding="utf-8")
        self.assertEqual(backend, "sandbox-exec")
        self.assertIn(str((root / "output").resolve()), profile)
        self.assertIn("allow file-read*", profile)
        self.assertIn("allow file-write*", profile)
        self.assertEqual(command[0], "/usr/bin/sandbox-exec")

    @mock.patch("scripts.agora_materialize.platform.system", return_value="Windows")
    def test_required_sandbox_fails_closed_when_backend_is_unavailable(self, _system):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("source", "output", "plugin", "work"):
                (root / name).mkdir()
            with self.assertRaisesRegex(RuntimeError, "sandbox"):
                build_sandbox_command(
                    plugin_root=root / "plugin",
                    source=root / "source",
                    output=root / "output",
                    work_dir=root / "work",
                    module="example.cli",
                    args=["{source}", "{output}"],
                )


if __name__ == "__main__":
    unittest.main()
