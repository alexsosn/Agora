from __future__ import annotations

import copy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog
from agora_context_fabric.service import ContextFabricService
import scripts.validate_registry as registry_validator
from scripts.validate_registry import schema_errors


SCHEMA = ROOT / "registry/schema/resources.schema.json"
MEASUREMENT_REVISION = "bf5fb918d513fcf859bc925a10922e841b777b98"
EVIDENCE = "https://github.com/alexsosn/Agora/issues/38#issuecomment-5536924435"


def _registry_resources() -> dict:
    return yaml.safe_load((ROOT / "registry/resources.yaml").read_text(encoding="utf-8"))


def _resource(resource_id: str) -> dict:
    return copy.deepcopy(
        next(item for item in _registry_resources()["resources"] if item["id"] == resource_id)
    )


def _feature_module(resource_id: str = "bhsa-phono") -> dict:
    doc = yaml.safe_load((ROOT / "registry/feature-modules.yaml").read_text(encoding="utf-8"))
    return copy.deepcopy(next(item for item in doc["resources"] if item["id"] == resource_id))


def _measurement() -> dict:
    return {
        "checked_at": "2026-09-04",
        "agora_revision": MEASUREMENT_REVISION,
        "environment": (
            "macOS 24.6.0 x86_64; Python 3.13; "
            "cfabric-mcp 0.1.7; context-fabric 0.5.7"
        ),
        "evidence": EVIDENCE,
    }


def _corpus_cost() -> dict:
    return {
        "scope": "resource",
        "source_size_mb": 3.1,
        "compiled_size_mb": 20,
        "first_load_seconds": 30,
        "warm_load_seconds": 1.5,
        "measurement": _measurement(),
    }


def _collection_cost() -> dict:
    return {
        "scope": "collection-member",
        "typical_member_cache_mb": 10,
        "typical_member_first_load_seconds": {"min": 20, "max": 33},
        "discovery_seconds": 5.2,
        "discovery_cache_mb": 1.7,
        "measurement": _measurement(),
    }


class LoadCostSchemaTests(unittest.TestCase):
    def _schema_errors_for(self, resource: dict) -> list[str]:
        return schema_errors(
            {"schema_version": 1, "resources": [resource]},
            SCHEMA,
            "resources.yaml",
        )

    def test_existing_resource_without_load_cost_remains_valid(self):
        resource = _resource("cuc")
        resource.pop("load_cost", None)
        self.assertEqual(self._schema_errors_for(resource), [])

    def test_corpus_resource_scope_is_accepted(self):
        resource = _resource("cuc")
        resource["load_cost"] = _corpus_cost()
        self.assertEqual(self._schema_errors_for(resource), [])

    def test_collection_member_scope_is_accepted(self):
        resource = _resource("greek_literature")
        resource["load_cost"] = _collection_cost()
        self.assertEqual(self._schema_errors_for(resource), [])

    def test_feature_module_load_cost_is_rejected(self):
        resource = _feature_module()
        resource["load_cost"] = _corpus_cost()
        errors = self._schema_errors_for(resource)
        self.assertTrue(errors, "feature modules must not advertise standalone load cost")

    def test_negative_observation_is_rejected(self):
        resource = _resource("cuc")
        cost = _corpus_cost()
        cost["compiled_size_mb"] = -1
        resource["load_cost"] = cost
        errors = self._schema_errors_for(resource)
        self.assertTrue(
            any(
                "compiled_size_mb" in error
                and ("minimum of 0" in error or "greater than or equal to 0" in error)
                for error in errors
            ),
            errors,
        )

    def test_measurement_provenance_is_required(self):
        resource = _resource("cuc")
        cost = _corpus_cost()
        del cost["measurement"]
        resource["load_cost"] = cost
        errors = self._schema_errors_for(resource)
        self.assertTrue(any("measurement" in error and "required" in error for error in errors), errors)

    def test_scope_specific_fields_do_not_cross(self):
        corpus = _resource("cuc")
        bad_corpus = _corpus_cost()
        bad_corpus["discovery_seconds"] = 1
        corpus["load_cost"] = bad_corpus
        corpus_errors = self._schema_errors_for(corpus)

        collection = _resource("greek_literature")
        bad_collection = _collection_cost()
        bad_collection["compiled_size_mb"] = 10
        collection["load_cost"] = bad_collection
        collection_errors = self._schema_errors_for(collection)

        self.assertTrue(corpus_errors, "collection-only field must be rejected for resource scope")
        self.assertTrue(collection_errors, "resource-only field must be rejected for member scope")


