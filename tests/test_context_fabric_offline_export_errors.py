from __future__ import annotations

import os
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

from agora_context_fabric.gitstore import GitStore


class SnapshotExportErrorTests(unittest.TestCase):
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
    def _fixture(cls, root: Path) -> tuple[GitStore, Path, str]:
        source = root / "source"
        source.mkdir()
        cls._git(source, "init", "-q", "-b", "main")
        cls._git(source, "config", "user.email", "tests@example.invalid")
        cls._git(source, "config", "user.name", "Agora Tests")
        tf = source / "tf" / "1.0"
        tf.mkdir(parents=True)
        (tf / "otype.tf").write_text("@node\n\nword\n", encoding="utf-8")
        cls._git(source, "add", "-A")
        cls._git(source, "commit", "-qm", "fixture")
        revision = cls._git(source, "rev-parse", "HEAD")
        store = GitStore(root / "cache", min_free_bytes=0)
        repo = store.ensure_metadata(str(source), cache_key="fixture")
        return store, repo, revision

    def test_connectivity_failure_during_snapshot_export_is_actionable_not_raw_git_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store, repo, revision = self._fixture(root)
            failure = subprocess.CalledProcessError(
                128,
                ["git", "fetch", "origin", revision],
                stderr=(
                    "fatal: unable to access 'https://example.invalid/repo.git/': "
                    "Could not resolve host: example.invalid\n"
                ),
            )

            with patch.object(store, "_export_snapshot", side_effect=failure):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "snapshot|network.*required|acquisition",
                ) as caught:
                    store.materialize(repo, "tf/1.0", revision)

            self.assertIs(caught.exception.__cause__, failure)

    def test_nonconnectivity_snapshot_export_failure_is_wrapped_without_cached_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store, repo, revision = self._fixture(root)
            failure = subprocess.CalledProcessError(
                128,
                ["git", "fetch", "origin", revision],
                stderr="remote: Repository not found.\nfatal: Authentication failed\n",
            )

            with patch.object(store, "_export_snapshot", side_effect=failure):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "snapshot|acquisition|cached state",
                ) as caught:
                    store.materialize(repo, "tf/1.0", revision)

            self.assertIs(caught.exception.__cause__, failure)

    def test_snapshot_export_fetch_uses_stable_locale_and_disables_prompting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store, repo, revision = self._fixture(root)
            original_run = subprocess.run
            observed_fetch_envs: list[dict[str, str] | None] = []

            def recording_run(command, *args, **kwargs):
                if "fetch" in command:
                    env = kwargs.get("env")
                    observed_fetch_envs.append(None if env is None else dict(env))
                return original_run(command, *args, **kwargs)

            with patch(
                "agora_context_fabric.gitstore._core.subprocess.run",
                side_effect=recording_run,
            ):
                store.materialize(repo, "tf/1.0", revision)

            self.assertTrue(observed_fetch_envs, "snapshot export must perform its fetch")
            for env in observed_fetch_envs:
                self.assertIsNotNone(env, "classified export fetch must receive explicit env")
                assert env is not None
                self.assertEqual(env.get("LC_ALL"), "C")
                self.assertEqual(env.get("GIT_TERMINAL_PROMPT"), "0")
                if "PATH" in os.environ:
                    self.assertEqual(env.get("PATH"), os.environ["PATH"])


if __name__ == "__main__":
    unittest.main()
