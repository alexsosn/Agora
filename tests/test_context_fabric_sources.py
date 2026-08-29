from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog, ResourceSpec
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.resolver import ContextFabricResolver


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def make_versioned_repo(root: Path) -> tuple[Path, str, str]:
    repo = root / "upstream"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    git(repo, "config", "user.email", "tests@example.invalid")
    git(repo, "config", "user.name", "Agora tests")

    first = repo / "tf" / "0.1.0" / "otype.tf"
    first.parent.mkdir(parents=True)
    first.write_text("published\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "published dataset")
    published_ref = git(repo, "rev-parse", "HEAD")

    subprocess.run(["rm", "-rf", str(repo / "tf")], check=True)
    (repo / "README.md").write_text("dataset regenerated elsewhere\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "remove generated dataset")
    current_ref = git(repo, "rev-parse", "HEAD")
    return repo, published_ref, current_ref


class PinnedGitStoreTests(unittest.TestCase):
    def test_pinned_ref_controls_metadata_discovery_and_materialization(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            upstream, published_ref, _current_ref = make_versioned_repo(tmp_path)
            store = GitStore(tmp_path / "cache")

            repo = store.ensure_metadata(
                str(upstream),
                cache_key="fixture",
                ref=published_ref,
            )

            self.assertEqual(store.dataset_roots(repo), ["tf/0.1.0"])
            local = store.materialize(repo, "tf/0.1.0")
            self.assertEqual(
                (local / "otype.tf").read_text(encoding="utf-8"),
                "published\n",
            )

    def test_unpinned_metadata_uses_current_default_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            upstream, _published_ref, _current_ref = make_versioned_repo(tmp_path)
            store = GitStore(tmp_path / "cache")
            repo = store.ensure_metadata(str(upstream), cache_key="fixture")
            self.assertEqual(store.dataset_roots(repo), [])


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

            def dataset_roots(self, repo):
                return ["tf/0.1.0", "tf/999.0"]

            def materialize(self, repo, relative_path):
                self.materialized = relative_path
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
        self.assertEqual(store.materialized, "tf/0.1.0")


if __name__ == "__main__":
    unittest.main()
