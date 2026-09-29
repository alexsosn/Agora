"""RED 1 contracts for #135: declaring a trusted parent input in a manifest.

These cover only the manifest contract and backward compatibility. Sandbox
mounting, resolution, trust and orchestration are later cycles.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts.agora_materialize import ManifestError, load_manifest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / "registry/schema/materializer-plugin.schema.json").read_text(encoding="utf-8")
)


def _parent_input(**overrides) -> dict:
    parent_input = {
        "resource": "cuc",
        "parent_versions": ["0.2.8"],
        "required_paths": ["otype.tf", "oslots.tf", "otext.tf"],
    }
    parent_input.update(overrides)
    return parent_input


def _materializer(
    *,
    parent_input: dict | None = None,
    args: list[str] | None = None,
    composition: dict | None = None,
) -> dict:
    materializer: dict = {
        "id": "example-module",
        "description": "Produce a feature module over a prepared parent corpus.",
        "acquisition": [
            {
                "type": "user-local",
                "path_type": "directory",
                "prompt": "Select the source directory",
            }
        ],
        "input": {
            "type": "directory",
            "required_globs": ["*/*.csv"],
            "allow_symlinks": False,
        },
        "execution": {
            "type": "python-module",
            "module": "example.cli",
            "args": args if args is not None else ["module", "{source}", "--output", "{output}"],
            "network": "deny",
        },
        "output": {
            "format": "text-fabric",
            "required_paths": ["example_feature.tf"],
        },
    }
    if parent_input is not None:
        materializer["parent_input"] = parent_input
    if composition is not None:
        materializer["output"]["composition"] = composition
    return materializer


def _manifest(materializer: dict) -> dict:
    return {
        "schema_version": 1,
        "plugin": {"id": "example-plugin", "name": "Example", "version": "1.0.0"},
        "materializers": [materializer],
    }


def _schema_errors(document: dict) -> list:
    return list(Draft202012Validator(SCHEMA).iter_errors(document))


def _load(document: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "agora.materializer.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return load_manifest(path)


PARENT_ARGS = [
    "module",
    "{source}",
    "--cuc",
    "{parent}",
    "--output",
    "{output}",
]


class ParentInputSchemaTests(unittest.TestCase):
    def test_single_source_materializer_remains_valid_without_a_parent(self):
        self.assertEqual(_schema_errors(_manifest(_materializer())), [])

    def test_well_formed_parent_input_is_accepted(self):
        document = _manifest(_materializer(parent_input=_parent_input(), args=PARENT_ARGS))
        self.assertEqual(_schema_errors(document), [])

    def test_parent_input_rejects_unknown_members(self):
        document = _manifest(
            _materializer(
                parent_input=_parent_input(writable=True),
                args=PARENT_ARGS,
            )
        )
        self.assertTrue(_schema_errors(document))

    def test_parent_input_requires_resource_versions_and_paths(self):
        for missing in ("resource", "parent_versions", "required_paths"):
            with self.subTest(missing=missing):
                parent_input = _parent_input()
                del parent_input[missing]
                document = _manifest(
                    _materializer(parent_input=parent_input, args=PARENT_ARGS)
                )
                self.assertTrue(_schema_errors(document))

    def test_parent_input_rejects_an_empty_version_list(self):
        document = _manifest(
            _materializer(parent_input=_parent_input(parent_versions=[]), args=PARENT_ARGS)
        )
        self.assertTrue(_schema_errors(document))

    def test_parent_input_rejects_an_escaping_required_path(self):
        document = _manifest(
            _materializer(
                parent_input=_parent_input(required_paths=["../otype.tf"]),
                args=PARENT_ARGS,
            )
        )
        self.assertTrue(_schema_errors(document))

    def test_parent_placeholders_are_permitted_execution_arguments(self):
        args = [
            "module",
            "{source}",
            "--cuc",
            "{parent}",
            "--cuc-revision",
            "{parent_revision}",
            "--cuc-version",
            "{parent_version}",
            "--output",
            "{output}",
        ]
        document = _manifest(_materializer(parent_input=_parent_input(), args=args))
        self.assertEqual(_schema_errors(document), [])

    def test_unknown_placeholders_remain_rejected(self):
        document = _manifest(
            _materializer(
                parent_input=_parent_input(),
                args=["module", "{source}", "{parent}", "{parent_secret}", "{output}"],
            )
        )
        self.assertTrue(_schema_errors(document))


class ParentInputSemanticsTests(unittest.TestCase):
    def test_single_source_manifest_still_loads(self):
        manifest = _load(_manifest(_materializer()))
        self.assertNotIn("parent_input", manifest["materializers"][0])

    def test_declared_parent_input_loads(self):
        manifest = _load(
            _manifest(_materializer(parent_input=_parent_input(), args=PARENT_ARGS))
        )
        self.assertEqual(manifest["materializers"][0]["parent_input"]["resource"], "cuc")

    def test_parent_placeholder_without_a_declared_parent_input_is_refused(self):
        document = _manifest(_materializer(args=PARENT_ARGS))
        with self.assertRaisesRegex(ManifestError, "parent_input"):
            _load(document)

    def test_parent_revision_placeholder_without_parent_input_is_refused(self):
        document = _manifest(
            _materializer(args=["module", "{source}", "{parent_revision}", "{output}"])
        )
        with self.assertRaisesRegex(ManifestError, "parent_input"):
            _load(document)

    def test_declared_parent_input_that_is_never_passed_is_refused(self):
        document = _manifest(_materializer(parent_input=_parent_input()))
        with self.assertRaisesRegex(ManifestError, r"\{parent\}"):
            _load(document)

    def test_composition_parent_must_agree_with_the_executed_parent(self):
        document = _manifest(
            _materializer(
                parent_input=_parent_input(),
                args=PARENT_ARGS,
                composition={
                    "kind": "feature-module",
                    "parent": "bhsa",
                    "compatibility": {"parent_versions": ["0.2.8"]},
                },
            )
        )
        # Asserting a distinctive message on purpose: a bare "parent" regex also
        # matches the schema violation raised while parent_input is unknown, so
        # the contract could never fail.
        with self.assertRaisesRegex(ManifestError, r"composition\.parent"):
            _load(document)

    def test_executed_parent_versions_must_be_covered_by_declared_compatibility(self):
        document = _manifest(
            _materializer(
                parent_input=_parent_input(parent_versions=["0.2.8", "0.2.7"]),
                args=PARENT_ARGS,
                composition={
                    "kind": "feature-module",
                    "parent": "cuc",
                    "compatibility": {"parent_versions": ["0.2.8"]},
                },
            )
        )
        with self.assertRaisesRegex(ManifestError, r"parent_input\.parent_versions"):
            _load(document)

    def test_agreeing_composition_and_parent_input_load_together(self):
        manifest = _load(
            _manifest(
                _materializer(
                    parent_input=_parent_input(),
                    args=PARENT_ARGS,
                    composition={
                        "kind": "feature-module",
                        "parent": "cuc",
                        "compatibility": {"parent_versions": ["0.2.8", "0.2.7"]},
                    },
                )
            )
        )
        spec = manifest["materializers"][0]
        self.assertEqual(spec["parent_input"]["parent_versions"], ["0.2.8"])
        self.assertEqual(spec["output"]["composition"]["parent"], "cuc")


if __name__ == "__main__":
    unittest.main()
