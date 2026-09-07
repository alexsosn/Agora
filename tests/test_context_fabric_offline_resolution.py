from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog, ResourceSpec
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.resolver import ContextFabricResolver
from agora_context_fabric.service import ContextFabricService


class SnapshotLoader:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, object]] = []

    def load(self, path: str, name: str | None = None, features=None):
        self.calls.append((path, name, features))
        return {
            "name": name,
            "path": path,
            "text": (Path(path) / "text.tf").read_text(encoding="utf-8"),
        }

    def unload(self, _name: str) -> None:
        return None


class GitFixtureMixin:
    @staticmethod
    def _git(source: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=source,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.stdout.strip()

    @classmethod
    def _init_repo(cls, source: Path) -> None:
        source.mkdir()
        cls._git(source, "init", "-q", "-b", "main")
        cls._git(source, "config", "user.email", "tests@example.invalid")
        cls._git(source, "config", "user.name", "Agora Tests")

    @classmethod
    def _commit(cls, source: Path, message: str = "fixture") -> str:
        cls._git(source, "add", "-A")
        cls._git(source, "commit", "-qm", message)
        return cls._git(source, "rev-parse", "HEAD")

    @classmethod
    def _make_corpus_source(cls, root: Path) -> tuple[Path, str]:
        source = root / "corpus-source"
        cls._init_repo(source)
        tf = source / "tf" / "1.0"
        tf.mkdir(parents=True)
        (tf / "otype.tf").write_text("@node\n\nword\n", encoding="utf-8")
        (tf / "text.tf").write_text("cached corpus\n", encoding="utf-8")
        return source, cls._commit(source)

    @staticmethod
    def _corpus_catalog(source: Path, *, ref: str | None = None) -> Catalog:
        return Catalog(
            [
                ResourceSpec(
                    id="fixture",
                    name="Offline fixture",
                    plugin="context-fabric",
                    provider="context-fabric",
                    kind="corpus",
                    repository=str(source),
                    ref=ref,
                    tf_path="tf/1.0",
                    languages=("test",),
                    disciplines=("test",),
                )
            ]
        )

    @classmethod
    def _make_collection_source(cls, root: Path) -> tuple[Path, str]:
        source = root / "collection-source"
        cls._init_repo(source)
        tf = source / "Author" / "Work" / "tf" / "1.0"
        tf.mkdir(parents=True)
        (tf / "otype.tf").write_text("@node\n\nword\n", encoding="utf-8")
        (tf / "text.tf").write_text("cached member\n", encoding="utf-8")
        return source, cls._commit(source)

    @staticmethod
    def _collection_catalog(source: Path) -> Catalog:
        return Catalog(
            [
                ResourceSpec(
                    id="collection",
                    name="Offline collection fixture",
                    plugin="context-fabric",
                    provider="context-fabric",
                    kind="collection",
                    repository=str(source),
                    languages=("test",),
                    disciplines=("test",),
                )
            ]
        )


class OfflineServiceTests(GitFixtureMixin, unittest.TestCase):
    def _service(self, root: Path, source: Path, catalog: Catalog | None = None):
        catalog = catalog or self._corpus_catalog(source)
        store = GitStore(root / "cache", min_free_bytes=0)
        resolver = ContextFabricResolver(catalog, store)
        return ContextFabricService(catalog, resolver, SnapshotLoader()), store

    @staticmethod
    def _connectivity_error() -> subprocess.CalledProcessError:
        return subprocess.CalledProcessError(
            128,
            ["git", "fetch", "origin", "HEAD"],
            stderr="fatal: unable to access 'https://example.invalid/x': Could not resolve host: example.invalid\n",
        )

    @staticmethod
    def _auth_error() -> subprocess.CalledProcessError:
        return subprocess.CalledProcessError(
            128,
            ["git", "fetch", "origin", "HEAD"],
            stderr="remote: Repository not found.\nfatal: Authentication failed for 'https://example.invalid/private.git/'\n",
        )

    def test_fully_cached_prepare_and_load_work_in_explicit_offline_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, revision = self._make_corpus_source(root)
            service, _store = self._service(root, source)

            warm = service.prepare("fixture")
            self.assertEqual(warm["source_revision"], revision)

            shutil.move(str(source), str(root / "source-now-unreachable"))

            prepared = service.prepare("fixture", source_mode="offline")
            self.assertEqual(prepared["source_revision"], revision)
            self.assertEqual(prepared["source_resolution"], "cached")
            self.assertFalse(prepared["source_revision_verified"])

            loaded = service.load("fixture", source_mode="offline")
            self.assertEqual(loaded["source_revision"], revision)
            self.assertEqual(loaded["source_resolution"], "cached")
            self.assertFalse(loaded["source_revision_verified"])
            self.assertEqual(loaded["corpus"]["text"], "cached corpus\n")

    def test_prefer_fresh_falls_back_only_for_connectivity_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, revision = self._make_corpus_source(root)
            service, store = self._service(root, source)
            service.prepare("fixture")

            with patch.object(store, "_select", side_effect=self._connectivity_error()):
                prepared = service.prepare("fixture")

            self.assertEqual(prepared["source_revision"], revision)
            self.assertEqual(prepared["source_resolution"], "cached")
            self.assertFalse(prepared["source_revision_verified"])

    def test_nonconnectivity_refresh_failure_is_not_silently_swallowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, _revision = self._make_corpus_source(root)
            service, store = self._service(root, source)
            service.prepare("fixture")

            with patch.object(store, "_select", side_effect=self._auth_error()):
                with self.assertRaisesRegex(RuntimeError, "refresh|repository|authentication") as caught:
                    service.prepare("fixture")

            self.assertIsInstance(caught.exception.__cause__, subprocess.CalledProcessError)

    def test_require_fresh_never_uses_cached_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, _revision = self._make_corpus_source(root)
            service, store = self._service(root, source)
            service.prepare("fixture")

            with patch.object(store, "_select", side_effect=self._connectivity_error()):
                with self.assertRaisesRegex(RuntimeError, "fresh|refresh|network") as caught:
                    service.prepare("fixture", source_mode="require-fresh")

            self.assertIsInstance(caught.exception.__cause__, subprocess.CalledProcessError)

    def test_uncached_explicit_offline_mode_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, _revision = self._make_corpus_source(root)
            service, _store = self._service(root, source)

            with self.assertRaisesRegex(RuntimeError, "offline|network.*required|not cached"):
                service.prepare("fixture", source_mode="offline")

    def test_pinned_resource_can_reuse_its_cached_selected_revision_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, revision = self._make_corpus_source(root)
            service, _store = self._service(root, source, self._corpus_catalog(source, ref="main"))
            service.prepare("fixture")
            shutil.move(str(source), str(root / "pinned-origin-now-unreachable"))

            prepared = service.prepare("fixture", source_mode="offline")
            self.assertEqual(prepared["source_revision"], revision)
            self.assertEqual(prepared["source_resolution"], "cached")
            self.assertFalse(prepared["source_revision_verified"])


class CachedOnlyMaterializationTests(GitFixtureMixin, unittest.TestCase):
    def test_cached_only_materialization_reuses_published_snapshot_but_never_exports_a_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, revision = self._make_corpus_source(root)
            store = GitStore(root / "cache", min_free_bytes=0)
            repo = store.ensure_metadata(str(source), cache_key="fixture")
            snapshot = store.materialize(repo, "tf/1.0", revision)

            self.assertEqual(
                store.materialize(repo, "tf/1.0", revision, allow_network=False),
                snapshot,
            )

            shutil.rmtree(snapshot)
            with patch.object(store, "_export_snapshot", side_effect=AssertionError("network export attempted")):
                with self.assertRaisesRegex(RuntimeError, "offline|network.*required|not cached"):
                    store.materialize(repo, "tf/1.0", revision, allow_network=False)

    def test_cached_only_feature_module_miss_never_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "module-source"
            self._init_repo(source)
            tf = source / "tf" / "1.0"
            tf.mkdir(parents=True)
            (tf / "addon.tf").write_text("module\n", encoding="utf-8")
            revision = self._commit(source)

            store = GitStore(root / "cache", min_free_bytes=0)
            repo = store.ensure_metadata(str(source), cache_key="module")
            snapshot = store.materialize_feature_module(repo, "tf/1.0", revision)
            self.assertEqual(
                store.materialize_feature_module(repo, "tf/1.0", revision, allow_network=False),
                snapshot,
            )

            shutil.rmtree(snapshot)
            with patch.object(store, "_export_snapshot", side_effect=AssertionError("network export attempted")):
                with self.assertRaisesRegex(RuntimeError, "offline|network.*required|not cached"):
                    store.materialize_feature_module(repo, "tf/1.0", revision, allow_network=False)


class OfflineCollectionTests(GitFixtureMixin, unittest.TestCase):
    def test_cached_collection_index_and_member_snapshot_are_usable_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, revision = self._make_collection_source(root)
            catalog = self._collection_catalog(source)
            service, _store = OfflineServiceTests()._service(root, source, catalog)

            page = service.list_collection_members("collection")
            member_id = page["items"][0]["id"]
            service.prepare("collection", member_id=member_id, source_revision=revision)
            shutil.move(str(source), str(root / "collection-origin-now-unreachable"))

            offline_page = service.list_collection_members("collection", source_mode="offline")
            self.assertEqual(offline_page["source_revision"], revision)
            self.assertEqual(offline_page["source_resolution"], "cached")
            self.assertFalse(offline_page["source_revision_verified"])

            prepared = service.prepare(
                "collection",
                member_id=member_id,
                source_revision=revision,
                source_mode="offline",
            )
            self.assertEqual(prepared["source_revision"], revision)
            self.assertEqual(prepared["source_resolution"], "explicit-revision")
            self.assertFalse(prepared["source_revision_verified"])

    def test_explicit_revision_plus_require_fresh_is_rejected_before_acquisition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, revision = self._make_collection_source(root)
            catalog = self._collection_catalog(source)
            service, store = OfflineServiceTests()._service(root, source, catalog)
            page = service.list_collection_members("collection")
            member_id = page["items"][0]["id"]

            with patch.object(store, "_select", side_effect=AssertionError("refresh attempted")):
                with self.assertRaisesRegex(ValueError, "source_revision|require-fresh|incompatible"):
                    service.prepare(
                        "collection",
                        member_id=member_id,
                        source_revision=revision,
                        source_mode="require-fresh",
                    )

    def test_invalid_source_mode_is_rejected_before_acquisition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, _revision = self._make_corpus_source(root)
            service, store = OfflineServiceTests()._service(root, source)

            with patch.object(store, "ensure_metadata", side_effect=AssertionError("acquisition attempted")):
                with self.assertRaisesRegex(ValueError, "source_mode"):
                    service.prepare("fixture", source_mode="sometimes")


if __name__ == "__main__":
    unittest.main()
