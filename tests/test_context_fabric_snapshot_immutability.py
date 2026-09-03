from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.gitstore import GitStore


class ImmutableSnapshotTests(unittest.TestCase):
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
    def _commit(cls, source: Path, message: str) -> str:
        cls._git(source, "add", "-A")
        cls._git(source, "commit", "-qm", message)
        return cls._git(source, "rev-parse", "HEAD")

    def test_corpus_snapshots_are_revision_addressed_and_drop_deleted_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            self._init_repo(source)
            tf = source / "tf" / "1.0"
            tf.mkdir(parents=True)
            (tf / "otype.tf").write_text("@node\n", encoding="utf-8")
            (tf / "keep.tf").write_text("old\n", encoding="utf-8")
            (tf / "obsolete.tf").write_text("remove-me\n", encoding="utf-8")
            rev_a = self._commit(source, "revision A")

            store = GitStore(root / "cache", min_free_bytes=0)
            repo = store.ensure_metadata(str(source), cache_key="fixture")
            snap_a = store.materialize(repo, "tf/1.0", rev_a)

            (tf / "keep.tf").write_text("new\n", encoding="utf-8")
            (tf / "obsolete.tf").unlink()
            rev_b = self._commit(source, "revision B")
            store.ensure_metadata(str(source), cache_key="fixture")
            snap_b = store.materialize(repo, "tf/1.0", rev_b)

            self.assertNotEqual(snap_a, snap_b)
            self.assertIn(rev_a, snap_a.parts)
            self.assertIn(rev_b, snap_b.parts)
            self.assertEqual((snap_a / "keep.tf").read_text(encoding="utf-8"), "old\n")
            self.assertTrue((snap_a / "obsolete.tf").is_file())
            self.assertEqual((snap_b / "keep.tf").read_text(encoding="utf-8"), "new\n")
            self.assertFalse((snap_b / "obsolete.tf").exists())

            self.assertEqual(store.materialize(repo, "tf/1.0", rev_a), snap_a)
            self.assertEqual((snap_a / "keep.tf").read_text(encoding="utf-8"), "old\n")

    def test_feature_modules_are_immutable_revision_snapshots_without_warp_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "module-source"
            self._init_repo(source)
            tf = source / "tf" / "1.0"
            tf.mkdir(parents=True)
            (tf / "addon.tf").write_text("old\n", encoding="utf-8")
            (tf / "removed.tf").write_text("old-only\n", encoding="utf-8")
            rev_a = self._commit(source, "module A")

            store = GitStore(root / "cache", min_free_bytes=0)
            repo = store.ensure_metadata(str(source), cache_key="module")
            snap_a = store.materialize_feature_module(repo, "tf/1.0", rev_a)

            (tf / "addon.tf").write_text("new\n", encoding="utf-8")
            (tf / "removed.tf").unlink()
            rev_b = self._commit(source, "module B")
            store.ensure_metadata(str(source), cache_key="module")
            snap_b = store.materialize_feature_module(repo, "tf/1.0", rev_b)

            self.assertNotEqual(snap_a, snap_b)
            self.assertIn("feature-modules", snap_a.parts)
            self.assertEqual((snap_a / "addon.tf").read_text(encoding="utf-8"), "old\n")
            self.assertTrue((snap_a / "removed.tf").exists())
            self.assertEqual((snap_b / "addon.tf").read_text(encoding="utf-8"), "new\n")
            self.assertFalse((snap_b / "removed.tf").exists())
            for forbidden in GitStore.FORBIDDEN_FEATURE_MODULE_FILES:
                self.assertFalse((snap_b / forbidden).exists())

    def test_snapshot_export_ignores_export_ignore_and_export_subst_transformations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            self._init_repo(source)
            tf = source / "tf" / "1.0"
            tf.mkdir(parents=True)
            (tf / "otype.tf").write_text("@node\n", encoding="utf-8")
            (tf / "hidden.tf").write_text("tracked\n", encoding="utf-8")
            raw = "$Format:%H$\n"
            (tf / "subst.tf").write_text(raw, encoding="utf-8")
            (source / ".gitattributes").write_text(
                "tf/1.0/hidden.tf export-ignore\n"
                "tf/1.0/subst.tf export-subst\n",
                encoding="utf-8",
            )
            revision = self._commit(source, "attributes")

            store = GitStore(root / "cache", min_free_bytes=0)
            repo = store.ensure_metadata(str(source), cache_key="fixture")
            snapshot = store.materialize(repo, "tf/1.0", revision)

            self.assertEqual((snapshot / "hidden.tf").read_text(encoding="utf-8"), "tracked\n")
            self.assertEqual((snapshot / "subst.tf").read_text(encoding="utf-8"), raw)

    def test_concurrent_materialization_of_two_revisions_keeps_both_snapshots_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            self._init_repo(source)
            tf = source / "tf" / "1.0"
            tf.mkdir(parents=True)
            (tf / "otype.tf").write_text("@node\n", encoding="utf-8")
            (tf / "value.tf").write_text("A\n", encoding="utf-8")
            rev_a = self._commit(source, "A")

            (tf / "value.tf").write_text("B\n", encoding="utf-8")
            rev_b = self._commit(source, "B")

            store = GitStore(root / "cache", min_free_bytes=0)
            repo = store.ensure_metadata(str(source), cache_key="fixture")

            with ThreadPoolExecutor(max_workers=2) as pool:
                future_a = pool.submit(store.materialize, repo, "tf/1.0", rev_a)
                future_b = pool.submit(store.materialize, repo, "tf/1.0", rev_b)
                snap_a = future_a.result()
                snap_b = future_b.result()

            self.assertEqual((snap_a / "value.tf").read_text(encoding="utf-8"), "A\n")
            self.assertEqual((snap_b / "value.tf").read_text(encoding="utf-8"), "B\n")
            self.assertNotEqual(snap_a, snap_b)


if __name__ == "__main__":
    unittest.main()
