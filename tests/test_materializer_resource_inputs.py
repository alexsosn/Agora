from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import agora_materialize as host


IMMUTABLE_REVISION = "ad69400f5446e1c8217af01659c7c10ab00c015b"


def _manifest(*, with_resource: bool = True) -> dict:
    materializer = {
        "id": "example-to-tf",
        "description": "Synthetic feature-module materializer.",
        "acquisition": [
            {
                "type": "user-local",
                "path_type": "directory",
                "prompt": "Select source",
            }
        ],
        "input": {
            "type": "directory",
            "required_globs": ["*.txt"],
            "allow_symlinks": False,
        },
        "execution": {
            "type": "python-module",
            "module": "fixture_converter",
            "args": ["{source}", "{output}"],
            "network": "deny",
        },
        "output": {
            "format": "text-fabric-feature-module",
            "required_paths": ["feature.tf"],
        },
    }
    if with_resource:
        materializer["resource_inputs"] = [
            {
                "name": "parent",
                "resource": "cuc",
                "version": "0.2.8",
                "source_revision": IMMUTABLE_REVISION,
            }
        ]
        materializer["execution"]["args"].extend(["--parent", "{resource:parent}"])
    return {
        "schema_version": 1,
        "plugin": {
            "id": "example-converter",
            "name": "Example converter",
            "version": "1.0.0",
        },
        "materializers": [materializer],
    }


def _write_manifest(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc), encoding="utf-8")


class ResourceInputManifestRedTests(unittest.TestCase):
    def test_named_resource_input_and_placeholder_are_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agora.materializer.json"
            _write_manifest(path, _manifest())
            parsed = host.load_manifest(path)
        self.assertEqual(parsed["materializers"][0]["resource_inputs"][0]["resource"], "cuc")

    def test_existing_single_source_manifest_remains_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agora.materializer.json"
            _write_manifest(path, _manifest(with_resource=False))
            parsed = host.load_manifest(path)
        self.assertNotIn("resource_inputs", parsed["materializers"][0])

    def test_duplicate_resource_input_names_are_rejected(self):
        doc = _manifest()
        doc["materializers"][0]["resource_inputs"].append(
            {
                "name": "parent",
                "resource": "other",
                "version": "1.0",
                "source_revision": "0123456789abcdef0123456789abcdef01234567",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agora.materializer.json"
            _write_manifest(path, doc)
            with self.assertRaisesRegex(host.ManifestError, "duplicate.*resource.*name"):
                host.load_manifest(path)

    def test_undeclared_resource_placeholder_is_rejected(self):
        doc = _manifest(with_resource=False)
        doc["materializers"][0]["execution"]["args"].append("{resource:missing}")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agora.materializer.json"
            _write_manifest(path, doc)
            with self.assertRaisesRegex(host.ManifestError, "undeclared.*resource"):
                host.load_manifest(path)


class ResourceInputHostRedTests(unittest.TestCase):
    def _binding(self, path: Path):
        cls = getattr(host, "PreparedResourceInput", None)
        self.assertIsNotNone(cls, "RED: host must expose PreparedResourceInput")
        return cls(
            name="parent",
            resource_id="cuc",
            version="0.2.8",
            source_revision=IMMUTABLE_REVISION,
            path=path,
        )

    def test_render_args_substitutes_declared_resource_path(self):
        rendered = host._render_args(
            ["--parent", "{resource:parent}"],
            source="/input",
            output="/output",
            resource_paths={"parent": "/resources/parent"},
        )
        self.assertEqual(rendered, ["--parent", "/resources/parent"])

    def test_linux_sandbox_read_only_mounts_parent_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "plugin"
            source = root / "source"
            parent = root / "parent"
            output = root / "stage" / "output"
            work = root / "work"
            for directory in (plugin, source, parent, output.parent, work):
                directory.mkdir(parents=True, exist_ok=True)
            binding = self._binding(parent)
            with mock.patch.object(host, "_sandbox_backend_preflight", return_value=("bubblewrap", "/usr/bin/bwrap")):
                command, backend = host.build_sandbox_command(
                    plugin_root=plugin,
                    source=source,
                    output=output,
                    work_dir=work,
                    module="fixture_converter",
                    args=["{source}", "{output}", "{resource:parent}"],
                    resource_inputs=(binding,),
                )
        self.assertEqual(backend, "bubblewrap")
        rendered = "\n".join(command)
        self.assertIn(str(parent.resolve()), rendered)
        self.assertIn("/resources/parent", command)
        parent_index = command.index(str(parent.resolve()))
        self.assertEqual(command[parent_index - 1], "--ro-bind")
        self.assertIn("/input", command)

    def test_materialize_records_logical_resource_identity_without_absolute_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "plugin"
            source = root / "source"
            parent = root / "parent"
            output = root / "artifact"
            for directory in (plugin, source, parent):
                directory.mkdir()
            (source / "source.txt").write_text("synthetic", encoding="utf-8")
            (parent / "otype.tf").write_text("synthetic parent", encoding="utf-8")
            (plugin / "fixture_converter.py").write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "source, output, parent = map(Path, sys.argv[1:4])\n"
                "assert (source / 'source.txt').is_file()\n"
                "assert (parent / 'otype.tf').is_file()\n"
                "(output / 'feature.tf').write_text('feature', encoding='utf-8')\n",
                encoding="utf-8",
            )
            manifest_path = plugin / "agora.materializer.json"
            doc = _manifest()
            doc["materializers"][0]["execution"]["args"] = [
                "{source}", "{output}", "{resource:parent}"
            ]
            _write_manifest(manifest_path, doc)
            binding = self._binding(parent)
            result = host.materialize(
                manifest_path=manifest_path,
                materializer_id="example-to-tf",
                source=source,
                output=output,
                sandbox="off",
                resource_inputs=(binding,),
            )
            provenance = json.loads(
                (result / "agora-materialization.json").read_text(encoding="utf-8")
            )
        self.assertEqual(
            provenance["resource_inputs"],
            [
                {
                    "name": "parent",
                    "resource": "cuc",
                    "version": "0.2.8",
                    "source_revision": IMMUTABLE_REVISION,
                }
            ],
        )
        self.assertNotIn(str(parent.resolve()), json.dumps(provenance, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
