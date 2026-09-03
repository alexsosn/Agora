from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.validate_registry import ROOT, validate_registry


class RegistryValidationTests(unittest.TestCase):
    def validate_mutation(self, relative_path: str, mutate):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            shutil.copytree(ROOT / "registry", tmp_root / "registry")
            path = tmp_root / relative_path
            with path.open("r", encoding="utf-8") as fh:
                doc = yaml.safe_load(fh)
            mutate(doc)
            with path.open("w", encoding="utf-8") as fh:
                yaml.safe_dump(doc, fh, sort_keys=False, allow_unicode=True)
            return validate_registry(tmp_root)

    def test_current_registry_is_valid(self):
        self.assertEqual(validate_registry(), [])

    def test_duplicate_plugin_id_is_rejected(self):
        def mutate(doc):
            doc["plugins"].append(copy.deepcopy(doc["plugins"][0]))

        errors = self.validate_mutation("registry/plugins.yaml", mutate)
        self.assertTrue(any("duplicate id 'context-fabric'" in error for error in errors), errors)

    def test_duplicate_resource_id_is_rejected(self):
        def mutate(doc):
            doc["resources"].append(copy.deepcopy(doc["resources"][0]))

        errors = self.validate_mutation("registry/resources.yaml", mutate)
        self.assertTrue(any("duplicate id 'bhsa'" in error for error in errors), errors)

    def test_invalid_provider_reference_is_rejected(self):
        def mutate(doc):
            doc["resources"][0]["provider"] = "missing-provider"

        errors = self.validate_mutation("registry/resources.yaml", mutate)
        self.assertTrue(any("references missing provider 'missing-provider'" in error for error in errors), errors)

    def test_unknown_language_is_rejected(self):
        def mutate(doc):
            doc["resources"][0]["languages"] = ["klingon"]

        errors = self.validate_mutation("registry/resources.yaml", mutate)
        self.assertTrue(any("unknown controlled-vocabulary value 'klingon'" in error for error in errors), errors)

    def test_malformed_plugin_id_is_rejected_by_schema(self):
        def mutate(doc):
            doc["plugins"][0]["id"] = "Bad Plugin ID"

        errors = self.validate_mutation("registry/plugins.yaml", mutate)
        self.assertTrue(any("does not match" in error and "Bad Plugin ID" in error for error in errors), errors)

    def test_v01_scope_is_fixed(self):
        with (ROOT / "registry/v0.1.yaml").open("r", encoding="utf-8") as fh:
            scope = yaml.safe_load(fh)
        self.assertEqual(set(scope["required_plugins"]), {"context-fabric", "perseus", "sefaria", "sedra"})
        self.assertEqual(len(scope["required_resources"]), 36)

    def test_every_v01_resource_has_integration_coverage_metadata(self):
        with (ROOT / "registry/v0.1.yaml").open("r", encoding="utf-8") as fh:
            scope = yaml.safe_load(fh)
        with (ROOT / "registry/resources.yaml").open("r", encoding="utf-8") as fh:
            resources = {item["id"]: item for item in yaml.safe_load(fh)["resources"]}

        for resource_id in scope["required_resources"]:
            resource = resources[resource_id]
            self.assertTrue(resource["upstream"]["repository"], resource_id)
            self.assertTrue(resource["acquisition"]["strategy"], resource_id)
            self.assertIn(resource["verification"]["status"], {"community", "verified", "experimental"})
            self.assertTrue(resource["source_snapshot"]["source"], resource_id)
            self.assertTrue(resource["source_snapshot"]["checked_at"], resource_id)

    def test_v01_collections_use_dynamic_git_tree_discovery(self):
        with (ROOT / "registry/resources.yaml").open("r", encoding="utf-8") as fh:
            resources = {item["id"]: item for item in yaml.safe_load(fh)["resources"]}
        for resource_id in ("bible", "patristics", "greek_literature", "translatin-manif"):
            resource = resources[resource_id]
            self.assertEqual(resource["kind"], "collection")
            self.assertEqual(resource["acquisition"]["strategy"], "collection")
            self.assertEqual(resource["collection"]["discovery"], "git-tree")
            self.assertTrue(resource["collection"]["lazy_members"])
            index_path = ROOT / resource["collection"]["member_index"]
            index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
            self.assertEqual(index["index_status"], "dynamic")
            self.assertEqual(index["members"], [])

    def test_git_tree_collection_rejects_static_or_pending_index(self):
        def mutate(doc):
            doc["index_status"] = "pending"

        errors = self.validate_mutation("registry/collections/bible.yaml", mutate)
        self.assertTrue(
            any("git-tree discovery requires collection index_status='dynamic'" in error for error in errors),
            errors,
        )

    def test_tlhdig_uses_community_integration_status(self):
        with (ROOT / "registry/resources.yaml").open("r", encoding="utf-8") as fh:
            resources = {item["id"]: item for item in yaml.safe_load(fh)["resources"]}
        self.assertEqual(resources["TLHdig-TF"]["verification"]["status"], "community")


if __name__ == "__main__":
    unittest.main()
