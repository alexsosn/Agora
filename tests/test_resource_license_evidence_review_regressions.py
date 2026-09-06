from __future__ import annotations

import unittest

from scripts.validate_registry import validate_license_evidence


class ResourceLicenseEvidenceReviewRegressionTests(unittest.TestCase):
    def test_resolved_evidence_rejects_missing_redistribution(self):
        resource = {
            "id": "example",
            "kind": "corpus",
            "licenses": {
                "data": "CC-BY-4.0",
                "evidence": {
                    "status": "resolved",
                    "checked_at": "2026-09-06",
                    "sources": ["https://example.org/license"],
                },
            },
        }
        errors: list[str] = []

        validate_license_evidence(
            resource,
            {"resolved", "component-specific", "member-specific", "unresolved"},
            errors,
        )

        self.assertTrue(
            any(
                "resource example.licenses" in error
                and "resolved evidence requires known data and redistribution" in error
                for error in errors
            ),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
