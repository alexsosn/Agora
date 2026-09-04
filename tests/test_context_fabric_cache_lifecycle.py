from __future__ import annotations

import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog, ResourceSpec
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.resolver import PreparedCorpus, PreparedFeatureModule
from agora_context_fabric.service import ContextFabricService


def _remove_object(cache_dir: str, path: str, queue) -> None:
    store = GitStore(Path(cache_dir), snapshot_soft_limit_bytes=10_000, min_free_bytes=0)
    queue.put(store.remove_cache_object(Path(path)))


def _hold_repository_lock(cache_dir: str, ready, release) -> None:
    store = GitStore(Path(cache_dir), snapshot_soft_limit_bytes=10_000, min_free_bytes=0)
    with store._repository_lock("fixture", timeout=2):
        ready.set()
        release.wait(3)


def _crash_with_repository_lock(cache_dir: str, ready) -> None:
    store = GitStore(Path(cache_dir), snapshot_soft_limit_bytes=10_000, min_free_bytes=0)
    with store._repository_lock("fixture", timeout=2):
        ready.set()
        os._exit(0)


class CacheFixture(unittest.TestCase):
    @staticmethod
    def _init_repo(source: Path) -> None:
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=source, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=source, check=True)
        subprocess.run(["git", "config", "user.name", "Agora Tests"], cwd=source, check=True)

    @staticmethod
    def _commit(source: Path, message: str = "fixture") -> None:
        subprocess.run(["git", "add", "."], cwd=source, check=True)
        subprocess.run(["git", "commit", "-qm", message], cwd=source, check=True)

    def make_corpus_repo(self, root: Path) -> Path:
        source = root / "corpus-source"
        source.mkdir()
        self._init_repo(source)
        for name, payload in (("1.0", "one"), ("2.0", "two")):
            tf = source / "tf" / name
            tf.mkdir(parents=True)
            (tf / "otype.tf").write_text("@node\n", encoding="utf-8")
            (tf / "word.tf").write_text(payload * 80, encoding="utf-8")
        self._commit(source)
        return source

    def make_module_repo(self, root: Path) -> Path:
        source = root / "module-source"
        source.mkdir()
        self._init_repo(source)
        tf = source / "tf" / "2.0"
        tf.mkdir(parents=True)
        (tf / "addon.tf").write_text("addon" * 80, encoding="utf-8")
        self._commit(source)
        return source

    def make_store(self, root: Path, *, soft_limit: int = 10_000) -> tuple[GitStore, Path]:
        source = self.make_corpus_repo(root)
        store = GitStore(
            root / "cache",
            snapshot_soft_limit_bytes=soft_limit,
            min_free_bytes=0,
        )
        repo = store.ensure_metadata(str(source), cache_key="fixture")
        return store, repo


class RepositoryLockContractTests(CacheFixture):
    def test_live_process_blocks_and_process_death_releases_repository_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store, _repo = self.make_store(root)
            ctx = multiprocessing.get_context("spawn")
            ready = ctx.Event()
            release = ctx.Event()
            holder = ctx.Process(
                target=_hold_repository_lock,
                args=(str(store.cache_dir), ready, release),
            )
            holder.start()
            self.assertTrue(ready.wait(3))
            with self.assertRaises(TimeoutError):
                with store._repository_lock("fixture", timeout=0.1):
                    pass
            release.set()
            holder.join(5)
            self.assertEqual(holder.exitcode, 0)

            ready = ctx.Event()
            crashed = ctx.Process(
                target=_crash_with_repository_lock,
                args=(str(store.cache_dir), ready),
            )
            crashed.start()
            self.assertTrue(ready.wait(3))
            crashed.join(5)
            self.assertEqual(crashed.exitcode, 0)
            with store._repository_lock("fixture", timeout=0.5):
                pass


