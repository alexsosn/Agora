"""#226 RED: the released Pseudepigrapha *corpus* is not its converter."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "plugins/context-fabric/src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agora_context_fabric.catalog import Catalog
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.resolver import ContextFabricResolver
from agora_context_fabric.service import ContextFabricService

ID = "pseudepigrapha"
PIN = {
    "release_tag": "v1.0.0",
    "asset_name": "tf-1.0.zip",
    "sha256": "d2dfad7e643699617a9493b9f5d724868f8027dd5f2e88bd558451e3e7819b7a",
    "compressed_bytes": 9632449,
    "version": "1.0",
}


class PseudepigraphaRegistration226Tests(unittest.TestCase):
    def setUp(self):
        resources = yaml.safe_load((ROOT / "registry/resources.yaml").read_text())
        self.row = next(x for x in resources["resources"] if x["id"] == ID)
        self.catalog = Catalog.from_registry(ROOT)
        self.bundled = Catalog.from_plugin_root(ROOT / "plugins/context-fabric")
        self.schema = json.loads((ROOT / "registry/schema/resources.schema.json").read_text())

    def test_published_corpus_is_pinned_and_separate_from_converter(self):
        res = self.catalog.get(ID)
        self.assertEqual(res, self.bundled.get(ID))
        self.assertEqual(res.kind, "corpus")
        self.assertEqual(res.release_archive, PIN)
        self.assertEqual(res.acquisition_strategy, "github-release-archive")
        self.assertEqual(res.repository, "alexsosn/Pseudepigrapha-TF")
        self.assertEqual(res.ref, "7c4b757bb543a110ae9a252d1281835859136852")
        self.assertNotIn("tf_path", self.row["upstream"])
        self.assertNotIn("release", self.row["acquisition"])
        self.assertEqual(self.row["licenses"]["data"], "CC-BY-4.0")
        self.assertEqual(self.row["licenses"]["redistribution"], "permitted")
        self.assertEqual(self.row["licenses"]["evidence"]["status"], "resolved")
        self.assertFalse(list(Draft202012Validator(self.schema).iter_errors({
            "schema_version": 1, "resources": [self.row]
        })))
        mat = yaml.safe_load((ROOT / "registry/materializers.yaml").read_text())
        self.assertIn("pseudepigrapha-tf", {r["id"] for r in mat["plugins"]})

    def test_bad_archive_identity_fails_both_schema_and_consumer(self):
        changes = (
            lambda r: r["acquisition"]["archive"].pop("sha256"),
            lambda r: r["acquisition"]["archive"].update(release_tag="latest"),
            lambda r: r["acquisition"]["archive"].update(asset_name="../evil.zip"),
            lambda r: r["acquisition"]["archive"].update(version="../../wrong"),
            lambda r: r["acquisition"].update(release={"sha256": "0" * 64}),
        )
        for f in changes:
            row = copy.deepcopy(self.row)
            f(row)
            with self.subTest(archive=row["acquisition"]):
                self.assertTrue(list(Draft202012Validator(self.schema).iter_errors({
                    "schema_version": 1, "resources": [row]
                })))
                with self.assertRaises(ValueError):
                    Catalog._resources_from_document({"resources": [row]})

    def test_describe_and_offline_cold_miss_never_clone_or_download(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GitStore(Path(directory) / "cache", min_free_bytes=0)
            resolver = ContextFabricResolver(self.catalog, store)
            service = ContextFabricService(self.catalog, resolver, object())
            with patch.object(store, "ensure_metadata", side_effect=AssertionError("must not clone OCP/converter")):
                self.assertEqual(resolver.corpus_versions(ID), ("1.0",))
                self.assertEqual(resolver.default_corpus_version(ID), "1.0")
                description = service.describe_resource(ID)
                self.assertEqual(description["default_version"], "1.0")
                self.assertEqual(description["acquisition"]["archive"], PIN)
                with store.source_policy("offline"), patch(
                    "agora_context_fabric.release_download.download_pinned_release",
                    side_effect=AssertionError("offline must not touch network"),
                ):
                    with self.assertRaisesRegex(FileNotFoundError, "offline"):
                        resolver.prepare(ID)
            self.assertEqual([], list(store.repositories_dir.iterdir()))

    def test_real_public_consumer_is_still_required_for_semantics(self):
        workflow = (ROOT / ".github/workflows/pseudepigrapha-registered-corpus.yml").read_text()
        smoke = (ROOT / "scripts/smoke_pseudepigrapha_release_226.py").read_text()
        for marker in ("test_pseudepigrapha_registration_226.py",
                       "smoke_pseudepigrapha_release_226.py", "persist-credentials: false"):
            self.assertIn(marker, workflow)
        for marker in ("source_ref", "1En__Ethiopic", "generated_translation",
                       "witness", "translation_of", 'source_mode="offline"'):
            self.assertIn(marker, smoke)
        self.assertNotIn("upload-artifact", workflow)


if __name__ == "__main__":
    unittest.main()
