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
from agora_context_fabric.mcp_tools import register_tools
from agora_context_fabric.network import (
    NetworkUnavailableError,
    OfflineCacheMissError,
    RemoteResolutionError,
    current_network_mode,
    use_network_mode,
)
from agora_context_fabric.resolver import ContextFabricResolver


class ControlledNetworkGitStore(GitStore):
    def __init__(self, cache_dir: Path) -> None:
        super().__init__(cache_dir, snapshot_soft_limit_bytes=0, min_free_bytes=0)
        self.fail_fetches = False
        self.fail_clones = False
        self.failure_stderr = (
            "fatal: unable to access 'https://example.invalid/repo.git/': "
            "Could not resolve host: example.invalid"
        )
        self.fetch_attempts = 0
        self.clone_attempts = 0

    def _network_failure(self, operation: str) -> subprocess.CalledProcessError:
        return subprocess.CalledProcessError(
            128,
            ["git", operation],
            stderr=self.failure_stderr,
        )

    def _run(self, *args: str, cwd: Path | None = None) -> str:
        if args and args[0] == "fetch":
            self.fetch_attempts += 1
            if self.fail_fetches:
                raise self._network_failure("fetch")
        if args and args[0] == "clone":
            self.clone_attempts += 1
            if self.fail_clones:
                raise self._network_failure("clone")
        return super()._run(*args, cwd=cwd)


class OfflineCacheTests(unittest.TestCase):
    @staticmethod
    def _init_repo(source: Path) -> str:
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=source, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=source, check=True)
        subprocess.run(["git", "config", "user.name", "Agora Tests"], cwd=source, check=True)
        tf = source / "tf" / "1.0"
        tf.mkdir(parents=True)
        (tf / "otype.tf").write_text("@node\n", encoding="utf-8")
        (tf / "word.tf").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=source, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=source, check=True)
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=source,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()

    @staticmethod
    def _resolver(source: Path, store: GitStore, *, ref: str | None = None) -> ContextFabricResolver:
        resource = ResourceSpec(
            id="fixture",
            name="Fixture corpus",
            plugin="context-fabric",
            provider="context-fabric",
            kind="corpus",
            repository=str(source),
            ref=ref,
            languages=("test",),
            disciplines=("testing",),
        )
        return ContextFabricResolver(Catalog([resource]), store)

    def test_auto_mode_reuses_complete_snapshot_after_connectivity_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            self._init_repo(source)
            store = ControlledNetworkGitStore(root / "cache")
            resolver = self._resolver(source, store)

            first = resolver.prepare("fixture")
            self.assertTrue((first.path / "otype.tf").is_file())
            self.assertTrue(first.source_revision_verified)
            self.assertEqual(first.resolution, "fresh")

            store.fail_fetches = True
            attempts_before = store.fetch_attempts
            with use_network_mode("auto"):
                second = resolver.prepare("fixture")

            self.assertEqual(second.path, first.path)
            self.assertEqual(second.source_revision, first.source_revision)
            self.assertFalse(second.source_revision_verified)
            self.assertEqual(second.resolution, "cached")
            self.assertEqual(store.fetch_attempts, attempts_before + 1)

    def test_offline_mode_skips_fetch_for_complete_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            self._init_repo(source)
            store = ControlledNetworkGitStore(root / "cache")
            resolver = self._resolver(source, store)
            first = resolver.prepare("fixture")

            store.fail_fetches = True
            attempts_before = store.fetch_attempts
            with use_network_mode("offline"):
                second = resolver.prepare("fixture")

            self.assertEqual(second.path, first.path)
            self.assertEqual(store.fetch_attempts, attempts_before)
            self.assertFalse(second.source_revision_verified)
            self.assertEqual(second.resolution, "cached")

    def test_require_fresh_does_not_fallback_to_cached_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            self._init_repo(source)
            store = ControlledNetworkGitStore(root / "cache")
            resolver = self._resolver(source, store)
            resolver.prepare("fixture")
            store.fail_fetches = True

            with self.assertRaisesRegex(NetworkUnavailableError, "fixture.*network"):
                with use_network_mode("require-fresh"):
                    resolver.prepare("fixture")

    def test_non_connectivity_remote_failure_is_not_hidden_by_cache_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            self._init_repo(source)
            store = ControlledNetworkGitStore(root / "cache")
            resolver = self._resolver(source, store)
            resolver.prepare("fixture")
            store.failure_stderr = "fatal: Authentication failed for 'https://example.invalid/private.git/'"
            store.fail_fetches = True

            with self.assertRaisesRegex(RemoteResolutionError, "Authentication failed"):
                with use_network_mode("auto"):
                    resolver.prepare("fixture")

    def test_uncached_offline_resource_fails_without_network_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            self._init_repo(source)
            store = ControlledNetworkGitStore(root / "cache")
            resolver = self._resolver(source, store)

            with self.assertRaisesRegex(OfflineCacheMissError, "fixture.*network"):
                with use_network_mode("offline"):
                    resolver.prepare("fixture")
            self.assertEqual(store.clone_attempts, 0)
            self.assertEqual(store.fetch_attempts, 0)

    def test_uncached_connectivity_failure_is_actionable_not_called_process_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            self._init_repo(source)
            store = ControlledNetworkGitStore(root / "cache")
            store.fail_clones = True
            resolver = self._resolver(source, store)

            with self.assertRaisesRegex(NetworkUnavailableError, "fixture.*network"):
                with use_network_mode("auto"):
                    resolver.prepare("fixture")

    def test_offline_metadata_without_materialized_snapshot_fails_before_export_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            self._init_repo(source)
            store = ControlledNetworkGitStore(root / "cache")
            resolver = self._resolver(source, store)
            store.ensure_metadata(str(source), cache_key="fixture")
            attempts_before = store.fetch_attempts

            with self.assertRaisesRegex(OfflineCacheMissError, "materialized.*fixture"):
                with use_network_mode("offline"):
                    resolver.prepare("fixture")
            self.assertEqual(store.fetch_attempts, attempts_before)

    def test_immutable_pinned_revision_is_verifiable_offline_once_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            revision = self._init_repo(source)
            store = ControlledNetworkGitStore(root / "cache")
            resolver = self._resolver(source, store, ref=revision)
            first = resolver.prepare("fixture")
            attempts_before = store.fetch_attempts

            with use_network_mode("offline"):
                second = resolver.prepare("fixture")

            self.assertEqual(second.source_revision, revision)
            self.assertEqual(second.path, first.path)
            self.assertTrue(second.source_revision_verified)
            self.assertEqual(second.resolution, "cached")
            self.assertEqual(store.fetch_attempts, attempts_before)


class FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, name: str | None = None):
        def decorator(func):
            self.tools[name or func.__name__] = func
            return func

        return decorator


class NetworkModeService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def prepare(self, resource_id: str, **_kwargs):
        self.calls.append(("prepare", current_network_mode()))
        return {"resource_id": resource_id}

    def load(self, resource_id: str, **_kwargs):
        self.calls.append(("load", current_network_mode()))
        return {"resource_id": resource_id}

    def __getattr__(self, name: str):
        def unused(*_args, **_kwargs):
            raise AssertionError(f"unexpected service call: {name}")

        return unused


class NetworkModeToolTests(unittest.TestCase):
    def test_prepare_and_load_tools_expose_network_mode(self):
        mcp = FakeMCP()
        service = NetworkModeService()
        register_tools(mcp, service)

        mcp.tools["prepare_corpus"]("fixture", network_mode="offline")
        mcp.tools["load_corpus"]("fixture", network_mode="require-fresh")

        self.assertEqual(service.calls, [("prepare", "offline"), ("load", "require-fresh")])

    def test_invalid_network_mode_is_rejected_before_service_call(self):
        mcp = FakeMCP()
        service = NetworkModeService()
        register_tools(mcp, service)

        with self.assertRaises(ValueError):
            mcp.tools["prepare_corpus"]("fixture", network_mode="sometimes")
        self.assertEqual(service.calls, [])


if __name__ == "__main__":
    unittest.main()
