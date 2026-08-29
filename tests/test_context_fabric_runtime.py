from __future__ import annotations

import json
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
from agora_context_fabric.resolver import (
    CollectionMember,
    ContextFabricResolver,
    PreparedCorpus,
    member_id_from_path,
    select_dataset_root,
)
from agora_context_fabric.service import ContextFabricService


class CatalogTests(unittest.TestCase):
    def test_catalog_contains_exact_v01_context_fabric_scope(self):
        catalog = Catalog.from_registry(ROOT)
        with (ROOT / "registry/v0.1.yaml").open("r", encoding="utf-8") as fh:
            import yaml

            scope = yaml.safe_load(fh)
        self.assertEqual(catalog.ids(), scope["required_resources"])

    def test_catalog_preserves_collection_semantics(self):
        catalog = Catalog.from_registry(ROOT)
        for resource_id in ("bible", "patristics", "greek_literature", "translatin-manif"):
            resource = catalog.get(resource_id)
            self.assertEqual(resource.kind, "collection")
            self.assertIsNotNone(resource.member_index)


class SelectionTests(unittest.TestCase):
    def test_select_dataset_root_prefers_highest_version_under_tf(self):
        roots = ["tf/0.1", "tf/0.9", "tf/0.10", "docs/tf/99"]
        self.assertEqual(select_dataset_root(roots), "tf/0.10")

    def test_select_dataset_root_rejects_empty_candidate_set(self):
        with self.assertRaises(ValueError):
            select_dataset_root([])

    def test_member_id_is_stable_and_path_sensitive(self):
        a = member_id_from_path("Homer/Iliad/tf/1.0")
        b = member_id_from_path("Homer/Iliad/tf/2.0")
        c = member_id_from_path("Homer/Odyssey/tf/1.0")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)


class GitStoreTests(unittest.TestCase):
    def _make_repository(self, root: Path) -> Path:
        source = root / "source"
        source.mkdir()
        import subprocess

        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=source, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=source, check=True)
        subprocess.run(["git", "config", "user.name", "Agora Tests"], cwd=source, check=True)
        for version in ("1.0", "2.0"):
            tf = source / "tf" / version
            tf.mkdir(parents=True)
            (tf / "otype.tf").write_text("@node\n", encoding="utf-8")
            (tf / "word.tf").write_text(f"version-{version}\n", encoding="utf-8")
        large = source / "unrelated-large-file.bin"
        large.write_bytes(b"x" * 1024)
        subprocess.run(["git", "add", "."], cwd=source, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=source, check=True)
        return source

    def test_metadata_clone_discovers_dataset_roots_without_full_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = self._make_repository(tmp_path)
            store = GitStore(tmp_path / "cache")
            repo = store.ensure_metadata(str(source), cache_key="fixture")
            self.assertEqual(store.dataset_roots(repo), ["tf/1.0", "tf/2.0"])
            self.assertFalse((repo / "unrelated-large-file.bin").exists())
            self.assertFalse((repo / "tf/1.0/otype.tf").exists())

    def test_materialize_fetches_only_selected_dataset_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = self._make_repository(tmp_path)
            store = GitStore(tmp_path / "cache")
            repo = store.ensure_metadata(str(source), cache_key="fixture")
            selected = store.materialize(repo, "tf/2.0")
            self.assertTrue((selected / "otype.tf").is_file())
            self.assertFalse((repo / "tf/1.0/otype.tf").exists())
            self.assertFalse((repo / "unrelated-large-file.bin").exists())


