from __future__ import annotations

import importlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
MODULE_NAME = "scripts.check_materializer_releases"
try:
    updates = importlib.import_module(MODULE_NAME)
except ModuleNotFoundError:
    updates = None


COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
COMMIT_C = "c" * 40
TAG_A = "d" * 40
TAG_B = "e" * 40


def _module():
    if updates is None:
        raise AssertionError(f"missing release updater module {MODULE_NAME}")
    return updates


def _plugin(**overrides):
    plugin = {
        "id": "example-converter",
        "name": "Example converter",
        "description": "Example.",
        "repository": "example/converter",
        "ref": COMMIT_A,
        "version": "1.2.3",
        "manifest": "agora.materializer.json",
        "package": {
            "type": "python-project",
            "path": ".",
            "install_trust": "explicit-code-execution",
        },
        "materializers": ["example-to-tf"],
        "disciplines": ["digital-philology"],
        "licenses": {"software": "MIT", "data": "upstream-dependent"},
        "verification": {"status": "experimental"},
        "release_tracking": {
            "mode": "github-releases",
            "channel": "stable",
            "tag_prefix": "v",
        },
    }
    plugin.update(overrides)
    return plugin


def _manifest(*, version="1.2.4", plugin_id="example-converter", repository="example/converter", materializers=None):
    ids = materializers if materializers is not None else ["example-to-tf"]
    return {
        "schema_version": 1,
        "plugin": {
            "id": plugin_id,
            "name": "Example converter",
            "version": version,
            "repository": repository,
        },
        "materializers": [
            {
                "id": materializer_id,
                "description": "Convert example XML.",
                "acquisition": [
                    {
                        "type": "git",
                        "url": "https://github.com/example/data.git",
                        "ref": COMMIT_C,
                        "subpath": "data",
                    }
                ],
                "input": {
                    "type": "directory",
                    "required_globs": ["*.xml"],
                    "allow_symlinks": False,
                },
                "execution": {
                    "type": "python-module",
                    "module": "example_converter.cli",
                    "args": ["{source}", "{output}"],
                    "network": "deny",
                },
                "output": {
                    "format": "text-fabric",
                    "required_paths": ["otype.tf", "oslots.tf"],
                },
            }
            for materializer_id in ids
        ],
    }


def _release(tag, *, draft=False, prerelease=False, release_id=1):
    return {
        "id": release_id,
        "tag_name": tag,
        "draft": draft,
        "prerelease": prerelease,
        "html_url": f"https://github.com/example/converter/releases/tag/{tag}",
    }


class FakeApi:
    def __init__(self, *, releases=None, refs=None, tags=None, files=None, fail=None):
        self.releases = list(releases or [])
        self.refs = dict(refs or {})
        self.tags = dict(tags or {})
        self.files = dict(files or {})
        self.fail = fail
        self.calls = []

    def list_releases(self, repository):
        self.calls.append(("list_releases", repository))
        if self.fail == "list_releases":
            raise RuntimeError("network down")
        return list(self.releases)

    def get_ref(self, repository, tag):
        self.calls.append(("get_ref", repository, tag))
        return self.refs[tag]

    def get_tag_object(self, repository, sha):
        self.calls.append(("get_tag_object", repository, sha))
        return self.tags[sha]

    def get_file(self, repository, path, ref):
        self.calls.append(("get_file", repository, path, ref))
        value = self.files[(path, ref)]
        if isinstance(value, Exception):
            raise value
        return value


def _valid_api(*, tag="v1.2.4", commit=COMMIT_B, manifest=None):
    manifest = manifest or _manifest(version=tag.removeprefix("v"))
    return FakeApi(
        releases=[_release(tag)],
        refs={tag: {"object": {"type": "commit", "sha": commit}}},
        files={("agora.materializer.json", commit): json.dumps(manifest).encode("utf-8")},
    )


