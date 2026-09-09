from __future__ import annotations

import unittest

from scripts import check_corpus_versions as versions


COMMIT = "a" * 40


def _source(*, publication_version: str | None = "1.2.4", signal: str = "v1.2.4"):
    return versions.SourceCandidate(
        resource_id="example-corpus",
        publication_version=publication_version,
        signal=signal,
        source_revision=COMMIT,
        release_url="https://github.com/example/corpus/releases/tag/example",
    )


def _resource(
    *,
    dataset_mode: str,
    root: str = "tf",
    ordering: str = "semver",
    tag_pattern: str = r"^v(?P<version>[0-9]+\.[0-9]+\.[0-9]+)$",
) -> dict:
    return {
        "id": "example-corpus",
        "kind": "corpus",
        "upstream": {"repository": "example/corpus"},
        "version_tracking": {
            "discovery": {
                "mode": "github-releases",
                "channel": "stable",
                "tag_pattern": tag_pattern,
            },
            "dataset": {
                "mode": dataset_mode,
                "root": root,
                "ordering": ordering,
            },
            "promotion": {"mode": "proposal"},
        },
    }


class FakeDatasetApi:
    def __init__(self, roots: list[str]):
        self.roots = list(roots)
        self.calls: list[tuple[str, str, str, str]] = []

    def list_tf_roots(self, repository: str, source_revision: str, root: str) -> list[str]:
        self.calls.append(("list_tf_roots", repository, source_revision, root))
        if source_revision != COMMIT:
            raise AssertionError("dataset inspection must use the frozen source commit")
        return list(self.roots)

    def download_file(self, *args, **kwargs):
        raise AssertionError("RED3 dataset discovery must not download or execute upstream code")

    def execute(self, *args, **kwargs):
        raise AssertionError("RED3 dataset discovery must be passive")


class CorpusDatasetIdentityRed3Tests(unittest.TestCase):
    def resolve(self, resource: dict, source, api: FakeDatasetApi):
        resolver = getattr(versions, "discover_dataset_candidate", None)
        self.assertIsNotNone(
            resolver,
            "RED3: passive TF dataset identity resolver is missing",
        )
        return resolver(resource, source, api)

    def test_release_version_match_selects_exact_cuc_style_root_at_frozen_commit(self):
        resource = _resource(dataset_mode="release-version-match")
        api = FakeDatasetApi(["1.2.3", "1.2.4", "1.3.0"])

        candidate = self.resolve(resource, _source(), api)

        self.assertEqual(candidate.tf_path, "tf/1.2.4")
        self.assertEqual(candidate.source_revision, COMMIT)
        self.assertEqual(
            api.calls,
            [("list_tf_roots", "example/corpus", COMMIT, "tf")],
        )

    def test_release_version_match_missing_root_fails_without_latest_fallback(self):
        resource = _resource(dataset_mode="release-version-match")
        api = FakeDatasetApi(["1.2.3", "9.9.9"])

        with self.assertRaisesRegex(versions.ReleaseDiscoveryError, r"1\.2\.4|matching|dataset"):
            self.resolve(resource, _source(), api)

    def test_captured_version_uses_configured_tf_capture_not_newer_branch_root(self):
        resource = _resource(
            dataset_mode="captured-version",
            tag_pattern=(
                r"^tlhdig-(?P<version>[0-9]+\.[0-9]+\.[0-9]+)_"
                r"tf-(?P<tf_version>[0-9]+\.[0-9]+\.[0-9]+)$"
            ),
        )
        source = _source(publication_version="0.3.0", signal="tlhdig-0.3.0_tf-0.2.0")
        api = FakeDatasetApi(["0.2.0", "0.3.0", "0.4.0"])

        candidate = self.resolve(resource, source, api)

        self.assertEqual(candidate.tf_path, "tf/0.2.0")

    def test_captured_version_requires_explicit_tf_version_capture(self):
        resource = _resource(dataset_mode="captured-version")
        api = FakeDatasetApi(["1.2.4"])

        with self.assertRaisesRegex(versions.ReleaseDiscoveryError, r"tf_version|capture"):
            self.resolve(resource, _source(), api)

    def test_latest_root_can_select_bhsa_style_dataset_independent_of_release_version(self):
        resource = _resource(dataset_mode="latest-root", ordering="natural")
        source = _source(publication_version="1.8.0", signal="v1.8.0")
        api = FakeDatasetApi(["2017", "2021", "9"])

        candidate = self.resolve(resource, source, api)

        self.assertEqual(candidate.tf_path, "tf/2021")

    def test_fixed_path_preserves_reviewed_release_dataset_mismatch_without_network_lookup(self):
        resource = _resource(dataset_mode="fixed", root="tf/0.1", ordering="none")
        source = _source(publication_version="0.1.0", signal="v0.1.0")
        api = FakeDatasetApi([])

        candidate = self.resolve(resource, source, api)

        self.assertEqual(candidate.tf_path, "tf/0.1")
        self.assertEqual(api.calls, [])

    def test_semver_ordering_is_numeric_not_lexicographic(self):
        resource = _resource(dataset_mode="latest-root", ordering="semver")
        api = FakeDatasetApi(["1.9.0", "1.10.0", "1.2.0"])

        candidate = self.resolve(resource, _source(), api)

        self.assertEqual(candidate.tf_path, "tf/1.10.0")

    def test_natural_ordering_is_deterministic_for_non_semver_labels(self):
        resource = _resource(dataset_mode="latest-root", ordering="natural")
        api = FakeDatasetApi(["9", "10", "2"])

        candidate = self.resolve(resource, _source(publication_version=None, signal="default-branch"), api)

        self.assertEqual(candidate.tf_path, "tf/10")

    def test_none_ordering_refuses_to_guess_between_multiple_roots(self):
        resource = _resource(dataset_mode="latest-root", ordering="none")
        api = FakeDatasetApi(["opaque-a", "opaque-b"])

        with self.assertRaisesRegex(versions.ReleaseDiscoveryError, r"ambiguous|ordering|multiple"):
            self.resolve(resource, _source(publication_version=None, signal="default-branch"), api)

    def test_none_ordering_accepts_one_unambiguous_non_semver_root(self):
        resource = _resource(dataset_mode="latest-root", ordering="none")
        api = FakeDatasetApi(["opaque-release"])

        candidate = self.resolve(resource, _source(publication_version=None, signal="default-branch"), api)

        self.assertEqual(candidate.tf_path, "tf/opaque-release")

    def test_malformed_or_escaping_tf_root_is_rejected_fail_closed(self):
        resource = _resource(dataset_mode="latest-root", ordering="natural")
        api = FakeDatasetApi(["2021", "../escape"])

        with self.assertRaisesRegex(versions.ReleaseDiscoveryError, r"path|root|unsafe|escape"):
            self.resolve(resource, _source(), api)


if __name__ == "__main__":
    unittest.main()
