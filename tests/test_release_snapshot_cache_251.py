"""Issue #251 RED: immutable, lease-aware archive snapshot persistence."""
from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins/context-fabric/src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.release_snapshots import ReleaseSnapshots


FEATURES = {
    "otype.tf": b"@node\n@valueType=str\n\n1-2\tword\n3\tdocument\n",
    "oslots.tf": b"@edge\n\n3\t1-2\n",
    "otext.tf": b"@config\n@sectionTypes=document\n@sectionFeatures=title\n@fmt:text-orig-full={norm} \n\n",
    "norm.tf": b"@node\n@valueType=str\n\n1\tKing\n2\tbook\n",
    "title.tf": b"@node\n@valueType=str\n\n3\tSample\n",
}


def zipped(entries=FEATURES):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


class PinnedReleaseSnapshot251Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.store = GitStore(self.root / "cache", min_free_bytes=0)
        self.snapshots = ReleaseSnapshots(self.store)
        self.asset = self.root / "corpus.zip"
        blob = zipped()
        self.asset.write_bytes(blob)
        self.identity = dict(
            resource_id="pseudepigrapha",
            repository="alexsosn/Pseudepigrapha-TF",
            release_tag="v1.0.0",
            version="1.0",
            asset_sha256=hashlib.sha256(blob).hexdigest(),
        )

    def install(self, **kwargs):
        return self.snapshots.install(self.asset, **{**self.identity, **kwargs})

    def prepare(self, **kwargs):
        return self.snapshots.prepare(**{**self.identity, **kwargs})

    def test_stable_id_attested_receipt_idempotent_restart_and_cache_management(self):
        first = self.install()
        self.assertEqual(first.resource_id, "pseudepigrapha")
        self.assertEqual(first.version, "1.0")
        self.assertEqual(first.source_revision, self.identity["asset_sha256"])
        self.assertEqual(first.path, (
            self.store.snapshots_dir / "pseudepigrapha" /
            self.identity["asset_sha256"] / "corpora" / "__root__"
        ))
        self.assertEqual({*FEATURES}, {p.name for p in first.path.glob("*.tf")})
        self.assertEqual(first.path, self.install().path)
        self.assertEqual(first.path, ReleaseSnapshots(GitStore(
            self.root / "cache", min_free_bytes=0
        )).prepare(**self.identity).path)
        receipt = json.loads((first.path / ".agora-release.json").read_text())
        self.assertEqual(receipt["repository"], "alexsosn/Pseudepigrapha-TF")
        self.assertEqual(receipt["release_tag"], "v1.0.0")
        self.assertEqual(receipt["asset_sha256"], self.identity["asset_sha256"])
        self.assertEqual(set(receipt["files"]), set(FEATURES))
        entries = self.store.cache_entries("pseudepigrapha")
        self.assertEqual(1, len(entries))
        self.assertEqual("pseudepigrapha", entries[0]["resource_id"])
        with self.store.acquire_cache_lease(first.path):
            removed = self.store.remove_cache_object(first.path)
            self.assertEqual(1, removed["skipped_in_use"])
            self.assertTrue(first.path.is_dir())
        removed = self.store.remove_cache_object(first.path)
        self.assertEqual(1, removed["removed_entries"])
        self.assertFalse(first.path.exists())
        with self.assertRaises(FileNotFoundError):
            self.prepare()

    def test_tampered_feature_and_receipt_rejected_even_on_reinstall(self):
        prepared = self.install()
        (prepared.path / "norm.tf").write_bytes(b"@node\n\n1\tbad\n")
        with self.assertRaisesRegex(ValueError, "integrity|mismatch"):
            self.prepare()
        with self.assertRaisesRegex(ValueError, "integrity|mismatch"):
            self.install()
        (prepared.path / "norm.tf").write_bytes(FEATURES["norm.tf"])
        receipt = prepared.path / ".agora-release.json"
        receipt.write_text(receipt.read_text().replace("v1.0.0", "v9.9.9"))
        with self.assertRaisesRegex(ValueError, "integrity|mismatch"):
            self.prepare()

    def test_mismatched_release_provenance_and_asset_revision_do_not_alias(self):
        self.install()
        for alternate in (
            dict(release_tag="v1.0.1"),
            dict(repository="other/corpus"),
            dict(version="9.0"),
        ):
            with self.subTest(alternate=alternate):
                with self.assertRaisesRegex(ValueError, "identity|mismatch"):
                    self.prepare(**alternate)
                with self.assertRaisesRegex(ValueError, "identity|mismatch"):
                    self.install(**alternate)
        with self.assertRaises(FileNotFoundError):
            self.prepare(asset_sha256="a" * 64)

    def test_bad_archive_hash_missing_warp_and_illegal_id_leave_no_index(self):
        for bad in ("../escaped", "local-deadbeef", "a/b", ".", ""):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.install(resource_id=bad)
        with self.assertRaisesRegex(ValueError, "sha256"):
            self.install(asset_sha256="0" * 64)
        self.asset.write_bytes(zipped({"otype.tf": FEATURES["otype.tf"]}))
        broken_hash = hashlib.sha256(self.asset.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "warp"):
            self.install(asset_sha256=broken_hash)
        self.assertEqual([], self.store.cache_entries())
        self.assertEqual([], list(self.store.snapshots_dir.rglob(".agora-release.json")))
        self.assertEqual([], list(self.store.tmp_dir.iterdir()))

    def test_publication_index_failure_removes_snapshot_and_sidecars(self):
        destination = self.store.snapshots_dir / "pseudepigrapha" / self.identity[
            "asset_sha256"
        ] / "corpora" / "__root__"
        with patch.object(self.store, "touch_cache_object", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.install()
        self.assertFalse(destination.exists())
        self.assertFalse(self.store._meta_path(destination).exists())
        self.assertFalse(self.store._access_path(destination).exists())
        self.assertEqual([], self.store.cache_entries())

    def test_non_network_snapshot_does_not_forge_canonical_discovery(self):
        self.install()
        from agora_context_fabric.catalog import Catalog
        from agora_context_fabric.local_import import LocalCatalog, LocalImports
        catalog = LocalCatalog(Catalog([]), LocalImports(self.store))
        self.assertEqual([], catalog.ids(), "cache install must not invent a corpus catalog entry")


if __name__ == "__main__":
    unittest.main()
