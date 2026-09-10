from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from scripts import agora_materialize as host


COMPOSITION = {
    "kind": "feature-module",
    "parent": "cuc",
    "compatibility": {"parent_versions": ["0.2.8"]},
}
REVISION = "a" * 40


def _manifest(*, composition: bool = False, parent_arg: bool = False) -> dict:
    output: dict[str, object] = {
        "format": "text-fabric",
        "required_paths": ["burns_annotations.tf"],
    }
    if composition:
        output["composition"] = copy.deepcopy(COMPOSITION)
    args = ["convert", "{source}", "--output", "{output}"]
    if parent_arg:
        args.extend(["--cuc", "{parent}"])
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
                    "args": args,
                    "network": "deny",
                },
                "output": output,
            }
        ],
    }


def _load(doc: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "agora.materializer.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        return host.load_manifest(path)


class ParentPlaceholderManifestTests(unittest.TestCase):
    def test_feature_module_may_use_parent_placeholder(self):
        loaded = _load(_manifest(composition=True, parent_arg=True))
        self.assertIn(
            "{parent}",
            loaded["materializers"][0]["execution"]["args"],
        )

    def test_standalone_materializer_may_not_use_parent_placeholder(self):
        with self.assertRaisesRegex(host.ManifestError, "parent|schema|composition"):
            _load(_manifest(composition=False, parent_arg=True))

    def test_feature_module_need_not_use_parent_placeholder(self):
        loaded = _load(_manifest(composition=True, parent_arg=False))
        self.assertNotIn(
            "{parent}",
            loaded["materializers"][0]["execution"]["args"],
        )


class ParentResourceBindingTests(unittest.TestCase):
    def binding(self, parent: Path, **overrides):
        values = {
            "resource_id": "cuc",
            "version": "0.2.8",
            "source_revision": REVISION,
            "path": parent,
        }
        values.update(overrides)
        return host.ParentResourceBinding(**values)

    def test_matching_binding_is_immutable_and_resolves_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "cuc"
            parent.mkdir()
            binding = self.binding(parent)
            validated = host.validate_parent_binding(
                _manifest(composition=True, parent_arg=True)["materializers"][0],
                binding,
            )
            self.assertEqual(validated.path, parent.resolve())
            with self.assertRaises(FrozenInstanceError):
                validated.version = "other"  # type: ignore[misc]

    def test_resource_id_must_match_composition_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "cuc"
            parent.mkdir()
            with self.assertRaisesRegex(ValueError, "resource|parent"):
                host.validate_parent_binding(
                    _manifest(composition=True, parent_arg=True)["materializers"][0],
                    self.binding(parent, resource_id="bhsa"),
                )

    def test_version_is_an_opaque_exact_membership_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "cuc"
            parent.mkdir()
            with self.assertRaisesRegex(ValueError, "version|compatib"):
                host.validate_parent_binding(
                    _manifest(composition=True, parent_arg=True)["materializers"][0],
                    self.binding(parent, version="0.2.8+local"),
                )

    def test_revision_must_be_full_immutable_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "cuc"
            parent.mkdir()
            for revision in ("main", "v0.2.8", "deadbeef", "g" * 40):
                with self.subTest(revision=revision):
                    with self.assertRaisesRegex(ValueError, "revision|immutable"):
                        host.validate_parent_binding(
                            _manifest(composition=True, parent_arg=True)["materializers"][0],
                            self.binding(parent, source_revision=revision),
                        )

    def test_parent_path_must_exist_as_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing"
            with self.assertRaisesRegex(ValueError, "parent|directory|path"):
                host.validate_parent_binding(
                    _manifest(composition=True, parent_arg=True)["materializers"][0],
                    self.binding(missing),
                )

    def test_binding_is_rejected_for_standalone_materializer(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "cuc"
            parent.mkdir()
            with self.assertRaisesRegex(ValueError, "standalone|composition|parent"):
                host.validate_parent_binding(
                    _manifest(composition=False, parent_arg=False)["materializers"][0],
                    self.binding(parent),
                )


if __name__ == "__main__":
    unittest.main()
