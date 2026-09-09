from __future__ import annotations

import copy
import unittest

from scripts import check_corpus_versions as checker


OLD_REF = "1" * 40
NEW_REF = "2" * 40
OLD_HEAD = "3" * 40
NEW_HEAD = "4" * 40


def _resource() -> dict:
    return {
        "id": "example-corpus",
        "kind": "corpus",
        "plugin": "context-fabric",
        "provider": "context-fabric",
        "upstream": {"repository": "example/corpus", "ref": OLD_REF, "tf_path": "tf/1.0.0"},
        "licenses": {
            "data": "CC-BY-4.0",
            "redistribution": "permitted",
            "evidence": {
                "status": "resolved",
                "checked_at": "2026-09-09",
                "sources": ["https://example.org/license"],
            },
        },
        "verification": {
            "status": "verified",
            "evidence": [{"check_id": "resource-load/example-corpus"}],
        },
        "version_tracking": {
            "discovery": {
                "mode": "github-releases",
                "channel": "stable",
                "tag_pattern": r"^v(?P<version>[0-9]+\.[0-9]+\.[0-9]+)$",
            },
            "dataset": {"mode": "release-version-match", "root": "tf", "ordering": "semver"},
            "promotion": {"mode": "proposal"},
            "accepted": {
                "publication_version": "1.0.0",
                "signal": "v1.0.0",
                "source_revision": OLD_REF,
                "tf_path": "tf/1.0.0",
            },
        },
    }


def _candidate(*, source_revision: str = NEW_REF, tf_path: str = "tf/2.0.0") -> checker.DatasetCandidate:
    return checker.DatasetCandidate(
        resource_id="example-corpus",
        publication_version="2.0.0",
        signal="v2.0.0",
        source_revision=source_revision,
        tf_path=tf_path,
        release_url="https://github.com/example/corpus/releases/tag/v2.0.0",
    )


def _module(*, versions: list[str]) -> dict:
    return {
        "id": "example-module",
        "kind": "feature-module",
        "parent": "example-corpus",
        "compatibility": {"parent_versions": versions},
    }


def _stage_a(resource: dict, candidate: checker.DatasetCandidate, *, modules: list[dict] | None = None) -> dict:
    helper = getattr(checker, "assess_stage_a_candidate", None)
    if not callable(helper):
        raise AssertionError("RED: assess_stage_a_candidate is missing")
    return helper(resource, candidate, feature_modules=modules or [])


def _evidence(**changes) -> dict:
    evidence = {
        "pr_head": NEW_HEAD,
        "resource_id": "example-corpus",
        "source_revision": NEW_REF,
        "tf_path": "tf/2.0.0",
        "check_id": "resource-load/example-corpus",
        "check_kind": "resource-load",
        "evidence_level": "verified",
        "claims": ["materialization", "load", "representative-content"],
    }
    evidence.update(changes)
    return evidence


def _stage_b(candidate: checker.DatasetCandidate, evidence: dict, **changes) -> dict:
    helper = getattr(checker, "assess_stage_b_promotion", None)
    if not callable(helper):
        raise AssertionError("RED: assess_stage_b_promotion is missing")
    kwargs = {
        "candidate_pr_head": NEW_HEAD,
        "evidence": [evidence],
        "trusted_base_fingerprints": {
            "verification-check": "a" * 64,
            "workflow": "b" * 64,
            "smoke": "c" * 64,
            "promotion-verifier": "d" * 64,
        },
        "candidate_fingerprints": {
            "verification-check": "a" * 64,
            "workflow": "b" * 64,
            "smoke": "c" * 64,
            "promotion-verifier": "d" * 64,
        },
    }
    kwargs.update(changes)
    return helper("example-corpus", candidate, **kwargs)


