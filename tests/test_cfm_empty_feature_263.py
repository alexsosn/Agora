"""#263 RED: keep valid *empty* TF features available in CFM offline caches.

Context-Fabric 0.5.7 writes empty-feature names into meta.json but skips their
arrays; the actual published Pseudepigrapha v1.0.0 reload fails on prefix_utf8.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/context-fabric/src"))

from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.release_snapshots import ReleaseSnapshots

HAS_CFABRIC = importlib.util.find_spec("cfabric") is not None

FEATURES = {
    "otype.tf": b"@node\n@valueType=str\n\n1-2\tword\n3\tdocument\n",
    "oslots.tf": b"@edge\n\n3\t1-2\n",
    "otext.tf": b"@config\n@sectionTypes=document\n@sectionFeatures=title\n\n",
    "prefix_utf8.tf": b"@node\n@valueType=str\n\n",
    "heading@en.tf": b"@node\n@valueType=str\n\n",
    "empty_int.tf": b"@node\n@valueType=int\n\n",
    "nonempty.tf": b"@node\n@valueType=str\n\n1\treal\n",
}


class EmptyCFMFeature263Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as z:
            for name, payload in FEATURES.items():
                z.writestr(name, payload)
        self.archive = self.root / "dataset.zip"
        self.archive.write_bytes(data.getvalue())
        self.store = GitStore(self.root / "cache", min_free_bytes=0)
        self.snapshots = ReleaseSnapshots(self.store)
        self.identity = {
            "resource_id": "empty-cfm-regression",
            "repository": "example/empty-cfm",
            "release_tag": "v1.0.0",
            "version": "1.0",
            "asset_sha256": hashlib.sha256(data.getvalue()).hexdigest(),
        }
        self.prepared = self.snapshots.install(self.archive, **self.identity)

    def _compiled(self, *, nodes=None):
        path = self.prepared.path / ".cfm" / "1"
        features = path / "features"
        features.mkdir(parents=True)
        meta = {
            "cfm_version": "1", "max_node": 3, "max_slot": 2,
            "features": {"node": nodes if nodes is not None else ["prefix_utf8", "empty_int"], "edge": []},
        }
        (path / "meta.json").write_text(json.dumps(meta))
        return features

    @unittest.skipUnless(HAS_CFABRIC, "requires Context-Fabric runtime; exercised in native release consumer CI")
    def test_reopens_empty_string_and_integer_features_without_touching_source(self):
        from cfabric.storage.string_pool import StringPool, IntFeatureArray

        features = self._compiled()
        self.assertFalse((features / "prefix_utf8_strings.npy").exists())
        reopened = self.snapshots.prepare(**self.identity)
        self.assertEqual(reopened.path, self.prepared.path)
        pool = StringPool.load(str(features / "prefix_utf8"))
        self.assertIsNone(pool.get(1))
        self.assertIsNone(pool.get(3))
        numbers = IntFeatureArray.load(str(features / "empty_int.npy"))
        self.assertIsNone(numbers.get(1))
        self.assertEqual((reopened.path / "prefix_utf8.tf").read_bytes(), FEATURES["prefix_utf8.tf"])
        self.assertEqual((reopened.path / "empty_int.tf").read_bytes(), FEATURES["empty_int.tf"])

    @unittest.skipUnless(HAS_CFABRIC, "requires Context-Fabric runtime; exercised in native release consumer CI")
    @unittest.skipUnless(HAS_CFABRIC, "requires Context-Fabric runtime; exercised in native release consumer CI")
    def test_language_qualified_empty_tf_feature_compiles_without_rejection(self):
        # CFM itself supports name@en section variants. Rejecting '@' in the
        # verified feature basename would make a valid corpus unreloadable.
        from cfabric.storage.string_pool import StringPool

        features = self._compiled(nodes=["heading@en"])
        self.snapshots.prepare(**self.identity)
        self.assertIsNone(StringPool.load(str(features / "heading@en")).get(1))

    @unittest.skipUnless(HAS_CFABRIC, "requires Context-Fabric runtime; exercised in native release consumer CI")
    def test_verified_cached_reinstall_also_repairs_valid_empty_compiled_features(self):
        # Resolver source_mode=require-fresh always calls install(), even for
        # a managed snapshot whose verified source bytes are unchanged.
        # Reinstall must not bypass the same sealed-source CFM compatibility
        # repair used by offline prepare().
        from cfabric.storage.string_pool import StringPool

        features = self._compiled(nodes=["prefix_utf8"])
        self.assertFalse((features / "prefix_utf8_strings.npy").exists())
        result = self.snapshots.install(self.archive, **self.identity)
        self.assertEqual(result.path, self.prepared.path)
        self.assertIsNone(StringPool.load(str(features / "prefix_utf8")).get(1))
        self.assertEqual((result.path / "prefix_utf8.tf").read_bytes(), FEATURES["prefix_utf8.tf"])

    def test_missing_binary_for_nonempty_source_fails_closed(self):
        self._compiled(nodes=["nonempty"])
        with self.assertRaisesRegex(ValueError, "nonempty|empty|integrity"):
            self.snapshots.prepare(**self.identity)

    @unittest.skipUnless(HAS_CFABRIC, "requires Context-Fabric runtime; exercised in native release consumer CI")
    def test_symlink_in_compiled_path_is_not_followed(self):
        feature_dir = self._compiled()
        feature_dir.rename(self.root / "outside")
        feature_dir.symlink_to(self.root / "outside", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink|unsafe"):
            self.snapshots.prepare(**self.identity)
        self.assertEqual([], list((self.root / "outside").iterdir()))

    def test_opaque_derived_cache_without_manifest_does_not_require_cfabric(self):
        cfm = self.prepared.path / ".cfm"
        cfm.mkdir()
        (cfm / "private-cache.bin").write_bytes(b"derived")
        original = __import__

        def guard(name, *args, **kwargs):
            if name == "cfabric" or name.startswith("cfabric."):
                raise AssertionError("data-only cache must not require Context-Fabric")
            return original(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=guard):
            reopened = self.snapshots.prepare(**self.identity)
        self.assertEqual(reopened.path, self.prepared.path)

    def test_compiled_corpus_without_section_schema_needs_no_index(self):
        from agora_context_fabric.cfm_compat import restore_compiled_section_index

        fabric = SimpleNamespace(_loaded_from_cfm=True, sectionTypes=[], sectionFeats=[])
        api = SimpleNamespace(C=SimpleNamespace())
        loader = SimpleNamespace(get=lambda logical_name: (fabric, api))
        self.assertFalse(restore_compiled_section_index(loader, "no-sections"))
        self.assertFalse(hasattr(api.C, "sections"))

    @unittest.skipUnless(HAS_CFABRIC, "requires Context-Fabric runtime; exercised in native release consumer CI")
    def test_mismatched_or_partial_compiled_files_fail_closed(self):
        features = self._compiled(nodes=["prefix_utf8"])
        (features / "prefix_utf8_idx.npy").write_bytes(b"partial")
        with self.assertRaisesRegex(ValueError, "partial|incomplete|integrity"):
            self.snapshots.prepare(**self.identity)

    @unittest.skipUnless(HAS_CFABRIC, "requires Context-Fabric runtime; exercised in native release consumer CI")
    def test_mixed_integer_and_string_arrays_fail_closed(self):
        from cfabric.storage.string_pool import IntFeatureArray
        features = self._compiled(nodes=["prefix_utf8"])
        IntFeatureArray.from_dict({}, 3).save(str(features / "prefix_utf8.npy"))
        (features / "prefix_utf8_idx.npy").write_bytes(b"bad-partial")
        with self.assertRaisesRegex(ValueError, "mixed|partial"):
            self.snapshots.prepare(**self.identity)

    @unittest.skipUnless(HAS_CFABRIC, "requires Context-Fabric runtime; exercised in native release consumer CI")
    def test_malformed_compiled_metadata_fails_closed(self):
        features = self._compiled()
        meta = features.parent / "meta.json"
        parsed = json.loads(meta.read_text())
        parsed["features"] = []
        meta.write_text(json.dumps(parsed))
        with self.assertRaisesRegex(ValueError, "feature manifest"):
            self.snapshots.prepare(**self.identity)

    @unittest.skipUnless(HAS_CFABRIC, "requires Context-Fabric runtime; exercised in native release consumer CI")
    def test_original_empty_feature_metadata_is_preserved(self):
        features = self._compiled(nodes=["prefix_utf8"])
        self.snapshots.prepare(**self.identity)
        meta = json.loads((features / "prefix_utf8_meta.json").read_text())
        self.assertEqual(meta["value_type"], "str")
        self.assertEqual(meta["name"], "prefix_utf8")
        self.assertEqual(meta["kind"], "node")

    def test_tampered_immutable_source_is_never_blessed_by_derived_repair(self):
        self._compiled()
        (self.prepared.path / "prefix_utf8.tf").write_bytes(b"@node\n\n1\tforgery\n")
        with self.assertRaisesRegex(ValueError, "integrity|mismatch"):
            self.snapshots.prepare(**self.identity)


if __name__ == "__main__":
    unittest.main()
