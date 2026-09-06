from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog, ResourceSpec
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.network import use_network_mode
from agora_context_fabric.resolver import ContextFabricResolver


class OfflineFeatureModuleTests(unittest.TestCase):
    @staticmethod
    def _init_repo(source: Path) -> None:
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=source, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=source, check=True)
        subprocess.run(["git", "config", "user.name", "Agora Tests"], cwd=source, check=True)

    @staticmethod
    def _commit(source: Path) -> None:
        subprocess.run(["git", "add", "."], cwd=source, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=source, check=True)

    def test_module_enabled_prepare_reuses_parent_and_module_snapshots_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent_source = root / "parent-source"
            module_source = root / "module-source"
            parent_source.mkdir()
            module_source.mkdir()
            self._init_repo(parent_source)
            self._init_repo(module_source)

            parent_tf = parent_source / "tf" / "2.0"
            parent_tf.mkdir(parents=True)
            (parent_tf / "otype.tf").write_text("@node\n", encoding="utf-8")
            (parent_tf / "word.tf").write_text("parent\n", encoding="utf-8")
            self._commit(parent_source)

            module_tf = module_source / "tf" / "2.0"
            module_tf.mkdir(parents=True)
            (module_tf / "addon.tf").write_text("module\n", encoding="utf-8")
            self._commit(module_source)

            catalog = Catalog(
                [
                    ResourceSpec(
                        id="fixture",
                        name="Fixture corpus",
                        plugin="context-fabric",
                        provider="context-fabric",
                        kind="corpus",
                        repository=str(parent_source),
                        languages=("test",),
                        disciplines=("testing",),
                    ),
                    ResourceSpec(
                        id="fixture-addon",
                        name="Fixture add-on",
                        plugin="context-fabric",
                        provider="context-fabric",
                        kind="feature-module",
                        repository=str(module_source),
                        languages=("test",),
                        disciplines=("testing",),
                        tf_path="tf/2.0",
                        parent="fixture",
                        parent_versions=("2.0",),
                        module_path="example/fixture-addon/tf",
                        module_status="optional",
                    ),
                ]
            )
            store = GitStore(root / "cache")
            resolver = ContextFabricResolver(catalog, store)

            fresh = resolver.prepare_with_modules("fixture", modules=["fixture-addon"])
            self.assertEqual(fresh.resolution, "fresh")
            self.assertTrue(fresh.source_revision_verified)
            self.assertEqual(fresh.modules[0].resolution, "fresh")
            self.assertTrue(fresh.modules[0].source_revision_verified)
            self.assertTrue((fresh.path / "addon.tf").is_file())

            # Prove the offline pass cannot acquire/export either source again.
            def unexpected(*_args, **_kwargs):
                raise AssertionError("offline reuse must not enter a remote-capable acquisition path")

            store.ensure_metadata = unexpected  # type: ignore[method-assign]
            store.materialize = unexpected  # type: ignore[method-assign]
            store.materialize_feature_module = unexpected  # type: ignore[method-assign]

            with use_network_mode("offline"):
                cached = resolver.prepare_with_modules("fixture", modules=["fixture-addon"])

            self.assertEqual(cached.path, fresh.path)
            self.assertEqual(cached.source_revision, fresh.source_revision)
            self.assertEqual(cached.resolution, "cached")
            self.assertFalse(cached.source_revision_verified)
            self.assertEqual(cached.modules[0].source_revision, fresh.modules[0].source_revision)
            self.assertEqual(cached.modules[0].resolution, "cached")
            self.assertFalse(cached.modules[0].source_revision_verified)
            self.assertTrue((cached.path / "otype.tf").is_file())
            self.assertTrue((cached.path / "addon.tf").is_file())


if __name__ == "__main__":
    unittest.main()
