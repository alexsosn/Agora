from __future__ import annotations

import importlib
import os
import unittest
from unittest import mock


COMMIT_123 = "1" * 40
COMMIT_124 = "2" * 40
TAG_OBJECT = "3" * 40


def _module():
    try:
        return importlib.import_module("scripts.check_corpus_versions")
    except ModuleNotFoundError:
        return None


def _resource(*, tag_pattern: str = r"^v(?P<version>[0-9]+\.[0-9]+\.[0-9]+)$") -> dict:
    return {
        "id": "example-corpus",
        "kind": "corpus",
        "upstream": {
            "repository": "example/corpus",
            "ref": COMMIT_123,
            # Deliberately unrelated to publication version. Source discovery
            # must compare accepted publication state, not reverse-engineer it
            # from a TF path.
            "tf_path": "tf/2099",
        },
        "version_tracking": {
            "discovery": {
                "mode": "github-releases",
                "channel": "stable",
                "tag_pattern": tag_pattern,
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
                "source_revision": COMMIT_123,
                "tf_path": "tf/2099",
            },
        },
    }


class FakeReleaseApi:
    def __init__(self, releases, *, refs=None, tags=None):
        self.releases = list(releases)
        self.refs = dict(refs or {})
        self.tags = dict(tags or {})
        self.calls = []

    def list_releases(self, repository):
        self.calls.append(("list_releases", repository))
        return list(self.releases)

    def get_ref(self, repository, tag):
        self.calls.append(("get_ref", repository, tag))
        value = self.refs[tag]
        if isinstance(value, Exception):
            raise value
        return value

    def get_tag_object(self, repository, sha):
        self.calls.append(("get_tag_object", repository, sha))
        return self.tags[sha]


class CorpusSourceDiscoveryRed2Tests(unittest.TestCase):
    def require_module(self):
        module = _module()
        self.assertIsNotNone(
            module,
            "RED2: scripts.check_corpus_versions immutable source-discovery seam is missing",
        )
        return module

    @staticmethod
    def release(tag, *, draft=False, prerelease=False):
        return {
            "tag_name": tag,
            "draft": draft,
            "prerelease": prerelease,
            "html_url": f"https://github.com/example/corpus/releases/tag/{tag}",
        }

    def test_selects_highest_stable_semver_and_ignores_draft_prerelease(self):
        module = self.require_module()
        api = FakeReleaseApi(
            [
                self.release("v9.0.0", draft=True),
                self.release("v2.0.0-rc.1", prerelease=True),
                self.release("v1.2.4"),
                self.release("v1.2.3"),
            ],
            refs={
                "v1.2.4": {"object": {"type": "commit", "sha": COMMIT_124}},
            },
        )
        candidate = module.discover_source_candidate(_resource(), api)
        self.assertEqual(candidate.publication_version, "1.2.4")
        self.assertEqual(candidate.signal, "v1.2.4")
        self.assertEqual(candidate.source_revision, COMMIT_124)

    def test_configured_nonstandard_tag_pattern_extracts_publication_version(self):
        module = self.require_module()
        resource = _resource(
            tag_pattern=r"^TLHdig-v(?P<version>[0-9]+\.[0-9]+\.[0-9]+)$"
        )
        resource["version_tracking"]["accepted"]["signal"] = "TLHdig-v1.2.3"
        api = FakeReleaseApi(
            [self.release("TLHdig-v1.2.4")],
            refs={
                "TLHdig-v1.2.4": {
                    "object": {"type": "commit", "sha": COMMIT_124}
                }
            },
        )
        candidate = module.discover_source_candidate(resource, api)
        self.assertEqual(candidate.publication_version, "1.2.4")
        self.assertEqual(candidate.signal, "TLHdig-v1.2.4")

    def test_annotated_release_tag_resolves_to_terminal_full_commit(self):
        module = self.require_module()
        api = FakeReleaseApi(
            [self.release("v1.2.4")],
            refs={
                "v1.2.4": {"object": {"type": "tag", "sha": TAG_OBJECT}},
            },
            tags={
                TAG_OBJECT: {"object": {"type": "commit", "sha": COMMIT_124}},
            },
        )
        candidate = module.discover_source_candidate(_resource(), api)
        self.assertEqual(candidate.source_revision, COMMIT_124)
        self.assertIn(("get_tag_object", "example/corpus", TAG_OBJECT), api.calls)

    def test_retargeted_accepted_release_is_supply_chain_anomaly(self):
        module = self.require_module()
        api = FakeReleaseApi(
            [self.release("v1.2.3")],
            refs={
                "v1.2.3": {"object": {"type": "commit", "sha": COMMIT_124}},
            },
        )
        with self.assertRaisesRegex(
            module.ReleaseDiscoveryError,
            r"retag|retarget|same.*version|accepted.*commit",
        ):
            module.discover_source_candidate(_resource(), api)

    def test_selected_highest_release_resolution_failure_does_not_fallback(self):
        module = self.require_module()
        failure = module.ReleaseDiscoveryError("selected release tag cannot be resolved")
        api = FakeReleaseApi(
            [self.release("v1.2.5"), self.release("v1.2.4")],
            refs={
                "v1.2.5": failure,
                "v1.2.4": {"object": {"type": "commit", "sha": COMMIT_124}},
            },
        )
        with self.assertRaisesRegex(module.ReleaseDiscoveryError, r"selected release"):
            module.discover_source_candidate(_resource(), api)
        self.assertNotIn(("get_ref", "example/corpus", "v1.2.4"), api.calls)

    def test_release_comparison_uses_accepted_publication_not_tf_path(self):
        module = self.require_module()
        resource = _resource()
        resource["upstream"]["tf_path"] = "tf/9999"
        resource["version_tracking"]["accepted"]["tf_path"] = "tf/9999"
        api = FakeReleaseApi(
            [self.release("v1.2.4")],
            refs={
                "v1.2.4": {"object": {"type": "commit", "sha": COMMIT_124}},
            },
        )
        candidate = module.discover_source_candidate(resource, api)
        self.assertEqual(candidate.publication_version, "1.2.4")

    def test_default_branch_source_is_frozen_before_any_dataset_inspection(self):
        module = self.require_module()
        resource = _resource()
        resource["upstream"] = {"repository": "example/corpus"}
        resource["version_tracking"] = {
            "discovery": {"mode": "default-branch"},
            "dataset": {"mode": "latest-root", "root": "tf", "ordering": "natural"},
            "promotion": {"mode": "discovery-only"},
        }

        class BranchApi:
            def __init__(self):
                self.calls = []

            def get_default_branch_head(self, repository):
                self.calls.append(("get_default_branch_head", repository))
                return COMMIT_124

            def list_tf_roots(self, *args, **kwargs):
                raise AssertionError("RED2 source discovery must not inspect TF roots")

        api = BranchApi()
        candidate = module.discover_source_candidate(resource, api)
        self.assertEqual(candidate.source_revision, COMMIT_124)
        self.assertEqual(api.calls, [("get_default_branch_head", "example/corpus")])

    def test_public_upstream_api_never_forwards_repository_scoped_token(self):
        module = self.require_module()
        observed = []

        def requester(url, *, headers, timeout):
            observed.append((url, dict(headers), timeout))
            return b"[]"

        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "repository-secret"}):
            api = module.public_github_api(requester=requester)
            self.assertEqual(api.list_releases("example/corpus"), [])

        self.assertEqual(len(observed), 1)
        self.assertNotIn("Authorization", observed[0][1])
        self.assertNotIn("repository-secret", repr(observed[0]))


if __name__ == "__main__":
    unittest.main()