class ReleaseTrackingSchemaTests(unittest.TestCase):
    def _schema(self):
        return json.loads((ROOT / "registry/schema/materializers.schema.json").read_text(encoding="utf-8"))

    def _validate(self, plugin):
        document = {"schema_version": 1, "plugins": [plugin]}
        return list(Draft202012Validator(self._schema()).iter_errors(document))

    def test_existing_entry_without_release_tracking_remains_valid(self):
        plugin = _plugin()
        plugin.pop("release_tracking")
        self.assertEqual(self._validate(plugin), [])

    def test_explicit_disabled_mode_is_valid(self):
        plugin = _plugin(release_tracking={"mode": "disabled"})
        self.assertEqual(self._validate(plugin), [])

    def test_github_stable_policy_is_valid(self):
        self.assertEqual(self._validate(_plugin()), [])

    def test_unknown_mode_channel_and_extra_properties_are_rejected(self):
        bad_mode = _plugin(release_tracking={"mode": "magic"})
        bad_channel = _plugin(release_tracking={"mode": "github-releases", "channel": "edge", "tag_prefix": "v"})
        extra = _plugin(release_tracking={"mode": "disabled", "surprise": True})
        self.assertTrue(self._validate(bad_mode))
        self.assertTrue(self._validate(bad_channel))
        self.assertTrue(self._validate(extra))

    def test_pseudepigrapha_tf_is_opted_into_stable_release_tracking(self):
        registry = yaml.safe_load((ROOT / "registry/materializers.yaml").read_text(encoding="utf-8"))
        plugin = next(item for item in registry["plugins"] if item["id"] == "pseudepigrapha-tf")
        self.assertEqual(
            plugin.get("release_tracking"),
            {"mode": "github-releases", "channel": "stable", "tag_prefix": "v"},
        )


