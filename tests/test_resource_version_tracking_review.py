from __future__ import annotations

import unittest

from scripts.validate_registry import validate_version_tracking


class ProposalCorpusTfIdentityReviewTests(unittest.TestCase):
    def test_proposal_corpus_requires_concrete_accepted_tf_path(self):
        revision = "a" * 40
        resource = {
            "id": "example-corpus",
            "kind": "corpus",
            "upstream": {
                "repository": "example/corpus",
                "ref": revision,
            },
            "version_tracking": {
                "discovery": {
                    "mode": "github-releases",
                    "channel": "stable",
                },
                "dataset": {
                    "mode": "latest-root",
                    "root": "tf",
                    "ordering": "natural",
                },
                "promotion": {"mode": "proposal"},
                "accepted": {
                    "publication_version": "1.0.0",
                    "signal": "v1.0.0",
                    "source_revision": revision,
                },
            },
        }

        errors: list[str] = []
        validate_version_tracking(resource, errors)

        self.assertTrue(
            any("tf_path" in error for error in errors),
            f"proposal corpus without an accepted/runtime TF path was accepted: {errors!r}",
        )


if __name__ == "__main__":
    unittest.main()
