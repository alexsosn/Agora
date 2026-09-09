from __future__ import annotations

import unittest

from scripts import check_corpus_versions as versions


CURRENT = "1" * 40
CANDIDATE = "2" * 40


def _resource() -> dict:
    return {
        "id": "example-corpus",
        "kind": "corpus",
        "upstream": {
            "repository": "example/corpus",
            "ref": CURRENT,
            "tf_path": "tf/1.2.3",
        },
        "version_tracking": {
            "discovery": {
                "mode": "github-releases",
                "channel": "stable",
                # tag_pattern is intentionally omitted: the merged design makes
                # it optional for ordinary release tags and reserves maintained
                # custom extraction rules for nonstandard conventions.
            },
            "dataset": {
                "mode": "release-version-match",
                "root": "tf",
                "ordering": "semver",
            },
            "promotion": {"mode": "proposal"},
            "accepted": {
                "publication_version": "1.2.3",
                "signal": "v1.2.3",
                "source_revision": CURRENT,
                "tf_path": "tf/1.2.3",
            },
        },
    }


class FakeApi:
    def __init__(self) -> None:
        self.releases = [
            {
                "tag_name": "v1.2.4",
                "draft": False,
                "prerelease": False,
                "html_url": "https://github.com/example/corpus/releases/tag/v1.2.4",
            },
            {
                "tag_name": "release-latest",
                "draft": False,
                "prerelease": False,
                "html_url": "https://github.com/example/corpus/releases/tag/release-latest",
            },
        ]

    def list_releases(self, repository: str):
        return list(self.releases)

    def get_ref(self, repository: str, tag: str):
        if tag != "v1.2.4":
            raise AssertionError("default release syntax must not guess nonstandard tags")
        return {"object": {"type": "commit", "sha": CANDIDATE}}


class OptionalTagPatternReviewTests(unittest.TestCase):
    def test_omitted_tag_pattern_uses_conservative_v_semver_default(self):
        candidate = versions.discover_source_candidate(_resource(), FakeApi())
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.publication_version, "1.2.4")
        self.assertEqual(candidate.signal, "v1.2.4")
        self.assertEqual(candidate.source_revision, CANDIDATE)


if __name__ == "__main__":
    unittest.main()
