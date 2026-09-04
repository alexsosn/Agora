from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class ProviderHealthContractTests(unittest.TestCase):
    def load_yaml(self, relative_path: str):
        with (ROOT / relative_path).open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    def test_providers_use_health_not_plugin_verification_status(self):
        providers = self.load_yaml("registry/providers.yaml")["providers"]
        for provider in providers:
            with self.subTest(provider=provider["id"]):
                self.assertIn("health", provider)
                self.assertNotIn("verification", provider)
                self.assertIn(
                    provider["health"]["status"],
                    {"unknown", "observed-operational", "degraded", "unavailable"},
                )

    def test_provider_health_has_separate_controlled_vocabulary(self):
        vocab = self.load_yaml("registry/vocabularies.yaml")
        self.assertEqual(
            set(vocab["provider_health_statuses"]),
            {"unknown", "observed-operational", "degraded", "unavailable"},
        )

    def test_provider_schema_requires_health_instead_of_verification(self):
        with (ROOT / "registry/schema/providers.schema.json").open("r", encoding="utf-8") as fh:
            schema = json.load(fh)
        provider_schema = schema["properties"]["providers"]["items"]
        self.assertIn("health", provider_schema["required"])
        self.assertNotIn("verification", provider_schema["required"])
        self.assertIn("health", provider_schema["properties"])
        self.assertNotIn("verification", provider_schema["properties"])


if __name__ == "__main__":
    unittest.main()
