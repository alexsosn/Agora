from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.validate_registry import ROOT, validate_registry


class ProviderHealthContractTests(unittest.TestCase):
    def load_yaml(self, relative_path: str, root: Path = ROOT):
        with (root / relative_path).open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    def write_yaml(self, root: Path, relative_path: str, doc) -> None:
        (root / relative_path).write_text(
            yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    def make_root(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        shutil.copytree(ROOT / "registry", root / "registry")
        workflows = root / ".github" / "workflows"
        workflows.parent.mkdir(parents=True)
        shutil.copytree(ROOT / ".github/workflows", workflows)
        (root / "tests").mkdir()
        shutil.copy2(ROOT / "tests/test_generation.py", root / "tests/test_generation.py")
        return root

    def mutate_provider(self, root: Path, provider_id: str, mutate) -> None:
        doc = self.load_yaml("registry/providers.yaml", root)
        provider = next(item for item in doc["providers"] if item["id"] == provider_id)
        mutate(provider)
        self.write_yaml(root, "registry/providers.yaml", doc)

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

    def test_provider_health_may_legitimately_differ_from_plugin_aggregate_status(self):
        self.assertEqual(validate_registry(), [])
        providers = self.load_yaml("registry/providers.yaml")["providers"]
        plugins = {
            item["id"]: item
            for item in self.load_yaml("registry/plugins.yaml")["plugins"]
        }
        for provider in providers:
            with self.subTest(provider=provider["id"]):
                self.assertEqual(provider["health"]["status"], "observed-operational")
                self.assertEqual(plugins[provider["plugin"]]["verification"]["status"], "community")

    def test_observed_operational_rejects_missing_check_id(self):
        root = self.make_root()
        self.mutate_provider(
            root,
            "context-fabric",
            lambda provider: provider["health"]["evidence"][0].update(
                {"check_id": "mcp-live/does-not-exist"}
            ),
        )
        errors = validate_registry(root)
        self.assertTrue(
            any("provider context-fabric.health.evidence" in error and "missing verification check" in error for error in errors),
            errors,
        )

    def test_observed_operational_rejects_deterministic_only_evidence(self):
        root = self.make_root()
        self.mutate_provider(
            root,
            "context-fabric",
            lambda provider: provider["health"]["evidence"][0].update(
                {"check_id": "manifest/context-fabric-claude"}
            ),
        )
        errors = validate_registry(root)
        self.assertTrue(
            any("provider context-fabric.health.evidence" in error and "must reference a live check" in error for error in errors),
            errors,
        )

    def test_observed_operational_rejects_cross_plugin_live_evidence(self):
        root = self.make_root()
        self.mutate_provider(
            root,
            "context-fabric",
            lambda provider: provider["health"]["evidence"][0].update(
                {"check_id": "mcp-live/perseus-codex"}
            ),
        )
        errors = validate_registry(root)
        self.assertTrue(
            any("provider context-fabric.health.evidence" in error and "belongs to plugin 'perseus'" in error for error in errors),
            errors,
        )

    def test_observed_operational_requires_evidence(self):
        root = self.make_root()
        self.mutate_provider(
            root,
            "context-fabric",
            lambda provider: provider["health"].pop("evidence", None),
        )
        errors = validate_registry(root)
        self.assertTrue(
            any("provider context-fabric.health" in error and "requires at least one live evidence check" in error for error in errors),
            errors,
        )

    def test_missing_provider_plugin_reference_is_still_rejected(self):
        root = self.make_root()
        self.mutate_provider(
            root,
            "context-fabric",
            lambda provider: provider.update({"plugin": "does-not-exist"}),
        )
        errors = validate_registry(root)
        self.assertTrue(
            any("provider context-fabric: references missing plugin 'does-not-exist'" in error for error in errors),
            errors,
        )

    def test_registry_docs_distinguish_three_status_dimensions(self):
        text = (ROOT / "registry/README.md").read_text(encoding="utf-8")
        for phrase in (
            "Provider/service health",
            "Plugin/client integration evidence",
            "Resource/data status",
        ):
            self.assertIn(phrase, text)

    def test_user_facing_verification_scope_keeps_health_and_quality_separate(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("provider/service health", text)
        self.assertIn("plugin/client integration evidence", text)
        self.assertIn("resource/data status", text)
        self.assertIn("does not establish scholarly suitability", text)


if __name__ == "__main__":
    unittest.main()
