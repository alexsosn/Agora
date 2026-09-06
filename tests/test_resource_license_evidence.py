from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.validate_registry import ROOT, validate_registry

PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog
from agora_context_fabric.service import ContextFabricService


class ResourceLicenseEvidenceTests(unittest.TestCase):
    VALIDATION_DEPENDENCIES = (
        "tests/test_generation.py",
        ".github/workflows/external-mcp-smoke.yml",
        "plugins/context-fabric/uv.lock",
        "plugins/perseus/runtime-constraints.txt",
        "plugins/sefaria/runtime-constraints.txt",
        "plugins/sedra/uv.lock",
        "verification/mcp-smoke/uv.lock",
    )

    @classmethod
    def copy_validation_dependencies(cls, tmp_root: Path) -> None:
        for relative in cls.VALIDATION_DEPENDENCIES:
            source = ROOT / relative
            target = tmp_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    def validate_resource_mutation(self, resource_id: str, mutate) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            shutil.copytree(ROOT / "registry", tmp_root / "registry")
            self.copy_validation_dependencies(tmp_root)
            path = tmp_root / "registry" / "resources.yaml"
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            resource = next(item for item in doc["resources"] if item["id"] == resource_id)
            mutate(resource)
            path.write_text(
                yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            return validate_registry(tmp_root)

    @staticmethod
    def evidence(status: str) -> dict[str, object]:
        return {
            "status": status,
            "checked_at": "2026-09-06",
            "sources": ["https://example.org/authoritative-license"],
        }

    def assert_error_contains(self, errors: list[str], *parts: str) -> None:
        self.assertTrue(
            any(all(part in error for part in parts) for error in errors),
            errors,
        )

    def test_every_corpus_and_collection_has_reproducible_license_evidence(self):
        doc = yaml.safe_load((ROOT / "registry" / "resources.yaml").read_text(encoding="utf-8"))
        audited = [item for item in doc["resources"] if item["kind"] in {"corpus", "collection"}]
        self.assertEqual(len(audited), 37)
        for resource in audited:
            with self.subTest(resource=resource["id"]):
                evidence = resource["licenses"]["evidence"]
                self.assertIn(
                    evidence["status"],
                    {"resolved", "component-specific", "member-specific", "unresolved"},
                )
                self.assertTrue(evidence["checked_at"])
                self.assertTrue(evidence["sources"])

    def test_corpus_without_license_evidence_is_rejected(self):
        def mutate(resource):
            resource["licenses"].pop("evidence", None)

        errors = self.validate_resource_mutation("bhsa", mutate)
        self.assert_error_contains(errors, "licenses", "'evidence' is a required property")

    def test_collection_without_license_evidence_is_rejected(self):
        def mutate(resource):
            resource["licenses"].pop("evidence", None)

        errors = self.validate_resource_mutation("bible", mutate)
        self.assert_error_contains(errors, "licenses", "'evidence' is a required property")

    def test_feature_module_without_license_evidence_remains_valid(self):
        feature_modules = yaml.safe_load(
            (ROOT / "registry" / "feature-modules.yaml").read_text(encoding="utf-8")
        )["resources"]
        self.assertTrue(feature_modules)
        self.assertTrue(all("evidence" not in item["licenses"] for item in feature_modules))
        errors = validate_registry()
        self.assertFalse(
            any("feature-module" in error and "evidence" in error for error in errors),
            errors,
        )

    def test_resolved_evidence_rejects_unknown_data_license(self):
        def mutate(resource):
            resource["licenses"] = {
                "data": "unknown",
                "redistribution": "permitted",
                "evidence": self.evidence("resolved"),
            }

        errors = self.validate_resource_mutation("bhsa", mutate)
        self.assert_error_contains(
            errors,
            "resource bhsa.licenses",
            "resolved evidence requires known data and redistribution",
        )

    def test_resolved_evidence_rejects_unknown_redistribution(self):
        def mutate(resource):
            resource["licenses"] = {
                "data": "CC-BY-4.0",
                "redistribution": "unknown",
                "evidence": self.evidence("resolved"),
            }

        errors = self.validate_resource_mutation("bhsa", mutate)
        self.assert_error_contains(
            errors,
            "resource bhsa.licenses",
            "resolved evidence requires known data and redistribution",
        )

    def test_researched_unknown_is_valid_with_notes_and_sources(self):
        def mutate(resource):
            resource["licenses"] = {
                "data": "unknown",
                "redistribution": "unknown",
                "notes": "Repository licence covers software; corpus-data terms remain unstated.",
                "evidence": self.evidence("unresolved"),
            }

        self.assertEqual(self.validate_resource_mutation("bhsa", mutate), [])

    def test_unresolved_evidence_requires_explanatory_notes(self):
        def mutate(resource):
            resource["licenses"] = {
                "data": "unknown",
                "redistribution": "unknown",
                "evidence": self.evidence("unresolved"),
            }

        errors = self.validate_resource_mutation("bhsa", mutate)
        self.assert_error_contains(
            errors,
            "resource bhsa.licenses.notes",
            "unresolved evidence requires explanatory notes",
        )

    def test_component_specific_top_level_license_is_valid(self):
        def mutate(resource):
            resource["licenses"] = {
                "data": "CC-BY-4.0",
                "redistribution": "restricted",
                "notes": "Embedded source components carry stricter no-change terms.",
                "evidence": self.evidence("component-specific"),
            }

        self.assertEqual(self.validate_resource_mutation("bhsa", mutate), [])

    def test_component_specific_scalar_requires_component_specific_evidence(self):
        def mutate(resource):
            resource["licenses"] = {
                "data": "component-specific",
                "redistribution": "unknown",
                "notes": "Text and annotations have materially different terms.",
                "evidence": self.evidence("unresolved"),
            }

        errors = self.validate_resource_mutation("bhsa", mutate)
        self.assert_error_contains(
            errors,
            "resource bhsa.licenses.data",
            "component-specific requires evidence.status='component-specific'",
        )

    def test_component_specific_evidence_requires_explanatory_notes(self):
        def mutate(resource):
            resource["licenses"] = {
                "data": "component-specific",
                "redistribution": "unknown",
                "evidence": self.evidence("component-specific"),
            }

        errors = self.validate_resource_mutation("bhsa", mutate)
        self.assert_error_contains(
            errors,
            "resource bhsa.licenses.notes",
            "component-specific evidence requires explanatory notes",
        )

    def test_member_specific_is_rejected_on_corpus(self):
        def mutate(resource):
            resource["licenses"] = {
                "data": "member-specific",
                "redistribution": "unknown",
                "notes": "Member-level terms would live in individual records.",
                "evidence": self.evidence("member-specific"),
            }

        errors = self.validate_resource_mutation("bhsa", mutate)
        self.assert_error_contains(
            errors,
            "resource bhsa.licenses",
            "member-specific licensing is only valid for collections",
        )

    def test_member_specific_collection_is_valid(self):
        def mutate(resource):
            resource["licenses"] = {
                "data": "member-specific",
                "redistribution": "unknown",
                "notes": "Individual collection members carry their own rights metadata.",
                "evidence": self.evidence("member-specific"),
            }

        self.assertEqual(self.validate_resource_mutation("bible", mutate), [])

    def test_member_specific_evidence_requires_explanatory_notes(self):
        def mutate(resource):
            resource["licenses"] = {
                "data": "member-specific",
                "redistribution": "unknown",
                "evidence": self.evidence("member-specific"),
            }

        errors = self.validate_resource_mutation("bible", mutate)
        self.assert_error_contains(
            errors,
            "resource bible.licenses.notes",
            "member-specific evidence requires explanatory notes",
        )

    def test_evidence_requires_at_least_one_source(self):
        def mutate(resource):
            evidence = self.evidence("unresolved")
            evidence["sources"] = []
            resource["licenses"] = {
                "data": "unknown",
                "redistribution": "unknown",
                "notes": "Authoritative sources were checked without a conclusive licence.",
                "evidence": evidence,
            }

        errors = self.validate_resource_mutation("bhsa", mutate)
        self.assert_error_contains(errors, "sources", "should be non-empty")

    def test_evidence_source_must_be_uri(self):
        def mutate(resource):
            evidence = self.evidence("unresolved")
            evidence["sources"] = ["not a uri"]
            resource["licenses"] = {
                "data": "unknown",
                "redistribution": "unknown",
                "notes": "Authoritative sources were checked without a conclusive licence.",
                "evidence": evidence,
            }

        errors = self.validate_resource_mutation("bhsa", mutate)
        self.assert_error_contains(errors, "not a uri", "is not a 'uri'")

    def test_evidence_checked_at_must_be_date(self):
        def mutate(resource):
            evidence = self.evidence("unresolved")
            evidence["checked_at"] = "2026-99-99"
            resource["licenses"] = {
                "data": "unknown",
                "redistribution": "unknown",
                "notes": "Authoritative sources were checked without a conclusive licence.",
                "evidence": evidence,
            }

        errors = self.validate_resource_mutation("bhsa", mutate)
        self.assert_error_contains(errors, "2026-99-99", "is not a 'date'")

    def test_runtime_description_preserves_nested_license_evidence(self):
        catalog = Catalog.from_registry(ROOT)
        service = ContextFabricService(catalog, resolver=None, loader=None)
        description = service.describe_resource("bhsa")
        self.assertEqual(description["licenses"], catalog.get("bhsa").licenses)
        self.assertEqual(description["licenses"]["evidence"]["status"], "resolved")
        self.assertTrue(description["licenses"]["evidence"]["sources"])


if __name__ == "__main__":
    unittest.main()
