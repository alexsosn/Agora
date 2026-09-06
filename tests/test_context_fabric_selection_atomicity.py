from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.network import resolve_repository


class InterleavingGitStore(GitStore):
    """Force the old post-ensure/pre-selected-revision race deterministically."""

    def __init__(self, *args, interfering_ref: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.interfering_ref = interfering_ref
        self.interleaved = False

    def ensure_metadata(self, repository: str, *, cache_key=None, ref=None):
        repo = super().ensure_metadata(repository, cache_key=cache_key, ref=ref)
        # At this point the historical API has released its repository lock. A
        # different process/version may now select another ref in the same cache
        # before resolve_repository() reads refs/agora/selected.
        other = GitStore(
            self.cache_dir,
            snapshot_soft_limit_bytes=self.snapshot_soft_limit_bytes,
            min_free_bytes=self.min_free_bytes,
        )
        other.ensure_metadata(
            repository,
            cache_key=cache_key,
            ref=self.interfering_ref,
        )
        self.interleaved = True
        return repo


class RepositorySelectionAtomicityTests(unittest.TestCase):
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

    def _make_source(self, root: Path) -> tuple[Path, str, str]:
        source = root / "source"
        source.mkdir()
        self._git(source, "init", "-q", "-b", "main")
        self._git(source, "config", "user.email", "tests@example.invalid")
        self._git(source, "config", "user.name", "Agora Tests")
        tf = source / "tf" / "1.0"
        tf.mkdir(parents=True)
        (tf / "otype.tf").write_text("@node\n", encoding="utf-8")
        (tf / "word.tf").write_text("base\n", encoding="utf-8")
        self._git(source, "add", ".")
        self._git(source, "commit", "-qm", "base")

        self._git(source, "switch", "-qc", "branch-a")
        (tf / "word.tf").write_text("branch-a\n", encoding="utf-8")
        self._git(source, "add", ".")
        self._git(source, "commit", "-qm", "branch a")
        revision_a = self._git(source, "rev-parse", "HEAD")

        self._git(source, "switch", "-q", "main")
        self._git(source, "switch", "-qc", "branch-b")
        (tf / "word.tf").write_text("branch-b\n", encoding="utf-8")
        self._git(source, "add", ".")
        self._git(source, "commit", "-qm", "branch b")
        revision_b = self._git(source, "rev-parse", "HEAD")
        self.assertNotEqual(revision_a, revision_b)
        return source, revision_a, revision_b

    def test_fresh_resolution_cannot_be_relabelled_by_a_competing_ref_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, revision_a, revision_b = self._make_source(root)
            store = InterleavingGitStore(
                root / "cache",
                interfering_ref="branch-b",
                snapshot_soft_limit_bytes=0,
                min_free_bytes=0,
            )

            resolution = resolve_repository(
                store,
                resource_id="fixture",
                repository=str(source),
                configured_ref="branch-a",
            )

            self.assertTrue(store.interleaved)
            self.assertEqual(resolution.resolution, "fresh")
            self.assertEqual(resolution.revision, revision_a)
            self.assertNotEqual(resolution.revision, revision_b)

            record = json.loads(
                (resolution.path / ".git" / "agora-selection.json").read_text(encoding="utf-8")
            )
            self.assertEqual(record["configured_ref"], "branch-a")
            self.assertEqual(record["revision"], revision_a)


if __name__ == "__main__":
    unittest.main()
