"""#251 RED: a release-backed resource is typed, pinned, and never clones Git."""
from __future__ import annotations

import copy
import hashlib
import io
import sys
import tempfile
import unittest
import zipfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

import json
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "plugins/context-fabric/src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agora_context_fabric.catalog import Catalog
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.resolver import ContextFabricResolver

FEATURES = {
    "otype.tf": b"@node\n\n1-2\tword\n3\tdocument\n",
    "oslots.tf": b"@edge\n\n3\t1-2\n",
    "otext.tf": b"@config\n@sectionTypes=document\n@sectionFeatures=title\n",
    "title.tf": b"@node\n\n3\tTest\n",
}

def zip_bytes():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in FEATURES.items():
            archive.writestr(name, data)
    return buffer.getvalue()


class ReleaseCorpusStrategy251Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        data = zip_bytes()
        self.archive = self.root / "tf-1.0.zip"
        self.archive.write_bytes(data)
        self.digest = hashlib.sha256(data).hexdigest()
        self.pin = dict(
            release_tag="v1.0.0", asset_name="tf-1.0.zip",
            sha256=self.digest, compressed_bytes=len(data), version="1.0",
        )
        resources = yaml.safe_load((ROOT / "registry/resources.yaml").read_text())["resources"]
        self.row = copy.deepcopy(next(r for r in resources if r["id"] == "bhsa"))
        self.row["id"] = "test-release"
        self.row["name"] = "Test release TF"
        self.row["upstream"] = {"repository": "alexsosn/Pseudepigrapha-TF"}
        self.row["acquisition"] = {"strategy": "github-release-archive", "archive": self.pin}
        self.schema = json.loads((ROOT / "registry/schema/resources.schema.json").read_text())

    def resource(self):
        return Catalog._resources_from_document({"resources": [self.row]})[0]

    def resolver(self):
        store = GitStore(self.root / "cache", min_free_bytes=0)
        catalog = Catalog([self.resource()])
        return ContextFabricResolver(catalog, store), store

    def test_canonical_schema_and_consumer_accept_only_complete_pinned_archive_spec(self):
        document = {"schema_version": 1, "resources": [self.row]}
        self.assertEqual([], list(Draft202012Validator(self.schema).iter_errors(document)))
        resource = self.resource()
        self.assertEqual("github-release-archive", resource.acquisition_strategy)
        self.assertEqual(self.pin, resource.release_archive)
        self.assertEqual("alexsosn/Pseudepigrapha-TF", resource.repository)

    def test_missing_unsafe_or_noncorpus_archive_specs_fail_before_discovery(self):
        for bad in (
            {"sha256": "bad"},
            {"asset_name": "../script.zip"},
            {"asset_name": "source.py"},
            {"compressed_bytes": 0},
            {"release_tag": "latest"},
            {"version": "../../oops"},
            {"unsupported": "value"},
        ):
            with self.subTest(bad=bad):
                row = copy.deepcopy(self.row)
                row["acquisition"]["archive"].update(bad)
                self.assertTrue(list(Draft202012Validator(self.schema).iter_errors({
                    "schema_version": 1, "resources": [row]
                })))
                with self.assertRaises(ValueError):
                    Catalog._resources_from_document({"resources": [row]})
        for missing in self.pin:
            row = copy.deepcopy(self.row)
            del row["acquisition"]["archive"][missing]
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                Catalog._resources_from_document({"resources": [row]})
        row = copy.deepcopy(self.row)
        row["kind"] = "collection"
        with self.assertRaises(ValueError):
            Catalog._resources_from_document({"resources": [row]})

    def test_exact_pinned_public_release_real_tf_resolver_workflow_is_required(self):
        workflow = (
            ROOT / ".github/workflows/pseudepigrapha-release-resolver.yml"
        ).read_text(encoding="utf-8")
        for required in (
            "tf-1.0.zip",
            "PINNED_RELEASE_ASSETS",
            "ContextFabricResolver",
            "source_policy(\"offline\")",
            "Fabric(",
            "source_revision",
            "test_release_corpus_strategy_251",
            "persist-credentials: false",
            "no public corpus registration",
        ):
            self.assertIn(required, workflow)
        self.assertNotIn("upload-artifact", workflow)

    def test_actual_catalog_versions_do_not_clone_or_fetch(self):
        resolver, store = self.resolver()
        with patch.object(store, "ensure_metadata", side_effect=AssertionError("Git clone forbidden")):
            self.assertEqual(("1.0",), resolver.corpus_versions("test-release"))
            self.assertEqual("1.0", resolver.default_corpus_version("test-release"))

    def test_prepare_exact_pinned_asset_offline_restart_without_git(self):
        resolver, store = self.resolver()
        calls = []
        @contextmanager
        def fake_download(**kwargs):
            calls.append(kwargs)
            yield self.archive

        with patch("agora_context_fabric.release_download.download_pinned_release", fake_download):
            with patch.object(store, "ensure_metadata", side_effect=AssertionError("Git clone forbidden")):
                prepared = resolver.prepare("test-release")
        self.assertEqual("test-release", prepared.resource_id)
        self.assertEqual("1.0", prepared.version)
        self.assertEqual(self.digest, prepared.source_revision)
        self.assertEqual(set(FEATURES), {p.name for p in prepared.path.glob("*.tf")})
        self.assertEqual(1, len(calls))
        self.assertEqual(self.digest, calls[0]["asset_sha256"])
        self.assertEqual("v1.0.0", calls[0]["release_tag"])
        self.assertEqual(len(self.archive.read_bytes()), calls[0]["asset_bytes"])
        self.archive.unlink()
        reopened_resolver = ContextFabricResolver(Catalog([self.resource()]), GitStore(
            self.root / "cache", min_free_bytes=0
        ))
        with reopened_resolver.store.source_policy("offline"), patch(
            "agora_context_fabric.release_download.download_pinned_release",
            side_effect=AssertionError("offline touched network")
        ):
            cached = reopened_resolver.prepare("test-release", source_revision=self.digest)
        self.assertEqual(prepared.path, cached.path)
        self.assertEqual(self.digest, cached.source_revision)

    def test_offline_cache_miss_and_wrong_revision_version_reject_before_network(self):
        resolver, store = self.resolver()
        with store.source_policy("offline"), patch(
            "agora_context_fabric.release_download.download_pinned_release",
            side_effect=AssertionError("offline network")
        ):
            with self.assertRaisesRegex(FileNotFoundError, "offline|cached"):
                resolver.prepare("test-release")
        with patch("agora_context_fabric.release_download.download_pinned_release",
                   side_effect=AssertionError("bad pin should fail before network")):
            for params in (
                {"version": "9.9"},
                {"source_revision": "a" * 64},
                {"source_revision": "a" * 40},
                {"member_id": "foo"},
            ):
                with self.subTest(params=params), self.assertRaises(ValueError):
                    resolver.prepare("test-release", **params)

    def test_cached_corruption_fails_closed_without_implicit_re_download(self):
        resolver, _ = self.resolver()
        @contextmanager
        def fake_download(**kwargs):
            yield self.archive
        with patch("agora_context_fabric.release_download.download_pinned_release", fake_download):
            prepared = resolver.prepare("test-release")
        (prepared.path / "title.tf").write_bytes(b"@node\n\n3\tchanged\n")
        with patch("agora_context_fabric.release_download.download_pinned_release",
                   side_effect=AssertionError("corruption must not be suppressed")):
            with self.assertRaisesRegex(ValueError, "integrity"):
                resolver.prepare("test-release")


if __name__ == "__main__":
    unittest.main()
