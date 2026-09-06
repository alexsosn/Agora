from __future__ import annotations

import unittest

from scripts.validate_registry import validate_license_evidence


class ResourceLicenseEvidenceReviewRegressionTests(unittest.TestCase):
    @staticmethod
    def _validate(licenses: dict[str, object], *, kind: str = "corpus") -> list[str]:
        resource = {
            "id": "example",
            "kind": kind,
            "licenses": licenses,
        }
        errors: list[str] = []
        validate_license_evidence(
            resource,
            {"resolved", "component-specific", "member-specific", "unresolved"},
            errors,
        )
        return errors

    def test_resolved_evidence_rejects_missing_redistribution(self):
        errors = self._validate(
            {
                "data": "CC-BY-4.0",
                "evidence": {
                    "status": "resolved",
                    "checked_at": "2026-09-06",
                    "sources": ["https://example.org/license"],
                },
            }
        )

        self.assertTrue(
            any(
                "resource example.licenses" in error
                and "resolved evidence requires known data and redistribution" in error
                for error in errors
            ),
            errors,
        )

    def test_unresolved_evidence_rejects_fully_resolved_scalars(self):
        errors = self._validate(
            {
                "data": "CC-BY-4.0",
                "redistribution": "permitted",
                "notes": "This deliberately contradictory fixture must fail closed.",
                "evidence": {
                    "status": "unresolved",
                    "checked_at": "2026-09-06",
                    "sources": ["https://example.org/license"],
                },
            }
        )

        self.assertTrue(
            any(
                "resource example.licenses" in error
                and "unresolved evidence requires an unknown licensing dimension" in error
                for error in errors
            ),
            errors,
        )

    def test_component_specific_evidence_rejects_unknown_data_scalar(self):
        errors = self._validate(
            {
                "data": "unknown",
                "redistribution": "unknown",
                "notes": "Components have different terms, so the data scalar must say so.",
                "evidence": {
                    "status": "component-specific",
                    "checked_at": "2026-09-06",
                    "sources": ["https://example.org/license"],
                },
            }
        )

        self.assertTrue(
            any(
                "resource example.licenses.data" in error
                and "component-specific evidence requires known or component-specific data" in error
                for error in errors
            ),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
