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


class GitSelectionTests(unittest.TestCase):
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
    def _source(cls, root: Path) -> tuple[Path, str]:
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
        return source, cls._git(source, "rev-parse", "HEAD")

    @staticmethod
    def _connectivity_error() -> subprocess.CalledProcessError:
        return subprocess.CalledProcessError(
            128,
            ["git", "fetch", "origin", "HEAD"],
            stderr=(
                "fatal: unable to access 'https://example.invalid/repo.git/': "
                "Could not resolve host: example.invalid\n"
            ),
        )

    @staticmethod
    def _auth_error() -> subprocess.CalledProcessError:
        return subprocess.CalledProcessError(
            128,
            ["git", "clone", "https://example.invalid/private.git"],
            stderr=(
                "remote: Repository not found.\n"
                "fatal: Authentication failed for 'https://example.invalid/private.git/'\n"
            ),
        )

    def test_connectivity_fallback_preserves_previous_selected_ref(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, revision = self._source(root)
            store = GitStore(root / "cache", min_free_bytes=0)
            repo = store.ensure_metadata(str(source), cache_key="fixture")
            self.assertEqual(store.selected_revision(repo), revision)

            with patch.object(store, "_select", side_effect=self._connectivity_error()):
                selection = store.select_metadata(
                    str(source),
                    cache_key="fixture",
                    source_mode="prefer-fresh",
                )

            self.assertEqual(selection.repo, repo)
            self.assertEqual(selection.revision, revision)
            self.assertEqual(selection.source_resolution, "cached")
            self.assertFalse(selection.source_revision_verified)
            self.assertEqual(store.selected_revision(repo), revision)

    def test_offline_selection_never_calls_select_or_clone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, revision = self._source(root)
            store = GitStore(root / "cache", min_free_bytes=0)
            repo = store.ensure_metadata(str(source), cache_key="fixture")

            with patch.object(store, "_select", side_effect=AssertionError("fetch attempted")), patch.object(
                store,
                "repository_url",
                side_effect=AssertionError("clone source resolution attempted"),
            ):
                selection = store.select_metadata(
                    str(source),
                    cache_key="fixture",
                    source_mode="offline",
                )

            self.assertEqual(selection.repo, repo)
            self.assertEqual(selection.revision, revision)
            self.assertEqual(selection.source_resolution, "cached")
            self.assertFalse(selection.source_revision_verified)

    def test_refresh_git_process_uses_stable_diagnostics_and_disables_prompting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, _revision = self._source(root)
            store = GitStore(root / "cache", min_free_bytes=0)
            store.ensure_metadata(str(source), cache_key="fixture")

            original_run = subprocess.run
            observed_fetch_envs: list[dict[str, str]] = []

            def recording_run(command, *args, **kwargs):
                if "fetch" in command:
                    env = kwargs.get("env")
                    self.assertIsNotNone(env, "classified refresh fetch must receive explicit env")
                    observed_fetch_envs.append(dict(env))
                return original_run(command, *args, **kwargs)

            with patch("agora_context_fabric.gitstore._core.subprocess.run", side_effect=recording_run):
                store.select_metadata(
                    str(source),
                    cache_key="fixture",
                    source_mode="require-fresh",
                )

            self.assertTrue(observed_fetch_envs)
            for env in observed_fetch_envs:
                self.assertEqual(env.get("LC_ALL"), "C")
                self.assertEqual(env.get("GIT_TERMINAL_PROMPT"), "0")
                # Selection must retain the normal process environment rather than replacing it.
                if "PATH" in os.environ:
                    self.assertEqual(env.get("PATH"), os.environ["PATH"])

    def test_offline_uncached_metadata_does_not_attempt_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, _revision = self._source(root)
            store = GitStore(root / "cache", min_free_bytes=0)

            with patch.object(store, "_run", side_effect=AssertionError("git command attempted")):
                with self.assertRaisesRegex(RuntimeError, "offline|network.*required|not cached"):
                    store.select_metadata(
                        str(source),
                        cache_key="fixture",
                        source_mode="offline",
                    )

    def test_uncached_connectivity_failure_is_actionable_and_preserves_git_cause(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GitStore(Path(tmp) / "cache", min_free_bytes=0)
            failure = self._connectivity_error()
            with patch.object(store, "_run_refresh", side_effect=failure):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "not cached|network.*required|acquisition",
                ) as caught:
                    store.select_metadata(
                        "https://example.invalid/repo.git",
                        cache_key="fixture",
                        source_mode="prefer-fresh",
                    )
            self.assertIs(caught.exception.__cause__, failure)

    def test_uncached_auth_failure_is_not_reported_as_offline_connectivity(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GitStore(Path(tmp) / "cache", min_free_bytes=0)
            failure = self._auth_error()
            with patch.object(store, "_run_refresh", side_effect=failure):
                with self.assertRaises(RuntimeError) as caught:
                    store.select_metadata(
                        "https://example.invalid/private.git",
                        cache_key="fixture",
                        source_mode="prefer-fresh",
                    )
            message = str(caught.exception)
            self.assertRegex(message, "acquisition|authentication|repository|cached state")
            self.assertNotRegex(message, "offline|network.*required")
            self.assertIs(caught.exception.__cause__, failure)


if __name__ == "__main__":
    unittest.main()
