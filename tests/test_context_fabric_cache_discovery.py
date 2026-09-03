from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.gitstore import GitStore


class ConservativeCacheDiscoveryTests(unittest.TestCase):
    def test_unindexed_nested_tf_tree_is_not_guessed_as_evictable_objects(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GitStore(
                Path(tmp) / "cache",
                snapshot_soft_limit_bytes=0,
                min_free_bytes=0,
            )
            module = (
                store.snapshots_dir
                / "legacy-module"
                / ("a" * 40)
                / "feature-modules"
                / "tf"
                / "2.0"
            )
            nested = module / "nested"
            nested.mkdir(parents=True)
            (module / "addon.tf").write_text("@node\n", encoding="utf-8")
            (nested / "extra.tf").write_text("@node\n", encoding="utf-8")

            # There is intentionally no object-meta sidecar. From the directory
            # tree alone Agora cannot prove whether `nested` is an independent
            # feature module or merely source content inside `module`. Guessing
            # wrong would let LRU prune mutate a source snapshot in place.
            self.assertEqual(store.cache_entries(), [])

            result = store.prune(target_bytes=0)
            self.assertEqual(result["removed_entries"], 0)
            self.assertTrue((module / "addon.tf").is_file())
            self.assertTrue((nested / "extra.tf").is_file())

    def test_access_indexes_exact_object_and_makes_only_that_root_evictable(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GitStore(
                Path(tmp) / "cache",
                snapshot_soft_limit_bytes=0,
                min_free_bytes=0,
            )
            module = (
                store.snapshots_dir
                / "legacy-module"
                / ("b" * 40)
                / "feature-modules"
                / "tf"
                / "2.0"
            )
            nested = module / "nested"
            nested.mkdir(parents=True)
            (module / "addon.tf").write_text("@node\n", encoding="utf-8")
            (nested / "extra.tf").write_text("@node\n", encoding="utf-8")

            store.touch_cache_object(module)
            entries = store.cache_entries()
            self.assertEqual(len(entries), 1)
            self.assertEqual(Path(entries[0]["path"]), module.resolve())

            result = store.prune(target_bytes=0)
            self.assertEqual(result["removed_entries"], 1)
            self.assertFalse(module.exists())


if __name__ == "__main__":
    unittest.main()
