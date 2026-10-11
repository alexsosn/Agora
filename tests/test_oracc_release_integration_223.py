"""#223: published ORACC-TF corpus uses the shared typed archive resolver."""
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
from scripts.audit_context_fabric_sources import audit_catalog

ID = "assyrian-royal-inscriptions"
PIN = dict(
    release_tag="v1.0.0",
    asset_name="assyrian-royal-inscriptions-1.0.0.zip",
    sha256="788f580604e30054fab34c4c3ea60ec3eb4f399412f1da90f778469d03507468",
    compressed_bytes=41285702,
    version="0.4.0",
)


class ORACCGenericRelease223Tests(unittest.TestCase):
    def setUp(self):
        doc = yaml.safe_load((ROOT / "registry/resources.yaml").read_text(encoding="utf-8"))
        self.row = next(r for r in doc["resources"] if r["id"] == ID)
        self.schema = json.loads((ROOT / "registry/schema/resources.schema.json").read_text())
        self.catalog = Catalog.from_registry(ROOT)
        self.bundled = Catalog.from_plugin_root(ROOT / "plugins/context-fabric")
        self.resource = self.catalog.get(ID)

    def test_public_asset_and_distinct_release_tf_versions_are_immutable(self):
        self.assertEqual(self.resource, self.bundled.get(ID))
        self.assertEqual(self.resource.acquisition_strategy, "github-release-archive")
        self.assertEqual(self.resource.release_archive, PIN)
        self.assertEqual(self.resource.repository, "alexsosn/ORACC-TF")
        self.assertEqual(self.resource.ref, "60db4b724a687c0f425e78eae924fce89454e106")
        self.assertEqual(self.row["licenses"]["redistribution"], "restricted")
        self.assertEqual(self.row["licenses"]["evidence"]["status"], "component-specific")
        self.assertTrue(all("/blob/v1.0.0/" in url for url in self.row["licenses"]["evidence"]["sources"]))
        self.assertNotIn("release", self.row["acquisition"])
        self.assertNotIn("tf_path", self.row["upstream"])
        self.assertFalse(list(Draft202012Validator(self.schema).iter_errors({
            "schema_version": 1, "resources": [self.row],
        })))

    def test_missing_or_mutated_release_identity_and_legacy_conflict_fail_closed(self):
        def remove_sha(row):
            row["acquisition"]["archive"].pop("sha256")
        mutations = (
            remove_sha,
            lambda row: row["acquisition"].update(release={"tag": "v1.0.0"}),
            lambda row: row["acquisition"]["archive"].update(version="../other"),
            lambda row: row["acquisition"]["archive"].update(asset_name="../evil.zip"),
        )
        for mutate in mutations:
            row = copy.deepcopy(self.row)
            mutate(row)
            with self.subTest(acquisition=row["acquisition"]):
                with self.assertRaises(ValueError):
                    Catalog._resources_from_document({"resources": [row]})
                self.assertTrue(list(Draft202012Validator(self.schema).iter_errors({
                    "schema_version": 1, "resources": [row],
                })))

    def test_versions_discovery_and_offline_cold_miss_do_not_clone_builder(self):
        with tempfile.TemporaryDirectory() as work:
            store = GitStore(Path(work) / "cache", min_free_bytes=0)
            resolver = ContextFabricResolver(self.catalog, store)
            service = ContextFabricService(self.catalog, resolver, object())
            with patch.object(store, "ensure_metadata", side_effect=AssertionError("no Git builder clone")):
                self.assertEqual(resolver.corpus_versions(ID), ("0.4.0",))
                self.assertEqual(resolver.default_corpus_version(ID), "0.4.0")
                row = service.describe_resource(ID)
                self.assertEqual(row["default_version"], "0.4.0")
                self.assertEqual(row["acquisition"]["archive"], PIN)
                self.assertEqual(row["source"]["archive"], PIN)
                with store.source_policy("offline"):
                    with self.assertRaisesRegex(FileNotFoundError, "offline"):
                        resolver.prepare(ID)
            self.assertEqual([], list(store.repositories_dir.iterdir()))

    def test_git_audit_reports_release_without_cloning_giant_builder(self):
        class NoGit:
            def ensure_metadata(self, *args, **kwargs):
                raise AssertionError("release audit must not clone")
        report = audit_catalog(Catalog([self.resource]), NoGit())
        self.assertTrue(report["ok"])
        self.assertEqual(report["skipped"], 1)
        self.assertEqual(report["resources"][0]["asset_sha256"], PIN["sha256"])

    def test_real_published_byte_oracle_and_reopen_are_required_in_ci(self):
        workflow = (ROOT / ".github/workflows/oracc-release-consumer.yml").read_text()
        smoke = (ROOT / "scripts/smoke_oracc_release_223.py").read_text()
        for needle in ("scripts/smoke_oracc_release_223.py",
                       "test_oracc_release_integration_223.py",
                       "persist-credentials: false"):
            self.assertIn(needle, workflow)
        for needle in ('source_mode="require-fresh"', 'source_mode="offline"',
                       "Q001801.1", "riao/ria1:Q001801",
                       "E₂", "𒂍", "translation_line", "fresh.unload"):
            self.assertIn(needle, smoke)


if __name__ == "__main__":
    unittest.main()
