from __future__ import annotations

import copy
import unittest

import yaml

from scripts.validate_registry import ROOT, schema_errors


MEASUREMENT = {
    "checked_at": "2026-09-04",
    "agora_revision": "bf5fb918d513fcf859bc925a10922e841b777b98",
    "environment": "test measurement environment",
    "evidence": "https://github.com/alexsosn/Agora/issues/38#issuecomment-5536924435",
}


def _resource(resource_id: str) -> dict:
    document = yaml.safe_load(
        (ROOT / "registry/resources.yaml").read_text(encoding="utf-8")
    )
    return copy.deepcopy(
        next(item for item in document["resources"] if item["id"] == resource_id)
    )


class LoadCostSchemaRedTests(unittest.TestCase):
    def test_feature_module_cannot_declare_standalone_load_cost(self):
        document = yaml.safe_load(
            (ROOT / "registry/feature-modules.yaml").read_text(encoding="utf-8")
        )
        module = copy.deepcopy(document["resources"][0])
        module["load_cost"] = {
            "scope": "resource",
            "source_size_mb": 1,
            "measurement": dict(MEASUREMENT),
        }
        errors = schema_errors(
            {"schema_version": 1, "resources": [module]},
            ROOT / "registry/schema/resources.schema.json",
            "feature-modules.yaml",
        )
        self.assertTrue(
            any("load_cost" in error for error in errors),
            "feature-module load_cost must be rejected rather than interpreted as a corpus cost",
        )

    def test_resource_scope_requires_an_observation(self):
        resource = _resource("cuc")
        resource["load_cost"] = {
            "scope": "resource",
            "measurement": dict(MEASUREMENT),
        }
        errors = schema_errors(
            {"schema_version": 1, "resources": [resource]},
            ROOT / "registry/schema/resources.schema.json",
            "resources.yaml",
        )
        self.assertTrue(errors, "resource load_cost cannot contain provenance without an observation")

    def test_collection_member_scope_requires_an_observation(self):
        resource = _resource("greek_literature")
        resource["load_cost"] = {
            "scope": "collection-member",
            "measurement": dict(MEASUREMENT),
        }
        errors = schema_errors(
            {"schema_version": 1, "resources": [resource]},
            ROOT / "registry/schema/resources.schema.json",
            "resources.yaml",
        )
        self.assertTrue(
            errors,
            "collection-member load_cost cannot contain provenance without an observation",
        )


if __name__ == "__main__":
    unittest.main()
