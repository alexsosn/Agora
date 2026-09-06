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


class RepositoryTransitionTests(unittest.TestCase):
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

    def _make_repository(self, root: Path, name: str, payload: str) -> tuple[Path, str]:
        source = root / name
        source.mkdir()
        self._git(source, "init", "-q", "-b", "main")
        self._git(source, "config", "user.email", "tests@example.invalid")
        self._git(source, "config", "user.name", "Agora Tests")
        tf = source / "tf" / "1.0"
        tf.mkdir(parents=True)
        (tf / "otype.tf").write_text("@node\n", encoding="utf-8")
        (tf / "word.tf").write_text(payload + "\n", encoding="utf-8")
        self._git(source, "add", ".")
        self._git(source, "commit", "-qm", f"{name} fixture")
        return source, self._git(source, "rev-parse", "HEAD")

    def test_fresh_resolution_repoints_metadata_cache_when_repository_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_a, revision_a = self._make_repository(root, "source-a", "a")
            source_b, revision_b = self._make_repository(root, "source-b", "b")
            self.assertNotEqual(revision_a, revision_b)

            store = GitStore(
                root / "cache",
                snapshot_soft_limit_bytes=0,
                min_free_bytes=0,
            )
            first = resolve_repository(
                store,
                resource_id="fixture",
                repository=str(source_a),
                configured_ref=None,
            )
            self.assertEqual(first.revision, revision_a)

            second = resolve_repository(
                store,
                resource_id="fixture",
                repository=str(source_b),
                configured_ref=None,
            )
            self.assertEqual(second.resolution, "fresh")
            self.assertEqual(second.revision, revision_b)
            self.assertNotEqual(second.revision, revision_a)

            actual_origin = store._run("remote", "get-url", "origin", cwd=second.path)
            self.assertEqual(Path(actual_origin).resolve(), source_b.resolve())

            record = json.loads(
                (second.path / ".git" / "agora-selection.json").read_text(encoding="utf-8")
            )
            self.assertEqual(record["repository"], str(source_b))
            self.assertEqual(record["revision"], revision_b)


if __name__ == "__main__":
    unittest.main()
