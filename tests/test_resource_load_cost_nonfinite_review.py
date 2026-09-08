from __future__ import annotations

import copy
import math
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_registry import schema_errors

SCHEMA = ROOT / "registry" / "schema" / "resources.schema.json"


def _resource(resource_id: str) -> dict:
    doc = yaml.safe_load((ROOT / "registry" / "resources.yaml").read_text(encoding="utf-8"))
    return copy.deepcopy(next(item for item in doc["resources"] if item["id"] == resource_id))


def _schema_errors(resource: dict) -> list[str]:
    return schema_errors(
        {"schema_version": 1, "resources": [resource]},
        SCHEMA,
        "resources.yaml",
    )


class LoadCostFiniteNumberReviewTests(unittest.TestCase):
    def test_non_finite_scalar_observations_are_rejected(self):
        for value in (float("nan"), float("inf")):
            with self.subTest(value=value):
                resource = _resource("cuc")
                resource["load_cost"]["compiled_size_mb"] = value
                errors = _schema_errors(resource)
                self.assertTrue(
                    errors,
                    "load_cost observations must be finite JSON numbers, not YAML NaN/Infinity",
                )

    def test_non_finite_range_observations_are_rejected(self):
        for key, value in (("min", float("nan")), ("max", float("inf"))):
            with self.subTest(key=key, value=value):
                resource = _resource("greek_literature")
                resource["load_cost"]["typical_member_first_load_seconds"][key] = value
                errors = _schema_errors(resource)
                self.assertTrue(
                    errors,
                    "load_cost ranges must contain finite JSON numbers, not YAML NaN/Infinity",
                )

    def test_yaml_non_finite_literals_are_rejected_after_parsing(self):
        for literal in (".nan", ".inf"):
            with self.subTest(literal=literal):
                parsed = yaml.safe_load(f"value: {literal}\n")["value"]
                self.assertIsInstance(parsed, float)
                self.assertFalse(math.isfinite(parsed))

                resource = _resource("cuc")
                resource["load_cost"]["compiled_size_mb"] = parsed
                errors = _schema_errors(resource)
                self.assertTrue(
                    any("not valid JSON" in error for error in errors),
                    errors,
                )


if __name__ == "__main__":
    unittest.main()