class CacheObjectContractTests(CacheFixture):
    def test_active_source_and_overlay_are_cross_process_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store, repo = self.make_store(root)
            source = store.materialize(repo, "tf/2.0")
            overlay = store.overlays_dir / "fixture" / store.selected_revision(repo) / "overlay-test"
            overlay.mkdir(parents=True)
            (overlay / "otype.tf").write_text("@node\n", encoding="utf-8")
            (overlay / "word.tf").write_text("derived", encoding="utf-8")
            store.touch_cache_object(overlay)

            ctx = multiprocessing.get_context("spawn")
            for path in (source, overlay):
                lease = store.acquire_cache_lease(path)
                try:
                    queue = ctx.Queue()
                    remover = ctx.Process(
                        target=_remove_object,
                        args=(str(store.cache_dir), str(path), queue),
                    )
                    remover.start()
                    remover.join(5)
                    self.assertEqual(remover.exitcode, 0)
                    result = queue.get(timeout=1)
                    self.assertEqual(result["removed_entries"], 0)
                    self.assertEqual(result["skipped_in_use"], 1)
                    self.assertTrue(path.exists())
                finally:
                    lease.release()

                queue = ctx.Queue()
                remover = ctx.Process(
                    target=_remove_object,
                    args=(str(store.cache_dir), str(path), queue),
                )
                remover.start()
                remover.join(5)
                self.assertEqual(remover.exitcode, 0)
                result = queue.get(timeout=1)
                self.assertEqual(result["removed_entries"], 1)
                self.assertFalse(path.exists())

    def test_status_and_prune_cover_corpora_modules_and_overlays(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store, repo = self.make_store(root, soft_limit=0)
            corpus = store.materialize(repo, "tf/2.0")

            module_source = self.make_module_repo(root)
            module_repo = store.ensure_metadata(str(module_source), cache_key="fixture-addon")
            module = store.materialize_feature_module(module_repo, "tf/2.0")

            overlay = store.overlays_dir / "fixture" / store.selected_revision(repo) / "overlay-test"
            overlay.mkdir(parents=True)
            (overlay / "otype.tf").write_text("@node\n", encoding="utf-8")
            (overlay / "word.tf").write_text("derived" * 80, encoding="utf-8")
            store.touch_cache_object(overlay)

            lease = store.acquire_cache_lease(overlay)
            try:
                status = store.cache_status()
                self.assertEqual(
                    {entry["kind"] for entry in status["entries"]},
                    {"corpus-snapshot", "feature-module-snapshot", "overlay"},
                )
                self.assertEqual(status["totals_by_kind"]["overlay"]["entries"], 1)
                overlay_entry = next(entry for entry in status["entries"] if entry["kind"] == "overlay")
                self.assertTrue(overlay_entry["in_use"])

                result = store.prune(target_bytes=0)
                self.assertTrue(overlay.exists())
                self.assertFalse(corpus.exists())
                self.assertFalse(module.exists())
                self.assertGreaterEqual(result["skipped_in_use"], 1)
                self.assertFalse(result["target_met"])
            finally:
                lease.release()

    def test_transition_guard_covers_composition_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, repo = self.make_store(Path(tmp))
            corpus = store.materialize(repo, "tf/2.0")
            with store.cache_transition():
                other = GitStore(store.cache_dir, snapshot_soft_limit_bytes=10_000, min_free_bytes=0)
                with self.assertRaises(TimeoutError):
                    other.remove_cache_object(corpus, timeout=0.05)
            removed = store.remove_cache_object(corpus)
            self.assertEqual(removed["removed_entries"], 1)

    def test_recursive_eviction_io_happens_after_transition_is_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, repo = self.make_store(Path(tmp))
            corpus = store.materialize(repo, "tf/2.0")
            other = GitStore(store.cache_dir, snapshot_soft_limit_bytes=10_000, min_free_bytes=0)
            real_rmtree = shutil.rmtree
            observed_detached_delete = False

            def checked_rmtree(path, *args, **kwargs):
                nonlocal observed_detached_delete
                candidate = Path(path)
                if candidate.name.startswith("evict-"):
                    # Recursive deletion of a detached tree must not hold the
                    # global exclusive transition lock. A normal prepare/load
                    # can therefore enter while deletion IO continues.
                    with other.cache_transition(timeout=0.1):
                        observed_detached_delete = True
                return real_rmtree(path, *args, **kwargs)

            with patch("agora_context_fabric.gitstore.shutil.rmtree", side_effect=checked_rmtree):
                result = store.remove_cache_object(corpus)

            self.assertEqual(result["removed_entries"], 1)
            self.assertTrue(observed_detached_delete)
            self.assertFalse(corpus.exists())

    def test_detach_invalidates_sidecars_before_served_path_can_disappear(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, repo = self.make_store(Path(tmp))
            corpus = store.materialize(repo, "tf/2.0")
            meta = store._meta_path(corpus)
            access = store._access_path(corpus)
            self.assertTrue(meta.is_file())
            self.assertTrue(access.is_file())

            real_replace = os.replace

            def fail_object_detach(source, destination):
                if Path(source) == corpus:
                    # If the process dies immediately after a successful rename,
                    # stale identity must not survive and later bless a nested
                    # path recreated by a different enclosing cache object.
                    self.assertFalse(meta.exists())
                    self.assertFalse(access.exists())
                    raise OSError("simulated detach failure")
                return real_replace(source, destination)

            with patch("agora_context_fabric.gitstore.os.replace", side_effect=fail_object_detach):
                with self.assertRaisesRegex(OSError, "simulated detach failure"):
                    store.remove_cache_object(corpus)

            self.assertTrue(corpus.is_dir())
            self.assertEqual(store.cache_entries(), [])
            store.touch_cache_object(corpus)
            self.assertEqual([Path(entry["path"]) for entry in store.cache_entries()], [corpus])

    def test_store_startup_never_performs_recursive_abandoned_eviction_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            store = GitStore(cache_dir, snapshot_soft_limit_bytes=10_000, min_free_bytes=0)
            abandoned = store.tmp_dir / "evict-abandoned"
            data = abandoned / "data"
            data.mkdir(parents=True)
            (data / "payload.tf").write_bytes(b"x" * 128)
            old = time.time() - 600
            os.utime(abandoned, (old, old))

            reopened = GitStore(cache_dir, snapshot_soft_limit_bytes=10_000, min_free_bytes=0)
            self.assertTrue(abandoned.is_dir())
            status = reopened.cache_status()
            self.assertGreaterEqual(status["abandoned_eviction_bytes"], 128)
            self.assertGreaterEqual(status["abandoned_eviction_entries"], 1)

            result = reopened.prune(target_bytes=10_000)
            self.assertFalse(abandoned.exists())
            self.assertGreaterEqual(result["abandoned_eviction_entries_removed"], 1)
            self.assertGreaterEqual(result["abandoned_eviction_bytes_removed"], 128)


class ServiceLifecycleContractTests(CacheFixture):
    @staticmethod
    def _resource() -> ResourceSpec:
        return ResourceSpec(
            id="fixture",
            name="Fixture",
            plugin="context-fabric",
            provider="context-fabric",
            kind="corpus",
            repository="unused/repository",
            languages=("test",),
            disciplines=("testing",),
        )

    def test_failed_reload_preserves_previous_load_and_lease(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store, repo = self.make_store(root)
            first = store.materialize(repo, "tf/1.0")
            second = store.materialize(repo, "tf/2.0")
            revision = store.selected_revision(repo)
            prepared = [
                PreparedCorpus("fixture", None, "fixture@1.0", "tf/1.0", first, "1.0", revision),
                PreparedCorpus("fixture", None, "fixture@1.0", "tf/2.0", second, "2.0", revision),
            ]

            class Resolver:
                def __init__(self):
                    self.store = store
                    self.calls = 0

                def prepare_with_modules(self, resource_id: str, **_kwargs):
                    value = prepared[self.calls]
                    self.calls += 1
                    return value

            class Loader:
                def __init__(self):
                    self.current = None
                    self.unloaded = []
                    self.calls = 0

                def load(self, path: str, name=None, features=None):
                    self.calls += 1
                    if self.calls == 2:
                        raise RuntimeError("replacement failed")
                    self.current = (path, name)
                    return {"path": path, "name": name}

                def unload(self, name: str):
                    self.unloaded.append(name)
                    self.current = None

            loader = Loader()
            service = ContextFabricService(Catalog([self._resource()]), Resolver(), loader)
            service.load("fixture", version="1.0")
            with self.assertRaisesRegex(RuntimeError, "replacement failed"):
                service.load("fixture", version="1.0")

            blocked = store.remove_cache_object(first)
            self.assertEqual(blocked["skipped_in_use"], 1)
            removed_new = store.remove_cache_object(second)
            self.assertEqual(removed_new["removed_entries"], 1)
            self.assertEqual(loader.unloaded, [])

            first_unload = service.unload("fixture@1.0")
            second_unload = service.unload("fixture@1.0")
            self.assertTrue(first_unload["was_loaded"])
            self.assertFalse(second_unload["was_loaded"])
            self.assertEqual(loader.unloaded, ["fixture@1.0"])

    def test_module_logical_name_leases_final_overlay_not_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store, repo = self.make_store(root)
            parent = store.materialize(repo, "tf/2.0")
            revision = store.selected_revision(repo)
            module_source = self.make_module_repo(root)
            module_repo = store.ensure_metadata(str(module_source), cache_key="fixture-addon")
            module_path = store.materialize_feature_module(module_repo, "tf/2.0")
            module_revision = store.selected_revision(module_repo)
            overlay = store.overlays_dir / "fixture" / revision / "module-overlay"
            overlay.mkdir(parents=True)
            (overlay / "otype.tf").write_text("@node\n", encoding="utf-8")
            store.touch_cache_object(overlay)
            prepared_module = PreparedFeatureModule(
                "fixture-addon", "fixture", "fixture/addon", "tf/2.0", module_path, module_revision
            )
            prepared = PreparedCorpus(
                "fixture", None, "fixture@2.0+fixture-addon", "tf/2.0", overlay,
                "2.0", revision, (prepared_module,)
            )

            class Resolver:
                def __init__(self):
                    self.store = store

                def prepare_with_modules(self, resource_id: str, **_kwargs):
                    return prepared

            class Loader:
                def load(self, path: str, name=None, features=None):
                    return {"path": path, "name": name}

                def unload(self, name: str):
                    return None

            service = ContextFabricService(Catalog([self._resource()]), Resolver(), Loader())
            result = service.load("fixture", version="2.0", modules=["fixture-addon"])
            self.assertEqual(result["logical_name"], "fixture@2.0+fixture-addon")
            self.assertEqual(store.remove_cache_object(overlay)["skipped_in_use"], 1)
            self.assertEqual(store.remove_cache_object(parent)["removed_entries"], 1)
            self.assertEqual(store.remove_cache_object(module_path)["removed_entries"], 1)
            service.unload("fixture@2.0+fixture-addon")
            self.assertEqual(store.remove_cache_object(overlay)["removed_entries"], 1)


if __name__ == "__main__":
    unittest.main()
