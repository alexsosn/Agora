"""RED 1 contracts for #135: declaring a trusted parent input in a manifest.

These cover only the manifest contract and backward compatibility. Sandbox
mounting, resolution, trust and orchestration are later cycles.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator

from scripts.agora_materialize import ManifestError, load_manifest, materialize

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


def _schema_faults(document: dict) -> list[tuple[str, str]]:
    """Where the schema objected and which keyword objected.

    `assertTrue(_schema_errors(...))` only says "something, somewhere" -- it
    stays green when the member under test is removed from the schema entirely,
    because `additionalProperties: false` then rejects the document for an
    unrelated reason.
    """
    return [(error.json_path, error.validator) for error in _schema_errors(document)]


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
        self.assertEqual(
            _schema_faults(document), [("$.materializers[0].parent_input", "additionalProperties")]
        )

    def test_parent_input_requires_resource_versions_and_paths(self):
        for missing in ("resource", "parent_versions", "required_paths"):
            with self.subTest(missing=missing):
                parent_input = _parent_input()
                del parent_input[missing]
                document = _manifest(
                    _materializer(parent_input=parent_input, args=PARENT_ARGS)
                )
                self.assertEqual(_schema_faults(document), [("$.materializers[0].parent_input", "required")])

    def test_parent_input_must_be_an_object(self):
        """Without `type: object` the semantic checks index a string and raise
        `TypeError` instead of a `ManifestError`.
        """
        document = _manifest(_materializer(args=PARENT_ARGS))
        document["materializers"][0]["parent_input"] = "cuc"
        self.assertEqual(
            _schema_faults(document), [("$.materializers[0].parent_input", "type")]
        )

    def test_parent_input_rejects_an_empty_version_list(self):
        document = _manifest(
            _materializer(parent_input=_parent_input(parent_versions=[]), args=PARENT_ARGS)
        )
        self.assertEqual(
            _schema_faults(document), [("$.materializers[0].parent_input.parent_versions", "minItems")]
        )

    def test_parent_input_rejects_an_escaping_required_path(self):
        document = _manifest(
            _materializer(
                parent_input=_parent_input(required_paths=["../otype.tf"]),
                args=PARENT_ARGS,
            )
        )
        self.assertEqual(
            _schema_faults(document), [("$.materializers[0].parent_input.required_paths[0]", "pattern")]
        )

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
        self.assertEqual(
            _schema_faults(document),
            [("$.materializers[0].execution.args[3]", "pattern")],
        )


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

    def test_parent_version_placeholder_without_parent_input_is_refused(self):
        """`{parent_revision}` was pinned and `{parent_version}` was not, so it
        could be dropped from `PARENT_PLACEHOLDERS` with every test green.
        """
        document = _manifest(
            _materializer(args=["module", "{source}", "{parent_version}", "{output}"])
        )
        with self.assertRaisesRegex(ManifestError, "parent_input"):
            _load(document)

    def test_an_embedded_parent_placeholder_counts_as_passing_the_parent(self):
        """The check is a substring test on purpose: `--cuc={parent}` is a
        legitimate, schema-valid argument and must satisfy it.
        """
        manifest = _load(
            _manifest(
                _materializer(
                    parent_input=_parent_input(),
                    args=["module", "{source}", "--cuc={parent}", "--output", "{output}"],
                )
            )
        )
        self.assertEqual(manifest["materializers"][0]["parent_input"]["resource"], "cuc")

    def test_required_paths_reject_a_separator_the_schema_does_not_see(self):
        """`safeRelativePath` only recognises `/`, so a backslash traversal
        produces no schema error at all and only `_safe_relative` rejects it.
        """
        parent_input = _parent_input(required_paths=["..\\..\\etc\\passwd"])
        document = _manifest(_materializer(parent_input=parent_input, args=PARENT_ARGS))
        self.assertEqual(_schema_faults(document), [])
        with self.assertRaisesRegex(ManifestError, "must stay inside"):
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


class ParentInputExecutionTests(unittest.TestCase):
    """A declared parent input must be refused before any side effect.

    `_render_args` substitutes only `{source}`, `{output}` and
    `{source_revision}`. Until the mounting cycle lands, a manifest declaring a
    parent therefore validated, installed, acquired its source and created a
    staging directory, and only then died on the leftover `{parent}` -- telling
    the user their placeholder was invalid moments after validation accepted it.

    The manifest contract itself stays valid and declarable: this is a limit of
    this host, not of the manifest, so it is reported as one.
    """

    def _manifest_file(self, document: dict, directory: Path) -> Path:
        path = directory / "agora.materializer.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    @mock.patch("scripts.agora_materialize.acquire_source")
    def test_a_declared_parent_input_is_refused_before_acquisition(self, acquire_source):
        document = _manifest(_materializer(parent_input=_parent_input(), args=PARENT_ARGS))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = self._manifest_file(document, root)
            source = root / "source" / "sheets"
            source.mkdir(parents=True)
            (source / "one.csv").write_text("a,b\n", encoding="utf-8")
            output = root / "out"
            with self.assertRaises(ManifestError) as caught:
                materialize(
                    manifest_path=manifest_path,
                    materializer_id="example-module",
                    output=output,
                    source=root / "source",
                    sandbox="off",
                )
            message = str(caught.exception)
            self.assertIn("cannot yet bind a parent input", message)
            self.assertIn("example-module", message)
            acquire_source.assert_not_called()
            self.assertFalse(output.exists())

    @mock.patch(
        "scripts.agora_materialize.acquire_source",
        side_effect=RuntimeError("single-source acquisition reached"),
    )
    def test_a_single_source_materializer_is_not_refused(self, acquire_source):
        """The parent guard must leave the existing single-source path unchanged."""
        document = _manifest(_materializer())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = self._manifest_file(document, root)
            source = root / "source" / "sheets"
            source.mkdir(parents=True)
            (source / "one.csv").write_text("a,b\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "single-source acquisition reached"):
                materialize(
                    manifest_path=manifest_path,
                    materializer_id="example-module",
                    output=root / "out",
                    source=root / "source",
                    sandbox="off",
                )
        acquire_source.assert_called_once()


if __name__ == "__main__":
    unittest.main()
