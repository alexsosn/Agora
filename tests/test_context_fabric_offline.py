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
from agora_context_fabric.network import (
    NetworkUnavailableError,
    OfflineCacheMissError,
    RemoteResolutionError,
    current_network_mode,
    resolve_repository,
    use_network_mode,
    validate_network_mode,
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


class OfflineRepositoryResolutionTests(unittest.TestCase):
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

    def _init_repo(self, source: Path) -> str:
        self._git(source, "init", "-q", "-b", "main")
        self._git(source, "config", "user.email", "tests@example.invalid")
        self._git(source, "config", "user.name", "Agora Tests")
        tf = source / "tf" / "1.0"
        tf.mkdir(parents=True)
        (tf / "otype.tf").write_text("@node\n", encoding="utf-8")
        (tf / "word.tf").write_text("fixture\n", encoding="utf-8")
        self._git(source, "add", ".")
        self._git(source, "commit", "-qm", "fixture")
        return self._git(source, "rev-parse", "HEAD")

    @staticmethod
    def _resolve(
        store: GitStore,
        source: Path,
        *,
        configured_ref: str | None = None,
    ):
        return resolve_repository(
            store,
            resource_id="fixture",
            repository=str(source),
            configured_ref=configured_ref,
        )

    @staticmethod
    def _selection_record(store: GitStore) -> Path:
        return store.repositories_dir / "fixture" / ".git" / "agora-selection.json"

    def test_network_mode_validation_and_scope_are_request_local(self):
        self.assertEqual(validate_network_mode(" OFFLINE "), "offline")
        with self.assertRaises(ValueError):
            validate_network_mode("sometimes")

        original = current_network_mode()
        with use_network_mode("offline"):
            self.assertEqual(current_network_mode(), "offline")
            with use_network_mode("require-fresh"):
                self.assertEqual(current_network_mode(), "require-fresh")
            self.assertEqual(current_network_mode(), "offline")
        self.assertEqual(current_network_mode(), original)

    def test_fresh_resolution_records_identity_and_auto_falls_back_only_on_connectivity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            revision = self._init_repo(source)
            store = ControlledNetworkGitStore(root / "cache")

            fresh = self._resolve(store, source)
            self.assertEqual(fresh.revision, revision)
            self.assertTrue(fresh.source_revision_verified)
            self.assertEqual(fresh.resolution, "fresh")
            self.assertTrue(self._selection_record(store).is_file())

            store.fail_fetches = True
            attempts = store.fetch_attempts
            with use_network_mode("auto"):
                cached = self._resolve(store, source)
            self.assertEqual(cached.revision, revision)
            self.assertFalse(cached.source_revision_verified)
            self.assertEqual(cached.resolution, "cached")
            self.assertFalse(cached.allow_network)
            self.assertEqual(store.fetch_attempts, attempts + 1)

            store.failure_stderr = "fatal: Authentication failed for upstream"
            with self.assertRaisesRegex(RemoteResolutionError, "Authentication failed"):
                with use_network_mode("auto"):
                    self._resolve(store, source)

    def test_offline_uncached_skips_clone_and_require_fresh_never_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            self._init_repo(source)
            store = ControlledNetworkGitStore(root / "cache")

            with self.assertRaisesRegex(OfflineCacheMissError, "fixture.*network"):
                with use_network_mode("offline"):
                    self._resolve(store, source)
            self.assertEqual(store.clone_attempts, 0)
            self.assertEqual(store.fetch_attempts, 0)

            self._resolve(store, source)
            store.fail_fetches = True
            with self.assertRaisesRegex(NetworkUnavailableError, "fixture.*network"):
                with use_network_mode("require-fresh"):
                    self._resolve(store, source)

    def test_persisted_selection_rejects_every_configured_ref_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            self._init_repo(source)
            store = ControlledNetworkGitStore(root / "cache")

            self._resolve(store, source, configured_ref="main")
            with self.assertRaisesRegex(OfflineCacheMissError, "repository/ref"):
                with use_network_mode("offline"):
                    self._resolve(store, source, configured_ref=None)
            with self.assertRaisesRegex(OfflineCacheMissError, "repository/ref"):
                with use_network_mode("offline"):
                    self._resolve(store, source, configured_ref="other")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            self._init_repo(source)
            store = ControlledNetworkGitStore(root / "cache")
            self._resolve(store, source, configured_ref=None)
            with self.assertRaisesRegex(OfflineCacheMissError, "repository/ref"):
                with use_network_mode("offline"):
                    self._resolve(store, source, configured_ref="main")

    def test_malformed_selection_record_fails_closed_instead_of_using_legacy_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            self._init_repo(source)
            store = ControlledNetworkGitStore(root / "cache")
            self._resolve(store, source)
            self._selection_record(store).write_text("{not-json", encoding="utf-8")

            with self.assertRaisesRegex(OfflineCacheMissError, "repository/ref"):
                with use_network_mode("offline"):
                    self._resolve(store, source)

    def test_legacy_floating_and_immutable_selections_are_migration_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            revision = self._init_repo(source)
            store = ControlledNetworkGitStore(root / "cache")

            self._resolve(store, source)
            self._selection_record(store).unlink()
            with use_network_mode("offline"):
                floating = self._resolve(store, source)
            self.assertEqual(floating.revision, revision)
            self.assertFalse(floating.source_revision_verified)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            revision = self._init_repo(source)
            store = ControlledNetworkGitStore(root / "cache")

            self._resolve(store, source, configured_ref=revision)
            self._selection_record(store).unlink()
            with use_network_mode("offline"):
                immutable = self._resolve(store, source, configured_ref=revision)
            self.assertEqual(immutable.revision, revision)
            self.assertTrue(immutable.source_revision_verified)

    def test_legacy_mutable_ref_requires_unambiguous_fetch_head_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            revision = self._init_repo(source)
            store = ControlledNetworkGitStore(root / "cache")

            self._resolve(store, source, configured_ref="main")
            self._selection_record(store).unlink()
            with use_network_mode("offline"):
                migrated = self._resolve(store, source, configured_ref="main")
            self.assertEqual(migrated.revision, revision)
            self.assertFalse(migrated.source_revision_verified)

            with self.assertRaisesRegex(OfflineCacheMissError, "repository/ref"):
                with use_network_mode("offline"):
                    self._resolve(store, source, configured_ref="other")

            fetch_head = store.repositories_dir / "fixture" / ".git" / "FETCH_HEAD"
            fetch_head.write_text(
                f"{revision}\t\tbranch 'main' of one\n"
                f"{revision}\t\tbranch 'main' of two\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(OfflineCacheMissError, "repository/ref"):
                with use_network_mode("offline"):
                    self._resolve(store, source, configured_ref="main")


class ResolverOfflineIntegrationTests(unittest.TestCase):
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

    def _init_corpus(self, source: Path) -> str:
        self._git(source, "init", "-q", "-b", "main")
        self._git(source, "config", "user.email", "tests@example.invalid")
        self._git(source, "config", "user.name", "Agora Tests")
        tf = source / "tf" / "1.0"
        tf.mkdir(parents=True)
        (tf / "otype.tf").write_text("@node\n", encoding="utf-8")
        (tf / "word.tf").write_text("fixture\n", encoding="utf-8")
        self._git(source, "add", ".")
        self._git(source, "commit", "-qm", "fixture corpus")
        return self._git(source, "rev-parse", "HEAD")

    def _init_collection(self, source: Path) -> str:
        self._git(source, "init", "-q", "-b", "main")
        self._git(source, "config", "user.email", "tests@example.invalid")
        self._git(source, "config", "user.name", "Agora Tests")
        tf = source / "Author" / "Work" / "tf" / "1.0"
        tf.mkdir(parents=True)
        (tf / "otype.tf").write_text("@node\n", encoding="utf-8")
        (tf / "word.tf").write_text("collection fixture\n", encoding="utf-8")
        self._git(source, "add", ".")
        self._git(source, "commit", "-qm", "fixture collection")
        return self._git(source, "rev-parse", "HEAD")

    @staticmethod
    def _corpus_resolver(
        source: Path,
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
            repository=str(source),
            ref=ref,
            languages=("test",),
            disciplines=("testing",),
        )
        return ContextFabricResolver(Catalog([resource]), store)

    @staticmethod
    def _collection_resolver(source: Path, store: GitStore) -> ContextFabricResolver:
        resource = ResourceSpec(
            id="collection",
            name="Fixture collection",
            plugin="context-fabric",
            provider="context-fabric",
            kind="collection",
            repository=str(source),
            languages=("test",),
            disciplines=("testing",),
        )
        return ContextFabricResolver(Catalog([resource]), store)

    def test_auto_and_offline_reuse_complete_corpus_snapshot_with_honest_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            revision = self._init_corpus(source)
            store = ControlledNetworkGitStore(root / "cache")
            resolver = self._corpus_resolver(source, store)

            first = resolver.prepare("fixture")
            self.assertEqual(first.source_revision, revision)
            self.assertEqual(first.resolution, "fresh")
            self.assertTrue(first.source_revision_verified)
            self.assertTrue((first.path / "otype.tf").is_file())

            store.fail_fetches = True
            attempts = store.fetch_attempts
            with use_network_mode("auto"):
                automatic = resolver.prepare("fixture")
            self.assertEqual(automatic.path, first.path)
            self.assertEqual(automatic.source_revision, revision)
            self.assertEqual(automatic.resolution, "cached")
            self.assertFalse(automatic.source_revision_verified)
            self.assertEqual(store.fetch_attempts, attempts + 1)

            attempts = store.fetch_attempts
            with use_network_mode("offline"):
                offline = resolver.prepare("fixture")
            self.assertEqual(offline.path, first.path)
            self.assertEqual(offline.resolution, "cached")
            self.assertEqual(store.fetch_attempts, attempts)

    def test_offline_metadata_only_cache_fails_without_snapshot_export_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            self._init_corpus(source)
            store = ControlledNetworkGitStore(root / "cache")
            # Establish the pre-#44 metadata-only state without a source snapshot.
            store.ensure_metadata(str(source), cache_key="fixture")
            attempts = store.fetch_attempts
            store.fail_fetches = True
            resolver = self._corpus_resolver(source, store)

            with self.assertRaisesRegex(OfflineCacheMissError, "materialized.*fixture"):
                with use_network_mode("offline"):
                    resolver.prepare("fixture")
            self.assertEqual(store.fetch_attempts, attempts)

    def test_immutable_pinned_corpus_snapshot_remains_verifiable_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            revision = self._init_corpus(source)
            store = ControlledNetworkGitStore(root / "cache")
            resolver = self._corpus_resolver(source, store, ref=revision)
            first = resolver.prepare("fixture")
            store.fail_fetches = True
            attempts = store.fetch_attempts

            with use_network_mode("offline"):
                second = resolver.prepare("fixture")
            self.assertEqual(second.path, first.path)
            self.assertEqual(second.source_revision, revision)
            self.assertEqual(second.resolution, "cached")
            self.assertTrue(second.source_revision_verified)
            self.assertEqual(store.fetch_attempts, attempts)

    def test_current_collection_resolution_reuses_same_commit_bound_member_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            revision = self._init_collection(source)
            store = ControlledNetworkGitStore(root / "cache")
            resolver = self._collection_resolver(source, store)

            listing = resolver.resolve_members("collection")
            self.assertEqual(listing.source_revision, revision)
            member = listing.members[0]
            first = resolver.prepare("collection", member_id=member.id)
            self.assertEqual(first.source_revision, revision)

            store.fail_fetches = True
            attempts = store.fetch_attempts
            with use_network_mode("auto"):
                second = resolver.prepare("collection", member_id=member.id)
            self.assertEqual(second.path, first.path)
            self.assertEqual(second.source_revision, revision)
            self.assertEqual(second.resolution, "cached")
            self.assertFalse(second.source_revision_verified)
            self.assertEqual(store.fetch_attempts, attempts + 1)

    def test_exact_collection_revision_missing_member_bytes_fails_offline_without_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            revision = self._init_collection(source)
            store = ControlledNetworkGitStore(root / "cache")
            resolver = self._collection_resolver(source, store)
            listing = resolver.resolve_members("collection")
            member = listing.members[0]
            self.assertEqual(listing.source_revision, revision)
            attempts = store.fetch_attempts
            store.fail_fetches = True

            with self.assertRaisesRegex(OfflineCacheMissError, "materialized.*collection"):
                with use_network_mode("offline"):
                    resolver.prepare(
                        "collection",
                        member_id=member.id,
                        source_revision=revision,
                    )
            self.assertEqual(store.fetch_attempts, attempts)


if __name__ == "__main__":
    unittest.main()
