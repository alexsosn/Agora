from __future__ import annotations

import unittest

from test_corpus_version_candidate_trust import _candidate, _evidence, _stage_b
from test_resource_version_tracking import _resource, _schema_errors


class CorpusVersionTrackingModeReviewTests(unittest.TestCase):
    """Adversarial RED: TF-directory discovery must not accept release-only fields."""

    def tracking(self) -> dict:
        return {
            "discovery": {"mode": "tf-directories"},
            "dataset": {"mode": "latest-root", "root": "tf", "ordering": "natural"},
            "promotion": {"mode": "discovery-only"},
        }

    def test_tf_directories_rejects_release_channel(self):
        resource = _resource()
        tracking = self.tracking()
        tracking["discovery"]["channel"] = "stable"
        resource["version_tracking"] = tracking
        self.assertTrue(_schema_errors(resource))

    def test_tf_directories_rejects_release_tag_pattern(self):
        resource = _resource()
        tracking = self.tracking()
        tracking["discovery"]["tag_pattern"] = r"^v(?P<version>[0-9]+)$"
        resource["version_tracking"] = tracking
        self.assertTrue(_schema_errors(resource))


class CorpusVersionStageBFingerprintReviewTests(unittest.TestCase):
    """Adversarial RED: absence is not proof of trusted-base byte equivalence."""

    def complete(self) -> dict[str, str]:
        return {
            "verification-check": "a" * 64,
            "workflow": "b" * 64,
            "smoke": "c" * 64,
            "promotion-verifier": "d" * 64,
        }

    def test_missing_same_fingerprint_on_both_sides_cannot_promote(self):
        trusted = self.complete()
        candidate = self.complete()
        trusted.pop("workflow")
        candidate.pop("workflow")
        result = _stage_b(
            _candidate(),
            _evidence(),
            trusted_base_fingerprints=trusted,
            candidate_fingerprints=candidate,
        )
        self.assertFalse(result["can_promote"], result)
        self.assertTrue(
            any("workflow" in reason.lower() and ("missing" in reason.lower() or "trusted" in reason.lower())
                for reason in result["blocking_reasons"]),
            result,
        )

    def test_missing_trusted_or_candidate_fingerprint_cannot_promote(self):
        for side in ("trusted", "candidate"):
            with self.subTest(side=side):
                trusted = self.complete()
                candidate = self.complete()
                (trusted if side == "trusted" else candidate).pop("smoke")
                result = _stage_b(
                    _candidate(),
                    _evidence(),
                    trusted_base_fingerprints=trusted,
                    candidate_fingerprints=candidate,
                )
                self.assertFalse(result["can_promote"], result)


if __name__ == "__main__":
    unittest.main()