class SemVerTests(unittest.TestCase):
    def test_stable_semver_parses_and_round_trips(self):
        value = _module().SemVer.parse("1.2.3")
        self.assertEqual(str(value), "1.2.3")

    def test_leading_zero_numeric_components_are_rejected(self):
        for text in ("01.2.3", "1.02.3", "1.2.03", "1.2.3-01"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    _module().SemVer.parse(text)

    def test_prerelease_precedence_matches_semver(self):
        parse = _module().SemVer.parse
        ordered = [
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-alpha.beta",
            "1.0.0-beta",
            "1.0.0-beta.2",
            "1.0.0-beta.11",
            "1.0.0-rc.1",
            "1.0.0",
        ]
        self.assertEqual(sorted(map(parse, reversed(ordered))), list(map(parse, ordered)))

    def test_build_metadata_does_not_change_precedence(self):
        parse = _module().SemVer.parse
        self.assertFalse(parse("1.2.3+one") < parse("1.2.3+two"))
        self.assertFalse(parse("1.2.3+two") < parse("1.2.3+one"))


class ReleaseSelectionTests(unittest.TestCase):
    def test_already_current_release_has_no_proposal(self):
        api = _valid_api(tag="v1.2.3", commit=COMMIT_A, manifest=_manifest(version="1.2.3"))
        self.assertIsNone(_module().discover_plugin_update(_plugin(), api))

    def test_newer_stable_release_produces_immutable_proposal(self):
        proposal = _module().discover_plugin_update(_plugin(), _valid_api())
        self.assertEqual(proposal.candidate_version, "1.2.4")
        self.assertEqual(proposal.candidate_ref, COMMIT_B)
        self.assertEqual(proposal.candidate_tag, "v1.2.4")

    def test_draft_release_is_ignored(self):
        api = FakeApi(releases=[_release("v1.2.4", draft=True)])
        self.assertIsNone(_module().discover_plugin_update(_plugin(), api))
        self.assertFalse(any(call[0] == "get_ref" for call in api.calls))

    def test_prerelease_release_is_ignored(self):
        api = FakeApi(releases=[_release("v2.0.0-rc.1", prerelease=True)])
        self.assertIsNone(_module().discover_plugin_update(_plugin(), api))

    def test_highest_semver_wins_independent_of_api_order(self):
        api = _valid_api(tag="v2.0.0", commit=COMMIT_B, manifest=_manifest(version="2.0.0"))
        api.releases = [_release("v1.9.9", release_id=2), _release("v2.0.0", release_id=1), _release("v1.10.0", release_id=3)]
        proposal = _module().discover_plugin_update(_plugin(), api)
        self.assertEqual(proposal.candidate_version, "2.0.0")

    def test_invalid_and_wrong_prefix_tags_are_ignored(self):
        api = FakeApi(releases=[_release("release-1.2.4"), _release("v01.2.4", release_id=2)])
        self.assertIsNone(_module().discover_plugin_update(_plugin(), api))

    def test_equal_version_duplicate_release_identity_fails_closed(self):
        api = FakeApi(releases=[_release("v1.2.4", release_id=1), _release("v1.2.4", release_id=2)])
        with self.assertRaises(_module().ReleaseDiscoveryError):
            _module().discover_plugin_update(_plugin(), api)

    def test_disabled_and_absent_tracking_make_no_network_calls(self):
        for tracking in ({"mode": "disabled"}, None):
            plugin = _plugin()
            if tracking is None:
                plugin.pop("release_tracking")
            else:
                plugin["release_tracking"] = tracking
            api = FakeApi(fail="list_releases")
            self.assertIsNone(_module().discover_plugin_update(plugin, api))
            self.assertEqual(api.calls, [])


class TagResolutionTests(unittest.TestCase):
    def test_lightweight_tag_resolves_directly_to_commit(self):
        api = FakeApi(refs={"v1.2.4": {"object": {"type": "commit", "sha": COMMIT_B}}})
        self.assertEqual(_module().resolve_tag_commit(api, "example/converter", "v1.2.4"), COMMIT_B)

    def test_annotated_tag_resolves_to_commit(self):
        api = FakeApi(
            refs={"v1.2.4": {"object": {"type": "tag", "sha": TAG_A}}},
            tags={TAG_A: {"object": {"type": "commit", "sha": COMMIT_B}}},
        )
        self.assertEqual(_module().resolve_tag_commit(api, "example/converter", "v1.2.4"), COMMIT_B)

    def test_nested_annotated_tags_resolve_recursively(self):
        api = FakeApi(
            refs={"v1.2.4": {"object": {"type": "tag", "sha": TAG_A}}},
            tags={
                TAG_A: {"object": {"type": "tag", "sha": TAG_B}},
                TAG_B: {"object": {"type": "commit", "sha": COMMIT_B}},
            },
        )
        self.assertEqual(_module().resolve_tag_commit(api, "example/converter", "v1.2.4"), COMMIT_B)

    def test_tag_cycle_fails_closed(self):
        api = FakeApi(
            refs={"v1.2.4": {"object": {"type": "tag", "sha": TAG_A}}},
            tags={TAG_A: {"object": {"type": "tag", "sha": TAG_A}}},
        )
        with self.assertRaises(_module().ReleaseDiscoveryError):
            _module().resolve_tag_commit(api, "example/converter", "v1.2.4")

    def test_unsupported_object_type_fails_closed(self):
        api = FakeApi(refs={"v1.2.4": {"object": {"type": "tree", "sha": COMMIT_B}}})
        with self.assertRaises(_module().ReleaseDiscoveryError):
            _module().resolve_tag_commit(api, "example/converter", "v1.2.4")

    def test_malformed_commit_sha_fails_closed(self):
        api = FakeApi(refs={"v1.2.4": {"object": {"type": "commit", "sha": "main"}}})
        with self.assertRaises(_module().ReleaseDiscoveryError):
            _module().resolve_tag_commit(api, "example/converter", "v1.2.4")


class CandidateManifestTests(unittest.TestCase):
    def _discover(self, manifest):
        return _module().discover_plugin_update(_plugin(), _valid_api(manifest=manifest))

    def test_valid_candidate_manifest_records_digest(self):
        proposal = self._discover(_manifest())
        self.assertRegex(proposal.manifest_sha256, r"^[0-9a-f]{64}$")

    def test_missing_or_malformed_manifest_fails_closed(self):
        for value in (KeyError("missing"), b"{not-json"):
            api = _valid_api()
            api.files[("agora.materializer.json", COMMIT_B)] = value
            with self.subTest(value=value):
                with self.assertRaises(_module().ReleaseDiscoveryError):
                    _module().discover_plugin_update(_plugin(), api)

    def test_schema_invalid_manifest_fails_closed(self):
        manifest = _manifest()
        del manifest["materializers"][0]["execution"]
        with self.assertRaises(_module().ReleaseDiscoveryError):
            self._discover(manifest)

    def test_plugin_id_drift_fails_closed(self):
        with self.assertRaises(_module().ReleaseDiscoveryError):
            self._discover(_manifest(plugin_id="other"))

    def test_repository_drift_fails_closed(self):
        with self.assertRaises(_module().ReleaseDiscoveryError):
            self._discover(_manifest(repository="other/repo"))

    def test_version_mismatch_fails_closed(self):
        with self.assertRaises(_module().ReleaseDiscoveryError):
            self._discover(_manifest(version="9.9.9"))

    def test_materializer_id_change_fails_closed(self):
        for ids in ([], ["example-to-tf", "new-one"], ["different"]):
            with self.subTest(ids=ids):
                with self.assertRaises(_module().ReleaseDiscoveryError):
                    self._discover(_manifest(materializers=ids))

    def test_invalid_highest_candidate_does_not_fall_back(self):
        api = _valid_api(tag="v2.0.0", commit=COMMIT_B, manifest=_manifest(version="9.9.9"))
        api.releases = [_release("v1.2.4", release_id=1), _release("v2.0.0", release_id=2)]
        with self.assertRaises(_module().ReleaseDiscoveryError):
            _module().discover_plugin_update(_plugin(), api)


class RegistryMutationTests(unittest.TestCase):
    def _registry_text(self):
        return (
            "schema_version: 1\n"
            "plugins:\n"
            "  # keep this comment\n"
            "  - id: example-converter\n"
            "    name: Example converter\n"
            "    description: Example.\n"
            "    repository: example/converter\n"
            f"    ref: {COMMIT_A}\n"
            "    version: 1.2.3\n"
            "    manifest: agora.materializer.json\n"
            "    package:\n"
            "      type: python-project\n"
            "      path: .\n"
            "      install_trust: explicit-code-execution\n"
            "    materializers: [example-to-tf]\n"
            "    disciplines: [digital-philology]\n"
            "    licenses: {software: MIT, data: upstream-dependent}\n"
            "    verification: {status: experimental}\n"
            "    release_tracking: {mode: github-releases, channel: stable, tag_prefix: v}\n"
        )

    def _proposal(self, **overrides):
        values = dict(
            plugin_id="example-converter",
            previous_version="1.2.3",
            previous_ref=COMMIT_A,
            candidate_version="1.2.4",
            candidate_tag="v1.2.4",
            candidate_ref=COMMIT_B,
            release_url="https://github.com/example/converter/releases/tag/v1.2.4",
            manifest_sha256="f" * 64,
        )
        values.update(overrides)
        return _module().ReleaseProposal(**values)

    def test_patch_changes_only_ref_and_version_and_preserves_other_bytes(self):
        original = self._registry_text()
        parsed = yaml.safe_load(original)
        changed = _module().apply_proposals_to_text(original, parsed, [self._proposal()])
        expected = original.replace(COMMIT_A, COMMIT_B).replace("version: 1.2.3", "version: 1.2.4")
        self.assertEqual(changed, expected)

    def test_repeated_application_is_idempotent(self):
        original = self._registry_text()
        parsed = yaml.safe_load(original)
        proposal = self._proposal()
        changed = _module().apply_proposals_to_text(original, parsed, [proposal])
        reparsed = yaml.safe_load(changed)
        self.assertEqual(_module().apply_proposals_to_text(changed, reparsed, [proposal]), changed)

    def test_stale_expected_old_value_fails_closed(self):
        original = self._registry_text()
        with self.assertRaises(_module().ReleaseDiscoveryError):
            _module().apply_proposals_to_text(
                original,
                yaml.safe_load(original),
                [self._proposal(previous_ref=COMMIT_C)],
            )

    def test_one_plugin_failure_prevents_partial_aggregate_result(self):
        good = _plugin()
        bad = _plugin(id="broken", repository="broken/repo", ref=COMMIT_C)
        registry = {"schema_version": 1, "plugins": [good, bad]}
        api = _valid_api()

        class MultiApi(FakeApi):
            def list_releases(self, repository):
                if repository == "broken/repo":
                    raise RuntimeError("network down")
                return super().list_releases(repository)

        multi = MultiApi(releases=api.releases, refs=api.refs, tags=api.tags, files=api.files)
        with self.assertRaises(_module().ReleaseDiscoveryError):
            _module().discover_updates(registry, multi)


class GitHubApiContractTests(unittest.TestCase):
    def test_list_releases_paginates_until_short_page(self):
        mod = _module()
        pages = [
            [_release(f"v1.0.{index}", release_id=index) for index in range(100)],
            [_release("v2.0.0", release_id=101)],
        ]
        calls = []

        def requester(url, *, headers, timeout):
            calls.append((url, headers, timeout))
            page = 1 if "page=1" in url else 2
            return json.dumps(pages[page - 1]).encode("utf-8")

        api = mod.GitHubApi(token="secret", requester=requester, timeout=7)
        releases = api.list_releases("example/converter")
        self.assertEqual(len(releases), 101)
        self.assertEqual(len(calls), 2)

    def test_client_sends_auth_version_accept_headers_and_timeout(self):
        mod = _module()
        observed = {}

        def requester(url, *, headers, timeout):
            observed.update(url=url, headers=headers, timeout=timeout)
            return b"[]"

        api = mod.GitHubApi(token="secret", requester=requester, timeout=9)
        api.list_releases("example/converter")
        lowered = {key.lower(): value for key, value in observed["headers"].items()}
        self.assertEqual(lowered["authorization"], "Bearer secret")
        self.assertIn("github+json", lowered["accept"])
        self.assertIn("x-github-api-version", lowered)
        self.assertEqual(observed["timeout"], 9)


class WorkflowContractTests(unittest.TestCase):
    def test_scheduled_workflow_has_manual_dispatch_minimal_writes_and_no_auto_merge(self):
        path = ROOT / ".github/workflows/materializer-release-updates.yml"
        self.assertTrue(path.is_file(), "release updater workflow is missing")
        text = path.read_text(encoding="utf-8")
        self.assertIn("schedule:", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("contents: write", text)
        self.assertIn("pull-requests: write", text)
        self.assertNotIn("gh pr merge", text)
        self.assertNotIn("enable-auto-merge", text)

    def test_workflow_validates_before_push_and_uses_one_fixed_bot_branch(self):
        path = ROOT / ".github/workflows/materializer-release-updates.yml"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        validate = text.index("validate_registry.py")
        push = text.index("git push")
        self.assertLess(validate, push)
        self.assertGreaterEqual(text.count("automation/materializer-releases"), 2)

    def test_workflow_uses_github_token_not_pat_and_discovery_never_installs_candidate(self):
        path = ROOT / ".github/workflows/materializer-release-updates.yml"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("GITHUB_TOKEN", text)
        self.assertNotIn("PERSONAL_ACCESS_TOKEN", text)
        self.assertNotIn("PAT_TOKEN", text)
        self.assertNotIn("agora_install_materializer.py install", text)
        self.assertNotIn("pip install .reference", text)


if __name__ == "__main__":
    unittest.main()
