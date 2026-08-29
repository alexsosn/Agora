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
from agora_context_fabric.resolver import ContextFabricResolver


class PinnedGitStoreTests(unittest.TestCase):
    def _make_repository(self, root: Path) -> tuple[Path, str, str]:
        source = root / "source"
        source.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=source, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=source, check=True)
        subprocess.run(["git", "config", "user.name", "Agora Tests"], cwd=source, check=True)

        first = source / "tf" / "1.0"
        first.mkdir(parents=True)
        (first / "otype.tf").write_text("@node\n", encoding="utf-8")
        (first / "word.tf").write_text("first\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=source, check=True)
        subprocess.run(["git", "commit", "-qm", "first"], cwd=source, check=True)
        first_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()

        second = source / "tf" / "2.0"
        second.mkdir(parents=True)
        (second / "otype.tf").write_text("@node\n", encoding="utf-8")
        (second / "word.tf").write_text("second\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=source, check=True)
        subprocess.run(["git", "commit", "-qm", "second"], cwd=source, check=True)
        second_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
        return source, first_sha, second_sha

    def test_pinned_ref_controls_metadata_discovery_and_materialization(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source, first_sha, _second_sha = self._make_repository(tmp_path)
            store = GitStore(tmp_path / "cache")
            repo = store.ensure_metadata(str(source), cache_key="fixture", ref=first_sha)
            self.assertEqual(store.dataset_roots(repo), ["tf/1.0"])
            selected = store.materialize(repo, "tf/1.0")
            self.assertEqual((selected / "word.tf").read_text(encoding="utf-8"), "first\n")
            self.assertFalse((repo / "tf/2.0/otype.tf").exists())

    def test_unpinned_metadata_uses_current_default_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source, _first_sha, _second_sha = self._make_repository(tmp_path)
            store = GitStore(tmp_path / "cache")
            repo = store.ensure_metadata(str(source), cache_key="fixture")
            self.assertEqual(store.dataset_roots(repo), ["tf/1.0", "tf/2.0"])


class PinnedCatalogTests(unittest.TestCase):
    def test_catalog_preserves_upstream_ref_and_tf_path(self):
        catalog = Catalog.from_registry(ROOT)
        tlhdig = catalog.get("TLHdig-TF")
        self.assertEqual(
            tlhdig.ref,
            "5d5e9af248566222738f8ac65ab8f9bb1b6aed3c",
        )
        self.assertEqual(tlhdig.tf_path, "tf/0.1.0")

    def test_translatin_is_a_collection(self):
        translatin = Catalog.from_registry(ROOT).get("translatin-manif")
        self.assertEqual(translatin.kind, "collection")
        self.assertIsNotNone(translatin.member_index)

    def test_resolver_honours_explicit_tf_path(self):
        class Store:
            def ensure_metadata(self, source, *, cache_key=None, ref=None):
                self.ref = ref
                return Path("/repo")

            def selected_revision(self, repo):
                return "a" * 40

            def dataset_roots(self, repo, revision=None):
                self.dataset_revision = revision
                return ["tf/0.1.0", "tf/999.0"]

            def materialize(self, repo, relative_path, revision=None):
                self.materialized = relative_path
                self.materialized_revision = revision
                return Path("/repo") / relative_path

        resource = ResourceSpec(
            id="fixture",
            name="Fixture",
            plugin="context-fabric",
            provider="context-fabric",
            kind="corpus",
            repository="example/fixture",
            languages=("hittite",),
            disciplines=("hittitology",),
            member_index=None,
            ref="abc123",
            tf_path="tf/0.1.0",
        )
        store = Store()
        prepared = ContextFabricResolver(Catalog([resource]), store).prepare("fixture")
        self.assertEqual(store.ref, "abc123")
        self.assertEqual(prepared.relative_path, "tf/0.1.0")
        self.assertEqual(prepared.source_revision, "a" * 40)
        self.assertEqual(store.dataset_revision, "a" * 40)
        self.assertEqual(store.materialized, "tf/0.1.0")
        self.assertEqual(store.materialized_revision, "a" * 40)


if __name__ == "__main__":
    unittest.main()