class ResolverTests(unittest.TestCase):
    def _make_collection_repository(self, root: Path) -> Path:
        source = root / "collection-source"
        source.mkdir()
        import subprocess

        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=source, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=source, check=True)
        subprocess.run(["git", "config", "user.name", "Agora Tests"], cwd=source, check=True)
        datasets = [
            "Homer/Iliad/tf/1.0",
            "Homer/Iliad/tf/2.0",
            "Homer/Odyssey/tf/1.0",
        ]
        for dataset in datasets:
            tf = source / dataset
            tf.mkdir(parents=True)
            (tf / "otype.tf").write_text("@node\n", encoding="utf-8")
            (tf / "text.tf").write_text(dataset, encoding="utf-8")
        (source / "huge-source.xml").write_bytes(b"z" * 2048)
        subprocess.run(["git", "add", "."], cwd=source, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=source, check=True)
        return source

    def test_prepare_ordinary_resource_selects_latest_tf_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = GitStoreTests()._make_repository(tmp_path)
            catalog = Catalog(
                [
                    ResourceSpec(
                        id="fixture",
                        name="Fixture corpus",
                        plugin="context-fabric",
                        provider="context-fabric",
                        kind="corpus",
                        repository=str(source),
                        languages=("test",),
                        disciplines=("testing",),
                    )
                ]
            )
            resolver = ContextFabricResolver(catalog, GitStore(tmp_path / "cache"))
            prepared = resolver.prepare("fixture")
            self.assertEqual(prepared.relative_path, "tf/2.0")
            self.assertEqual(prepared.logical_name, "fixture")
            self.assertTrue((prepared.path / "otype.tf").is_file())

    def test_collection_members_are_discovered_and_loaded_individually(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = self._make_collection_repository(tmp_path)
            catalog = Catalog(
                [
                    ResourceSpec(
                        id="greek",
                        name="Greek fixture",
                        plugin="context-fabric",
                        provider="context-fabric",
                        kind="collection",
                        repository=str(source),
                        languages=("greek",),
                        disciplines=("classics",),
                    )
                ]
            )
            resolver = ContextFabricResolver(catalog, GitStore(tmp_path / "cache"))
            members = resolver.list_members("greek")
            self.assertEqual(len(members), 2)
            iliad = next(member for member in members if member.title == "Iliad")
            self.assertEqual(iliad.relative_path, "Homer/Iliad/tf/2.0")
            prepared = resolver.prepare("greek", member_id=iliad.id)
            self.assertEqual(prepared.relative_path, "Homer/Iliad/tf/2.0")
            self.assertTrue((prepared.path / "otype.tf").is_file())
            self.assertFalse((prepared.path.parents[3] / "huge-source.xml").exists())

    def test_collection_requires_member_id_for_prepare(self):
        resource = ResourceSpec(
            id="greek",
            name="Greek fixture",
            plugin="context-fabric",
            provider="context-fabric",
            kind="collection",
            repository="unused/repository",
            languages=("greek",),
            disciplines=("classics",),
        )
        catalog = Catalog([resource])

        class NoCloneStore:
            def ensure_metadata(self, *_args, **_kwargs):
                raise AssertionError("collection validation must happen before cloning")

        resolver = ContextFabricResolver(catalog, NoCloneStore())
        with self.assertRaisesRegex(ValueError, "member_id is required"):
            resolver.prepare("greek")


class FakeResolver:
    def list_members(self, resource_id: str):
        return [
            CollectionMember(
                id="iliad-a1b2c3d4",
                resource_id=resource_id,
                relative_path="Homer/Iliad/tf/1.0",
                identity_path="Homer/Iliad",
                author="Homer",
                title="Iliad",
            ),
            CollectionMember(
                id="odyssey-e5f6a7b8",
                resource_id=resource_id,
                relative_path="Homer/Odyssey/tf/1.0",
                identity_path="Homer/Odyssey",
                author="Homer",
                title="Odyssey",
            ),
        ]

    def search_members(self, resource_id: str, query: str):
        return [
            member
            for member in self.list_members(resource_id)
            if query.casefold() in f"{member.author} {member.title}".casefold()
        ]

    def prepare(self, resource_id: str, *, member_id: str | None = None):
        return PreparedCorpus(
            resource_id=resource_id,
            member_id=member_id,
            logical_name=resource_id if member_id is None else f"{resource_id}:{member_id}",
            relative_path="tf/1.0",
            path=Path("/tmp/agora-fixture/tf/1.0"),
        )


class FakeLoader:
    def __init__(self):
        self.calls: list[tuple[str, str | None, object]] = []

    def load(self, path: str, name: str | None = None, features=None):
        self.calls.append((path, name, features))
        return {"name": name, "path": path, "features": features}


class ServiceTests(unittest.TestCase):
    def test_resource_discovery_filters_the_canonical_catalog(self):
        service = ContextFabricService(
            Catalog.from_registry(ROOT),
            FakeResolver(),
            FakeLoader(),
        )

        hittite = service.list_resources(language="hittite")
        self.assertEqual([item["id"] for item in hittite], ["TLHdig-TF"])

        collections = service.list_resources(kind="collection")
        self.assertEqual(
            {item["id"] for item in collections},
            {"bible", "patristics", "greek_literature", "translatin-manif"},
        )

        dead = service.list_resources(query="dead sea")
        self.assertEqual([item["id"] for item in dead], ["dss"])

    def test_collection_member_search_is_paginated(self):
        greek = ResourceSpec(
            id="greek",
            name="Greek fixture",
            plugin="context-fabric",
            provider="context-fabric",
            kind="collection",
            repository="unused/repository",
            languages=("greek",),
            disciplines=("classics",),
        )
        service = ContextFabricService(
            Catalog([greek]),
            FakeResolver(),
            FakeLoader(),
        )
        page = service.list_collection_members("greek", query="homer", offset=1, limit=1)
        self.assertEqual(page["total"], 2)
        self.assertEqual(page["offset"], 1)
        self.assertEqual(page["limit"], 1)
        self.assertEqual([item["title"] for item in page["items"]], ["Odyssey"])

    def test_pagination_arguments_are_validated_before_resolution(self):
        greek = ResourceSpec(
            id="greek",
            name="Greek fixture",
            plugin="context-fabric",
            provider="context-fabric",
            kind="collection",
            repository="unused/repository",
            languages=("greek",),
            disciplines=("classics",),
        )
        service = ContextFabricService(
            Catalog([greek]),
            FakeResolver(),
            FakeLoader(),
        )
        with self.assertRaises(ValueError):
            service.list_collection_members("greek", offset=-1, limit=5)
        with self.assertRaises(ValueError):
            service.list_collection_members("greek", offset=0, limit=0)
        with self.assertRaises(ValueError):
            service.list_collection_members("greek", offset=0, limit=101)

    def test_loading_prepares_then_delegates_to_corpus_manager(self):
        corpus = ResourceSpec(
            id="fixture",
            name="Fixture",
            plugin="context-fabric",
            provider="context-fabric",
            kind="corpus",
            repository="unused/repository",
            languages=("test",),
            disciplines=("testing",),
        )
        loader = FakeLoader()
        service = ContextFabricService(Catalog([corpus]), FakeResolver(), loader)
        result = service.load_resource("fixture", features=["lex", "sp"])
        self.assertEqual(result["resource_id"], "fixture")
        self.assertEqual(result["logical_name"], "fixture")
        self.assertEqual(result["features"], ["lex", "sp"])
        self.assertEqual(
            loader.calls,
            [("/tmp/agora-fixture/tf/1.0", "fixture", ["lex", "sp"])],
        )


if __name__ == "__main__":
    unittest.main()
