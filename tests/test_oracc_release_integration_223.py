"""#223 RED-first contracts for immutable ORACC release ZIP -> managed TF corpus."""
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
SOURCE = ROOT / "plugins/context-fabric/src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from agora_context_fabric.catalog import Catalog, ResourceSpec
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.resolver import ContextFabricResolver
from agora_context_fabric.release_resource import ReleaseArchiveAcquirer

FEATURES = {
    "otype.tf": b"@node\n1\tword\n",
    "oslots.tf": b"@edge\n1\t1\n",
    "otext.tf": b"@config\n@fmt=text\n",
    "form.tf": b"@node\n1\tE2\n",
}


def archive_bytes(*, manifest_updates=None):
    manifest = dict(
        dataset="assyrian-royal-inscriptions", release_id="1.0.0",
        tf_version="1.0.0", tf_root="tf/1.0.0",
        builder_commit="1" * 40, source_state="sha256:" + "2" * 64,
    )
    manifest.update(manifest_updates or {})
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("app/config.yaml", "dataDisplay: {}")
        archive.writestr("docs/README.md", "test")
        for name, content in FEATURES.items():
            archive.writestr("tf/1.0.0/" + name, content)
    return output.getvalue()


class ReleaseArchive223Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = GitStore(self.root / "store", min_free_bytes=0)
        self.payload = archive_bytes()
        self.downloads = 0
        self.descriptor = dict(
            tag="v1.0.0", asset="assyrian-royal-inscriptions-1.0.0.zip",
            sha256=hashlib.sha256(self.payload).hexdigest(), bytes=len(self.payload),
            dataset="assyrian-royal-inscriptions", release_id="1.0.0",
            tf_version="1.0.0",
        )
        self.resource = ResourceSpec(
            id="assyrian-royal-inscriptions", name="Assyrian royal inscriptions",
            plugin="context-fabric", provider="context-fabric", kind="corpus",
            repository="alexsosn/ORACC-TF", languages=("akkadian",),
            disciplines=("assyriology",), ref="1" * 40,
            tf_path="tf/1.0.0", acquisition_strategy="github-release-archive",
            release=self.descriptor,
        )

    def downloader(self, url, path, *, max_bytes):
        self.downloads += 1
        self.assertEqual(
            url, "https://github.com/alexsosn/ORACC-TF/releases/download/v1.0.0/"
            "assyrian-royal-inscriptions-1.0.0.zip",
        )
        self.assertEqual(max_bytes, len(self.payload))
        Path(path).write_bytes(self.payload)

    def test_published_release_registry_and_bundled_catalog_agree(self):
        canonical = Catalog.from_registry(ROOT).get("assyrian-royal-inscriptions")
        bundled = Catalog.from_plugin_root(ROOT / "plugins/context-fabric").get(
            "assyrian-royal-inscriptions"
        )
        self.assertEqual(canonical, bundled)
        self.assertEqual(canonical.release["sha256"],
                         "788f580604e30054fab34c4c3ea60ec3eb4f399412f1da90f778469d03507468")
        self.assertEqual(canonical.acquisition_strategy, "github-release-archive")

    def test_prepare_then_offline_reuse_same_registered_resource(self):
        acquirer = ReleaseArchiveAcquirer(self.store, download=self.downloader)
        resolver = ContextFabricResolver(Catalog([self.resource]), self.store, release_acquirer=acquirer)
        prepared = resolver.prepare(self.resource.id)
        self.assertEqual(prepared.resource_id, self.resource.id)
        self.assertEqual(prepared.version, "1.0.0")
        self.assertEqual(prepared.source_revision, self.descriptor["sha256"])
        self.assertEqual((prepared.path / "form.tf").read_bytes(), FEATURES["form.tf"])
        self.assertEqual(self.downloads, 1)
        with self.store.source_policy("offline"):
            repeat = resolver.prepare(self.resource.id, version="1.0.0",
                                      source_revision=self.descriptor["sha256"])
        self.assertEqual(repeat.path, prepared.path)
        self.assertEqual(self.downloads, 1)

    def test_offline_cold_miss_never_fetches_or_clones(self):
        resolver = ContextFabricResolver(
            Catalog([self.resource]), self.store,
            release_acquirer=ReleaseArchiveAcquirer(self.store, download=self.downloader),
        )
        with self.store.source_policy("offline"):
            with self.assertRaisesRegex(ValueError, "offline|cached"):
                resolver.prepare(self.resource.id)
        self.assertEqual(self.downloads, 0)
        self.assertEqual([], list(self.store.repositories_dir.iterdir()))

    def test_bad_sha_or_manifest_does_not_publish_any_snapshot(self):
        for payload in (self.payload + b"corruption", archive_bytes(manifest_updates={"dataset": "other"})):
            with self.subTest(payload=payload[-20:]):
                self.payload = payload
                acquirer = ReleaseArchiveAcquirer(self.store, download=self.downloader)
                with self.assertRaisesRegex(ValueError, "sha256|manifest|dataset"):
                    acquirer.prepare(self.resource)
                self.assertEqual([], list(self.store.snapshots_dir.rglob("otype.tf")))

    def test_corrupted_warm_cache_fails_closed_instead_of_redownload_or_load(self):
        acquirer = ReleaseArchiveAcquirer(self.store, download=self.downloader)
        prepared = acquirer.prepare(self.resource)
        (prepared.path / "form.tf").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "integrity"):
            acquirer.prepare(self.resource)
        self.assertEqual(self.downloads, 1)

    def test_pinned_revision_and_version_mismatch_rejected_without_download(self):
        acquirer = ReleaseArchiveAcquirer(self.store, download=self.downloader)
        with self.assertRaisesRegex(ValueError, "version"):
            acquirer.prepare(self.resource, version="2.0.0")
        with self.assertRaisesRegex(ValueError, "revision"):
            acquirer.prepare(self.resource, source_revision="3" * 64)
        self.assertEqual(self.downloads, 0)


if __name__ == "__main__":
    unittest.main()
