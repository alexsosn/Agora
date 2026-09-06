from __future__ import annotations

import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog, ResourceSpec
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.network import NetworkUnavailableError
from agora_context_fabric.resolver import ContextFabricResolver
from agora_context_fabric.service import ContextFabricService


class RecordingLoader:
    def __init__(self) -> None:
        self.loads: list[tuple[str, str | None, object]] = []
        self.unloads: list[str] = []

    def load(self, path: str, name: str | None = None, features=None):
        self.loads.append((path, name, features))
        return {"path": path, "name": name, "features": features}

    def unload(self, logical_name: str) -> None:
        self.unloads.append(logical_name)


class ProductionOfflineIntegrationTests(unittest.TestCase):
    @staticmethod
    def _init_repo(source: Path) -> None:
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=source, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=source, check=True)
        subprocess.run(["git", "config", "user.name", "Agora Tests"], cwd=source, check=True)
        tf = source / "tf" / "1.0"
        tf.mkdir(parents=True)
        (tf / "otype.tf").write_text("@node\n", encoding="utf-8")
        (tf / "word.tf").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=source, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=source, check=True)

    @staticmethod
    def _resolver(
        repository: str,
        store: GitStore,
        *,
        ref: str | None = None,
    ) -> ContextFabricResolver:
        resource = ResourceSpec(
            id="fixture",
            name="Fixture corpus",
            plugin="context-fabric",
            provider="context-fabric",
            kind="corpus",
            repository=repository,
            ref=ref,
            languages=("test",),
            disciplines=("testing",),
        )
        return ContextFabricResolver(Catalog([resource]), store)

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    @staticmethod
    def _wait_for_listener(port: int) -> None:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("git daemon did not start")

    @staticmethod
    def _daemon(root: Path, port: int) -> subprocess.Popen[str]:
        return subprocess.Popen(
            [
                "git",
                "daemon",
                "--reuseaddr",
                "--export-all",
                f"--base-path={root}",
                "--listen=127.0.0.1",
                f"--port={port}",
                str(root),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

    @staticmethod
    def _stop_daemon(daemon: subprocess.Popen[str]) -> None:
        daemon.terminate()
        daemon.wait(timeout=5)
        if daemon.stderr is not None:
            daemon.stderr.close()

    def test_auto_fallback_handles_real_git_connectivity_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            work.mkdir()
            self._init_repo(work)
            remote = root / "remote.git"
            subprocess.run(["git", "clone", "-q", "--bare", str(work), str(remote)], check=True)

            port = self._free_port()
            daemon = self._daemon(root, port)
            try:
                self._wait_for_listener(port)
                repository = f"git://127.0.0.1:{port}/remote.git"
                store = GitStore(root / "cache")
                resolver = self._resolver(repository, store)
                first = resolver.prepare("fixture")
                self.assertEqual(first.resolution, "fresh")
                self.assertTrue(first.source_revision_verified)
                self.assertTrue((first.path / "otype.tf").is_file())
            finally:
                self._stop_daemon(daemon)

            second = resolver.prepare("fixture")
            self.assertEqual(second.path, first.path)
            self.assertEqual(second.source_revision, first.source_revision)
            self.assertEqual(second.resolution, "cached")
            self.assertFalse(second.source_revision_verified)

            loader = RecordingLoader()
            service = ContextFabricService(resolver.catalog, resolver, loader)
            loaded = service.load("fixture")
            self.assertEqual(loaded["path"], str(first.path))
            self.assertEqual(loaded["source_revision"], first.source_revision)
            self.assertEqual(loaded["resolution"], "cached")
            self.assertFalse(loaded["source_revision_verified"])
            self.assertEqual(loaded["cache_residency"], "leased")
            self.assertEqual(loader.loads, [(str(first.path), "fixture", None)])

            unloaded = service.unload(loaded["logical_name"])
            self.assertTrue(unloaded["was_loaded"])
            self.assertEqual(loader.unloads, ["fixture"])

            uncached = GitStore(root / "empty-cache")
            with self.assertRaises(NetworkUnavailableError):
                self._resolver(repository, uncached).prepare("fixture")

    def test_auto_fallback_preserves_legacy_mutable_ref_evidence_after_real_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            work.mkdir()
            self._init_repo(work)
            remote = root / "remote.git"
            subprocess.run(["git", "clone", "-q", "--bare", str(work), str(remote)], check=True)

            port = self._free_port()
            daemon = self._daemon(root, port)
            try:
                self._wait_for_listener(port)
                repository = f"git://127.0.0.1:{port}/remote.git"
                store = GitStore(root / "cache")
                resolver = self._resolver(repository, store, ref="main")
                first = resolver.prepare("fixture")
                record = store.repositories_dir / "fixture" / ".git" / "agora-selection.json"
                self.assertTrue(record.is_file())
                record.unlink()
            finally:
                self._stop_daemon(daemon)

            second = resolver.prepare("fixture")
            self.assertEqual(second.path, first.path)
            self.assertEqual(second.source_revision, first.source_revision)
            self.assertEqual(second.resolution, "cached")
            self.assertFalse(second.source_revision_verified)


if __name__ == "__main__":
    unittest.main()
