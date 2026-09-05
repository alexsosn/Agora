from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "context-fabric"
PLUGIN_SRC = PLUGIN_ROOT / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog
from scripts.generate_context_fabric_catalog import (
    build_catalog_document,
    build_collection_index_documents,
)
from scripts.validate_registry import validate_registry


REVISION = "a" * 40


class CollectionIndexRegistryTests(unittest.TestCase):
    def load_yaml(self, path: Path):
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def write_yaml(self, path: Path, document) -> None:
        path.write_text(
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=1000),
            encoding="utf-8",
        )

    def make_root(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        shutil.copytree(ROOT / "registry", root / "registry")
        workflows = root / ".github" / "workflows"
        workflows.parent.mkdir(parents=True)
        shutil.copytree(ROOT / ".github" / "workflows", workflows)
        (root / "tests").mkdir()
        shutil.copy2(ROOT / "tests" / "test_generation.py", root / "tests" / "test_generation.py")
        return root

    def make_complete_bible_index(self, root: Path, *, evidence: str | None = None) -> None:
        resources = self.load_yaml(root / "registry" / "resources.yaml")
        bible = next(item for item in resources["resources"] if item["id"] == "bible")
        bible["collection"]["discovery"] = "indexed"
        self.write_yaml(root / "registry" / "resources.yaml", resources)

        verification = {"status": "community"}
        if evidence is not None:
            verification["evidence"] = [{"check_id": evidence}]
        index = {
            "schema_version": 1,
            "collection_id": "bible",
            "source_revision": REVISION,
            "index_status": "complete",
            "members": [
                {
                    "id": "fixture-12345678",
                    "path": "old_testament/Fixture",
                    "tf_path": "old_testament/Fixture/tf/1.0",
                    "languages": ["greek"],
                    "canonical_id": "urn:cts:greekLit:fixture",
                    "edition": "Fixture edition",
                    "verification": verification,
                }
            ],
        }
        self.write_yaml(root / "registry" / "collections" / "bible.yaml", index)

    def test_schema_requires_revision_and_nonempty_members_for_complete_index(self):
        schema = json.loads(
            (ROOT / "registry" / "schema" / "collection-index.schema.json").read_text(
                encoding="utf-8"
            )
        )
        rendered = json.dumps(schema)
        self.assertIn("source_revision", schema["properties"])
        self.assertIn("^[0-9a-fA-F]{40}$", rendered)
        self.assertIn('"const": "complete"', rendered)
        self.assertIn('"minItems": 1', rendered)

    def test_member_schema_carries_tf_path_edition_and_verification_evidence(self):
        schema = json.loads(
            (ROOT / "registry" / "schema" / "collection-index.schema.json").read_text(
                encoding="utf-8"
            )
        )
        member = schema["properties"]["members"]["items"]
        self.assertIn("tf_path", member["required"])
        self.assertIn("edition", member["properties"])
        verification = member["properties"]["verification"]
        self.assertIn("evidence", verification["properties"])
        evidence_item = verification["properties"]["evidence"]["items"]
        self.assertEqual(evidence_item["required"], ["check_id"])

    def test_registry_accepts_complete_revision_bound_index(self):
        root = self.make_root()
        self.make_complete_bible_index(root)
        errors = validate_registry(root)
        self.assertFalse(
            any("resource bible" in error or "collections/bible.yaml" in error for error in errors),
            errors,
        )

    def test_member_verification_evidence_must_reference_existing_check(self):
        root = self.make_root()
        self.make_complete_bible_index(root, evidence="member-live/does-not-exist")
        errors = validate_registry(root)
        self.assertTrue(
            any(
                "resource bible.member[fixture-12345678].verification.evidence" in error
                and "missing verification check" in error
                for error in errors
            ),
            errors,
        )

    def test_installed_catalog_rewrites_only_collection_index_location(self):
        root = self.make_root()
        self.make_complete_bible_index(root)
        registry = self.load_yaml(root / "registry" / "resources.yaml")
        source = copy.deepcopy(next(item for item in registry["resources"] if item["id"] == "bible"))
        generated = build_catalog_document(root)
        installed = next(item for item in generated["resources"] if item["id"] == "bible")

        self.assertEqual(
            installed["collection"]["member_index"],
            "resources/collections/bible.yaml",
        )
        installed = copy.deepcopy(installed)
        installed["collection"]["member_index"] = source["collection"]["member_index"]
        self.assertEqual(installed, source)

    def test_installed_collection_indexes_are_generated_from_canonical_registry(self):
        root = self.make_root()
        self.make_complete_bible_index(root)
        documents = build_collection_index_documents(root)
        self.assertIn(Path("plugins/context-fabric/resources/collections/bible.yaml"), documents)
        self.assertEqual(
            documents[Path("plugins/context-fabric/resources/collections/bible.yaml")],
            self.load_yaml(root / "registry" / "collections" / "bible.yaml"),
        )

    def test_catalog_resolves_plugin_root_relative_member_index_path(self):
        resource = Catalog.from_plugin_root(PLUGIN_ROOT).get("bible")
        self.assertIsNotNone(resource.member_index_path)
        self.assertEqual(
            resource.member_index_path,
            PLUGIN_ROOT / "resources" / "collections" / "bible.yaml",
        )


if __name__ == "__main__":
    unittest.main()
