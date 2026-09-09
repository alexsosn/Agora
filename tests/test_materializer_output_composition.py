from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.agora_materialize import ManifestError, load_manifest, materialize


COMPOSITION = {
    "kind": "feature-module",
    "parent": "cuc",
    "compatibility": {"parent_versions": ["0.2.8"]},
}


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
                        "type": "user-local",
                        "path_type": "directory",
                        "prompt": "Select the source data directory",
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


class MaterializerOutputCompositionManifestTests(unittest.TestCase):
    def load(self, doc: dict) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agora.materializer.json"
            _write_manifest(path, doc)
            return load_manifest(path)

    def test_feature_module_composition_is_accepted(self):
        doc = _manifest()
        doc["materializers"][0]["output"]["composition"] = copy.deepcopy(COMPOSITION)
        loaded = self.load(doc)
        self.assertEqual(
            loaded["materializers"][0]["output"]["composition"],
            COMPOSITION,
        )

    def test_standalone_output_remains_valid_without_composition(self):
        loaded = self.load(_manifest())
        self.assertNotIn("composition", loaded["materializers"][0]["output"])

    def test_partial_feature_module_composition_is_rejected(self):
        for missing in ("kind", "parent", "compatibility"):
            with self.subTest(missing=missing):
                doc = _manifest()
                composition = copy.deepcopy(COMPOSITION)
                del composition[missing]
                doc["materializers"][0]["output"]["composition"] = composition
                with self.assertRaisesRegex(ManifestError, "violates schema"):
                    self.load(doc)

    def test_non_feature_module_composition_kind_is_rejected(self):
        doc = _manifest()
        composition = copy.deepcopy(COMPOSITION)
        composition["kind"] = "corpus"
        doc["materializers"][0]["output"]["composition"] = composition
        with self.assertRaisesRegex(ManifestError, "violates schema"):
            self.load(doc)

    def test_feature_module_composition_requires_text_fabric_output(self):
        doc = _manifest()
        doc["materializers"][0]["output"]["format"] = "csv"
        doc["materializers"][0]["output"]["composition"] = copy.deepcopy(COMPOSITION)
        with self.assertRaisesRegex(ManifestError, "violates schema"):
            self.load(doc)

    def test_empty_or_duplicate_parent_versions_are_rejected(self):
        for versions in ([], ["0.2.8", "0.2.8"]):
            with self.subTest(versions=versions):
                doc = _manifest()
                composition = copy.deepcopy(COMPOSITION)
                composition["compatibility"]["parent_versions"] = versions
                doc["materializers"][0]["output"]["composition"] = composition
                with self.assertRaisesRegex(ManifestError, "violates schema"):
                    self.load(doc)


class MaterializerOutputCompositionReceiptTests(unittest.TestCase):
    def test_validated_composition_is_preserved_in_agora_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "plugin"
            source = root / "source"
            output = root / "artifact"
            plugin.mkdir()
            source.mkdir()
            (source / "book.xml").write_text("<book/>", encoding="utf-8")
            (plugin / "fixture_converter.py").write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "source = Path(sys.argv[1])\n"
                "output = Path(sys.argv[2])\n"
                "assert (source / 'book.xml').is_file()\n"
                "(output / 'burns_annotations.tf').write_text('feature', encoding='utf-8')\n",
                encoding="utf-8",
            )

            doc = _manifest()
            materializer = doc["materializers"][0]
            materializer["execution"] = {
                "type": "python-module",
                "module": "fixture_converter",
                "args": ["{source}", "{output}"],
                "network": "deny",
            }
            materializer["output"] = {
                "format": "text-fabric",
                "required_paths": ["burns_annotations.tf"],
                "composition": copy.deepcopy(COMPOSITION),
            }
            manifest_path = plugin / "agora.materializer.json"
            _write_manifest(manifest_path, doc)

            materialize(
                manifest_path=manifest_path,
                materializer_id="example-to-tf",
                source=source,
                output=output,
                sandbox="off",
            )
            provenance = json.loads(
                (output / "agora-materialization.json").read_text(encoding="utf-8")
            )

        self.assertEqual(provenance["output"]["format"], "text-fabric")
        self.assertEqual(provenance["output"]["composition"], COMPOSITION)


if __name__ == "__main__":
    unittest.main()
