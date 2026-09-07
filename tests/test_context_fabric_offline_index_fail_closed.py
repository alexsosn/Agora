from __future__ import annotations

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

from agora_context_fabric.collection_index import CollectionIndexManager
from agora_context_fabric.gitstore import GitStore


class OfflineCollectionIndexFailClosedTests(unittest.TestCase):
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

    def test_manager_never_regenerates_index_when_source_policy_is_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            self._git(source, "init", "-q", "-b", "main")
            self._git(source, "config", "user.email", "tests@example.invalid")
            self._git(source, "config", "user.name", "Agora Tests")
            tf = source / "Author" / "Work" / "tf" / "1.0"
            tf.mkdir(parents=True)
            (tf / "otype.tf").write_text("@node\n\nword\n", encoding="utf-8")
            self._git(source, "add", "-A")
            self._git(source, "commit", "-qm", "fixture")
            revision = self._git(source, "rev-parse", "HEAD")

            store = GitStore(root / "cache", min_free_bytes=0)
            repo = store.ensure_metadata(str(source), cache_key="collection")
            manager = CollectionIndexManager(store)

            with store.source_policy("offline"), patch.object(
                store,
                "dataset_roots",
                side_effect=AssertionError("dynamic collection index generation attempted"),
            ):
                with self.assertRaisesRegex(RuntimeError, "offline|index|network.*required"):
                    manager.resolve(
                        collection_id="collection",
                        languages=("test",),
                        repo=repo,
                        source_revision=revision,
                    )


if __name__ == "__main__":
    unittest.main()