class LoadCostSemanticTests(unittest.TestCase):
    def _validate_resource_mutation(self, mutate) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            shutil.copytree(ROOT / "registry", tmp_root / "registry")
            path = tmp_root / "registry/resources.yaml"
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            mutate(doc)
            path.write_text(
                yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            with (
                mock.patch.object(registry_validator, "validate_verification_checks", return_value=[]),
                mock.patch.object(registry_validator, "validate_candidate_research", return_value=[]),
                mock.patch.object(registry_validator, "validate_runtime_environments", return_value=[]),
            ):
                return registry_validator.validate_registry(tmp_root)

    def test_corpus_cannot_claim_collection_member_scope(self):
        def mutate(doc):
            item = next(value for value in doc["resources"] if value["id"] == "cuc")
            item["load_cost"] = _collection_cost()

        errors = self._validate_resource_mutation(mutate)
        self.assertTrue(
            any("resource cuc.load_cost.scope" in error and "must be 'resource'" in error for error in errors),
            errors,
        )

    def test_collection_cannot_claim_resource_scope(self):
        def mutate(doc):
            item = next(
                value for value in doc["resources"] if value["id"] == "greek_literature"
            )
            item["load_cost"] = _corpus_cost()

        errors = self._validate_resource_mutation(mutate)
        self.assertTrue(
            any(
                "resource greek_literature.load_cost.scope" in error
                and "must be 'collection-member'" in error
                for error in errors
            ),
            errors,
        )

    def test_member_range_must_be_ordered(self):
        def mutate(doc):
            item = next(
                value for value in doc["resources"] if value["id"] == "greek_literature"
            )
            cost = _collection_cost()
            cost["typical_member_first_load_seconds"] = {"min": 34, "max": 20}
            item["load_cost"] = cost

        errors = self._validate_resource_mutation(mutate)
        self.assertTrue(
            any("typical_member_first_load_seconds" in error and "min" in error for error in errors),
            errors,
        )


class LoadCostProjectionTests(unittest.TestCase):
    def test_catalog_preserves_load_cost_losslessly(self):
        item = _resource("cuc")
        item["load_cost"] = _corpus_cost()
        spec = Catalog._resources_from_document(
            {"schema_version": 1, "resources": [item]}
        )[0]
        self.assertEqual(spec.load_cost, item["load_cost"])

    def test_resource_description_exposes_exact_mapping(self):
        item = _resource("cuc")
        item["load_cost"] = _corpus_cost()
        spec = Catalog._resources_from_document(
            {"schema_version": 1, "resources": [item]}
        )[0]
        service = ContextFabricService(Catalog([spec]), object(), object())
        self.assertEqual(service._resource_dict(spec)["load_cost"], item["load_cost"])

    def test_unmeasured_resource_reports_explicit_null(self):
        item = _resource("dss")
        spec = Catalog._resources_from_document(
            {"schema_version": 1, "resources": [item]}
        )[0]
        service = ContextFabricService(Catalog([spec]), object(), object())
        self.assertIsNone(service._resource_dict(spec)["load_cost"])


class CanonicalLoadCostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = {
            item["id"]: item for item in _registry_resources()["resources"]
        }
        bundled_doc = yaml.safe_load(
            (ROOT / "plugins/context-fabric/resources/catalog.yaml").read_text(
                encoding="utf-8"
            )
        )
        cls.bundled = {item["id"]: item for item in bundled_doc["resources"]}

    def test_only_measured_resources_are_seeded(self):
        measured = {
            resource_id
            for resource_id, resource in self.canonical.items()
            if "load_cost" in resource
        }
        self.assertEqual(measured, {"bhsa", "cuc", "TLHdig-TF", "greek_literature"})

    def test_seeded_corpora_have_resource_scope_and_provenance(self):
        for resource_id in ("bhsa", "cuc", "TLHdig-TF"):
            with self.subTest(resource_id=resource_id):
                cost = self.canonical[resource_id]["load_cost"]
                self.assertEqual(cost["scope"], "resource")
                self.assertEqual(cost["measurement"]["agora_revision"], MEASUREMENT_REVISION)
                self.assertEqual(cost["measurement"]["evidence"], EVIDENCE)

    def test_greek_literature_uses_member_scope_and_measured_range(self):
        cost = self.canonical["greek_literature"]["load_cost"]
        self.assertEqual(cost["scope"], "collection-member")
        self.assertEqual(cost["typical_member_first_load_seconds"], {"min": 20, "max": 33})

    def test_bhsa_discloses_module_combination_boundary(self):
        notes = self.canonical["bhsa"]["load_cost"].get("notes", "").lower()
        self.assertIn("module", notes)
        self.assertIn("#46", notes)

    def test_bundled_catalog_preserves_seeded_load_cost_exactly(self):
        for resource_id in ("bhsa", "cuc", "TLHdig-TF", "greek_literature"):
            with self.subTest(resource_id=resource_id):
                self.assertEqual(
                    self.bundled[resource_id]["load_cost"],
                    self.canonical[resource_id]["load_cost"],
                )


if __name__ == "__main__":
    unittest.main()
