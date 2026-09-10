from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import agora_materialize as host


class ParentAliasReviewTests(unittest.TestCase):
    def test_source_and_parent_cannot_alias_same_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "plugin"
            shared = root / "shared-input"
            output = root / "artifact"
            plugin.mkdir()
            shared.mkdir()
            (shared / "book.xml").write_text("source-and-parent", encoding="utf-8")

            manifest_doc = {
                "schema_version": 1,
                "plugin": {
                    "id": "example-converter",
                    "name": "Example converter",
                    "version": "1.0.0",
                },
                "materializers": [
                    {
                        "id": "example-to-feature-module",
                        "description": "Synthetic parent alias regression.",
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
                            "module": "fixture_parent_converter",
                            "args": ["{source}", "{parent}", "{output}"],
                            "network": "deny",
                        },
                        "output": {
                            "format": "text-fabric",
                            "required_paths": ["annotations.tf"],
                            "composition": {
                                "kind": "feature-module",
                                "parent": "cuc",
                                "compatibility": {"parent_versions": ["0.2.8"]},
                            },
                        },
                    }
                ],
            }
            manifest = plugin / "agora.materializer.json"
            manifest.write_text(json.dumps(manifest_doc), encoding="utf-8")
            binding = host.ParentResourceBinding(
                resource_id="cuc",
                version="0.2.8",
                source_revision="a" * 40,
                path=shared,
            )

            with patch.object(host.subprocess, "run") as run:
                with self.assertRaisesRegex(ValueError, "source|parent|overlap"):
                    host.materialize(
                        manifest_path=manifest,
                        materializer_id="example-to-feature-module",
                        source=shared,
                        output=output,
                        sandbox="off",
                        parent=binding,
                    )
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
