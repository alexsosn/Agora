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
    def _resolver(repository: str, store: GitStore) -> ContextFabricResolver:
        resource = ResourceSpec(
            id="fixture",
            name="Fixture corpus",
            plugin="context-fabric",
            provider="context-fabric",
            kind="corpus",
            repository=repository,
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

    def test_auto_fallback_handles_real_git_connectivity_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            work.mkdir()
            self._init_repo(work)
            remote = root / "remote.git"
            subprocess.run(["git", "clone", "-q", "--bare", str(work), str(remote)], check=True)

            port = self._free_port()
            daemon = subprocess.Popen(
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
                daemon.terminate()
                daemon.wait(timeout=5)
                if daemon.stderr is not None:
                    daemon.stderr.close()

            second = resolver.prepare("fixture")
            self.assertEqual(second.path, first.path)
            self.assertEqual(second.source_revision, first.source_revision)
            self.assertEqual(second.resolution, "cached")
            self.assertFalse(second.source_revision_verified)

            uncached = GitStore(root / "empty-cache")
            with self.assertRaises(NetworkUnavailableError):
                self._resolver(repository, uncached).prepare("fixture")


if __name__ == "__main__":
    unittest.main()
