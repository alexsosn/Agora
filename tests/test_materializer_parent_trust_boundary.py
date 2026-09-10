from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import agora_materialize as host


REVISION = "a" * 40
COMPOSITION = {
    "kind": "feature-module",
    "parent": "cuc",
    "compatibility": {"parent_versions": ["0.2.8"]},
}


def _fixture(root: Path, topology: str):
    plugin = root / "plugin"
    plugin.mkdir()

    if topology == "equal":
        source = root / "shared"
        parent = source
        source.mkdir()
    elif topology == "source-inside-parent":
        parent = root / "parent"
        source = parent / "source"
        source.mkdir(parents=True)
    elif topology == "parent-inside-source":
        source = root / "source"
        parent = source / "parent"
        parent.mkdir(parents=True)
    elif topology == "disjoint":
        source = root / "source"
        parent = root / "parent"
        source.mkdir()
        parent.mkdir()
    else:  # pragma: no cover - test helper contract
        raise AssertionError(topology)

    (source / "book.xml").write_text("<book/>", encoding="utf-8")
    doc = {
        "schema_version": 1,
        "plugin": {
            "id": "fixture-parent",
            "name": "Parent trust-boundary fixture",
            "version": "1.0.0",
        },
        "materializers": [
            {
                "id": "fixture-to-tf",
                "description": "Synthetic two-input fixture.",
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
                    "module": "fixture_converter",
                    "args": ["{source}", "{parent}", "{output}"],
                    "network": "deny",
                },
                "output": {
                    "format": "text-fabric",
                    "required_paths": ["burns_annotations.tf"],
                    "composition": COMPOSITION,
                },
            }
        ],
    }
    manifest = plugin / "agora.materializer.json"
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    binding = host.ParentResourceBinding(
        resource_id="cuc",
        version="0.2.8",
        source_revision=REVISION,
        path=parent,
    )
    return manifest, source, binding, root / "artifact"


class ParentTrustBoundaryRedTests(unittest.TestCase):
    def test_overlapping_source_and_parent_fail_before_staging(self):
        for topology in ("equal", "source-inside-parent", "parent-inside-source"):
            with self.subTest(topology=topology), tempfile.TemporaryDirectory() as tmp:
                manifest, source, binding, output = _fixture(Path(tmp), topology)
                with patch.object(
                    host,
                    "_create_staging_output",
                    side_effect=AssertionError("staging reached for overlapping inputs"),
                ) as staging:
                    with self.assertRaisesRegex(ValueError, "source|parent|overlap"):
                        host.materialize(
                            manifest_path=manifest,
                            materializer_id="fixture-to-tf",
                            source=source,
                            output=output,
                            sandbox="off",
                            parent=binding,
                        )
                staging.assert_not_called()
                self.assertFalse(output.exists())

    def test_disjoint_source_and_parent_still_reach_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, source, binding, output = _fixture(Path(tmp), "disjoint")
            with patch.object(
                host,
                "_create_staging_output",
                side_effect=RuntimeError("disjoint staging control"),
            ) as staging:
                with self.assertRaisesRegex(RuntimeError, "disjoint staging control"):
                    host.materialize(
                        manifest_path=manifest,
                        materializer_id="fixture-to-tf",
                        source=source,
                        output=output,
                        sandbox="off",
                        parent=binding,
                    )
            staging.assert_called_once()
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