class CorpusVersionStageATrustRedTests(unittest.TestCase):
    def test_changed_source_revision_downgrades_stale_verified_status(self):
        result = _stage_a(_resource(), _candidate())
        self.assertEqual(result["verification_status"], "community")
        self.assertTrue(result["verification_pending"])
        self.assertNotEqual(result["verification_status"], "verified")

    def test_changed_tf_path_downgrades_stale_verified_status(self):
        resource = _resource()
        candidate = _candidate(source_revision=OLD_REF, tf_path="tf/2.0.0")
        result = _stage_a(resource, candidate)
        self.assertEqual(result["verification_status"], "community")
        self.assertTrue(result["verification_pending"])

    def test_unchanged_effective_dataset_identity_preserves_verified_status(self):
        resource = _resource()
        candidate = _candidate(source_revision=OLD_REF, tf_path="tf/1.0.0")
        result = _stage_a(resource, candidate)
        self.assertEqual(result["verification_status"], "verified")
        self.assertFalse(result["verification_pending"])

    def test_incompatible_feature_module_blocks_parent_promotion(self):
        result = _stage_a(_resource(), _candidate(), modules=[_module(versions=["1.0.0"])])
        self.assertTrue(any("module" in reason.lower() and "compat" in reason.lower() for reason in result["blocking_reasons"]), result)

    def test_compatible_feature_module_does_not_block_parent_promotion(self):
        result = _stage_a(_resource(), _candidate(), modules=[_module(versions=["2.0.0"])])
        self.assertFalse(any("module" in reason.lower() and "compat" in reason.lower() for reason in result["blocking_reasons"]), result)

    def test_unresolved_license_remains_visible_as_caveat(self):
        resource = _resource()
        resource["licenses"] = {
            "data": "unknown",
            "redistribution": "unknown",
            "notes": "Authoritative evidence did not establish corpus redistribution rights.",
            "evidence": {
                "status": "unresolved",
                "checked_at": "2026-09-09",
                "sources": ["https://example.org/terms"],
            },
        }
        result = _stage_a(resource, _candidate())
        self.assertTrue(any("licen" in caveat.lower() or "redistribut" in caveat.lower() for caveat in result["caveats"]), result)
        self.assertEqual(result["license_evidence_status"], "unresolved")


class CorpusVersionStageBTrustRedTests(unittest.TestCase):
    def test_exact_candidate_verified_evidence_can_promote(self):
        result = _stage_b(_candidate(), _evidence())
        self.assertTrue(result["can_promote"], result)
        self.assertEqual(result["verification_status"], "verified")
        self.assertEqual(result["promoted_subjects"], ["example-corpus"])

    def test_evidence_from_different_pr_head_cannot_promote(self):
        result = _stage_b(_candidate(), _evidence(pr_head=OLD_HEAD))
        self.assertFalse(result["can_promote"])
        self.assertTrue(any("head" in reason.lower() for reason in result["blocking_reasons"]), result)

    def test_evidence_from_different_source_revision_or_tf_path_cannot_promote(self):
        wrong_ref = _stage_b(_candidate(), _evidence(source_revision=OLD_REF))
        wrong_path = _stage_b(_candidate(), _evidence(tf_path="tf/1.0.0"))
        self.assertFalse(wrong_ref["can_promote"])
        self.assertFalse(wrong_path["can_promote"])

    def test_known_issue_canary_cannot_supply_positive_promotion(self):
        result = _stage_b(
            _candidate(),
            _evidence(check_id="known-issue-canary/example", check_kind="known-issue-canary"),
        )
        self.assertFalse(result["can_promote"])
        self.assertTrue(any("canary" in reason.lower() or "positive" in reason.lower() for reason in result["blocking_reasons"]), result)

    def test_missing_required_live_claim_cannot_promote(self):
        result = _stage_b(_candidate(), _evidence(claims=["load", "representative-content"]))
        self.assertFalse(result["can_promote"])
        self.assertTrue(any("materialization" in reason.lower() or "claim" in reason.lower() for reason in result["blocking_reasons"]), result)

    def test_candidate_changed_verification_producer_blocks_automatic_promotion(self):
        candidate_fingerprints = {
            "verification-check": "a" * 64,
            "workflow": "9" * 64,
            "smoke": "c" * 64,
            "promotion-verifier": "d" * 64,
        }
        result = _stage_b(_candidate(), _evidence(), candidate_fingerprints=candidate_fingerprints)
        self.assertFalse(result["can_promote"])
        self.assertTrue(any("trusted" in reason.lower() or "workflow" in reason.lower() for reason in result["blocking_reasons"]), result)

    def test_candidate_changed_evidence_consumer_blocks_automatic_promotion(self):
        candidate_fingerprints = {
            "verification-check": "a" * 64,
            "workflow": "b" * 64,
            "smoke": "c" * 64,
            "promotion-verifier": "9" * 64,
        }
        result = _stage_b(_candidate(), _evidence(), candidate_fingerprints=candidate_fingerprints)
        self.assertFalse(result["can_promote"])
        self.assertTrue(any("trusted" in reason.lower() or "verifier" in reason.lower() for reason in result["blocking_reasons"]), result)


if __name__ == "__main__":
    unittest.main()
