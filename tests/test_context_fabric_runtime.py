from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
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


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def make_git_repo(root: Path, files: dict[str, str]) -> Path:
    repo = root / "upstream"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    git(repo, "config", "user.email", "tests@example.invalid")
    git(repo, "config", "user.name", "Agora tests")
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "fixture")
    return repo


class CatalogTests(unittest.TestCase):
    def test_catalog_contains_exact_v01_context_fabric_scope(self):
        catalog = Catalog.from_registry(ROOT)
        with (ROOT / "registry" / "v0.1.yaml").open("r", encoding="utf-8") as fh:
            scope = yaml.safe_load(fh)

        self.assertEqual(set(catalog.ids()), set(scope["required_resources"]))
        self.assertEqual(len(catalog.ids()), 36)
        self.assertTrue(all(item.plugin == "context-fabric" for item in catalog.resources()))

    def test_catalog_preserves_collection_semantics(self):
        catalog = Catalog.from_registry(ROOT)
        for resource_id in ("bible", "patristics", "greek_literature"):
            resource = catalog.get(resource_id)
            self.assertEqual(resource.kind, "collection")
            self.assertIsNotNone(resource.member_index)


class SelectionTests(unittest.TestCase):
    def test_member_id_is_stable_and_path_sensitive(self):
        first = member_id_from_path("canonical-greekLit/tlg0012/tlg001/tf/1.0")
        second = member_id_from_path("canonical-greekLit/tlg0012/tlg002/tf/1.0")
        self.assertEqual(first, member_id_from_path("canonical-greekLit/tlg0012/tlg001/tf/1.0"))
        self.assertNotEqual(first, second)
        self.assertRegex(first, r"^[a-z0-9][a-z0-9-]*-[0-9a-f]{8}$")

    def test_select_dataset_root_prefers_highest_version_under_tf(self):
        roots = [
            "legacy/otype-root",
            "tf/0.1.0",
            "tf/0.10.0",
            "tf/0.2.0",
        ]
        self.assertEqual(select_dataset_root(roots), "tf/0.10.0")

    def test_select_dataset_root_rejects_empty_candidate_set(self):
        with self.assertRaisesRegex(ValueError, "no Text-Fabric dataset"):
            select_dataset_root([])


class GitStoreTests(unittest.TestCase):
    def test_metadata_clone_discovers_dataset_roots_without_full_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            upstream = make_git_repo(
                tmp_path,
                {
                    "tf/1.0/otype.tf": "@node\n",
                    "tf/2.0/otype.tf": "@node\n",
                    "tf/2.0/word.tf": "@node\n",
                    "README.md": "fixture\n",
                },
            )
            store = GitStore(tmp_path / "cache")
            repo = store.ensure_metadata(str(upstream), cache_key="fixture")

            self.assertEqual(store.dataset_roots(repo), ["tf/1.0", "tf/2.0"])
            self.assertFalse((repo / "README.md").exists())

    def test_materialize_fetches_only_selected_dataset_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            upstream = make_git_repo(
                tmp_path,
                {
                    "tf/1.0/otype.tf": "one\n",
                    "tf/2.0/otype.tf": "two\n",
                    "unrelated/large.txt": "not needed\n",
                },
            )
            store = GitStore(tmp_path / "cache")
            repo = store.ensure_metadata(str(upstream), cache_key="fixture")
            local = store.materialize(repo, "tf/2.0")

            self.assertEqual((local / "otype.tf").read_text(encoding="utf-8"), "two\n")
            self.assertFalse((repo / "unrelated" / "large.txt").exists())


class ResolverTests(unittest.TestCase):
    def test_prepare_ordinary_resource_selects_latest_tf_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            upstream = make_git_repo(
                tmp_path,
                {
                    "tf/0.9/otype.tf": "old\n",
                    "tf/1.0/otype.tf": "new\n",
                },
            )
            resource = ResourceSpec(
                id="fixture",
                name="Fixture",
                plugin="context-fabric",
                provider="context-fabric",
                kind="corpus",
                repository=str(upstream),
                languages=("greek",),
                disciplines=("classics",),
                member_index=None,
            )
            resolver = ContextFabricResolver(
                Catalog([resource]),
                GitStore(tmp_path / "cache"),
            )

            prepared = resolver.prepare("fixture")
            self.assertEqual(prepared.logical_name, "fixture")
            self.assertEqual(prepared.relative_path, "tf/1.0")
            self.assertTrue((prepared.path / "otype.tf").is_file())

    def test_collection_members_are_discovered_and_loaded_individually(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            upstream = make_git_repo(
                tmp_path,
                {
                    "Homer/Iliad/tf/1.0/otype.tf": "iliad\n",
                    "Plato/Phaedo/tf/1.0/otype.tf": "phaedo\n",
                    "Plato/Phaedo/notes.txt": "metadata\n",
                },
            )
            resource = ResourceSpec(
                id="greek",
                name="Greek fixture",
                plugin="context-fabric",
                provider="context-fabric",
                kind="collection",
                repository=str(upstream),
                languages=("greek",),
                disciplines=("classics",),
                member_index="unused-in-fixture",
            )
            resolver = ContextFabricResolver(
                Catalog([resource]),
                GitStore(tmp_path / "cache"),
            )

            members = resolver.list_members("greek")
            self.assertEqual(len(members), 2)
            iliad = next(member for member in members if "Homer/Iliad" in member.relative_path)
            phaedo = next(member for member in members if "Plato/Phaedo" in member.relative_path)
            self.assertNotEqual(iliad.id, phaedo.id)

            search = resolver.search_members("greek", "phaedo")
            self.assertEqual([member.id for member in search], [phaedo.id])

            prepared = resolver.prepare("greek", member_id=iliad.id)
            self.assertEqual(prepared.logical_name, f"greek:{iliad.id}")
            self.assertEqual(prepared.relative_path, "Homer/Iliad/tf/1.0")
            self.assertEqual((prepared.path / "otype.tf").read_text(encoding="utf-8"), "iliad\n")
            self.assertFalse((prepared.path.parents[3] / "Plato" / "Phaedo" / "otype.tf").exists())

    def test_collection_requires_member_id_for_prepare(self):
        resource = ResourceSpec(
            id="greek",
            name="Greek fixture",
            plugin="context-fabric",
            provider="context-fabric",
            kind="collection",
            repository="unused",
            languages=("greek",),
            disciplines=("classics",),
            member_index="unused",
        )
        with tempfile.TemporaryDirectory() as tmp:
            resolver = ContextFabricResolver(Catalog([resource]), GitStore(Path(tmp)))
            with self.assertRaisesRegex(ValueError, "member_id is required"):
                resolver.prepare("greek")


class FakeResolver:
    def __init__(self):
        self.prepare_calls: list[tuple[str, str | None]] = []
        self.members = [
            CollectionMember(
                id="homer-iliad-a1b2c3d4",
                resource_id="greek",
                relative_path="Homer/Iliad/tf/1.0",
                identity_path="Homer/Iliad",
                author="Homer",
                title="Iliad",
            ),
            CollectionMember(
                id="plato-phaedo-b1c2d3e4",
                resource_id="greek",
                relative_path="Plato/Phaedo/tf/1.0",
                identity_path="Plato/Phaedo",
                author="Plato",
                title="Phaedo",
            ),
            CollectionMember(
                id="plato-cratylus-c1d2e3f4",
                resource_id="greek",
                relative_path="Plato/Cratylus/tf/1.0",
                identity_path="Plato/Cratylus",
                author="Plato",
                title="Cratylus",
            ),
        ]

    def list_members(self, resource_id: str) -> list[CollectionMember]:
        if resource_id != "greek":
            raise AssertionError(resource_id)
        return list(self.members)

    def search_members(self, resource_id: str, query: str) -> list[CollectionMember]:
        if resource_id != "greek":
            raise AssertionError(resource_id)
        needle = query.casefold()
        return [member for member in self.members if needle in member.identity_path.casefold()]

    def prepare(self, resource_id: str, *, member_id: str | None = None) -> PreparedCorpus:
        self.prepare_calls.append((resource_id, member_id))
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
            {"bible", "patristics", "greek_literature"},
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
            repository="unused",
            languages=("greek",),
            disciplines=("classics",),
            member_index="unused",
        )
        service = ContextFabricService(Catalog([greek]), FakeResolver(), FakeLoader())

        page = service.list_members("greek", query="plato", offset=1, limit=1)
        self.assertEqual(page["total"], 2)
        self.assertEqual(page["offset"], 1)
        self.assertEqual(page["limit"], 1)
        self.assertFalse(page["has_more"])
        self.assertEqual([item["title"] for item in page["members"]], ["Cratylus"])

    def test_loading_prepares_then_delegates_to_corpus_manager(self):
        resource = ResourceSpec(
            id="fixture",
            name="Fixture",
            plugin="context-fabric",
            provider="context-fabric",
            kind="corpus",
            repository="unused",
            languages=("greek",),
            disciplines=("classics",),
            member_index=None,
        )
        resolver = FakeResolver()
        loader = FakeLoader()
        service = ContextFabricService(Catalog([resource]), resolver, loader)

        result = service.load("fixture", features=["otype", "word"])

        self.assertEqual(resolver.prepare_calls, [("fixture", None)])
        self.assertEqual(
            loader.calls,
            [("/tmp/agora-fixture/tf/1.0", "fixture", ["otype", "word"])],
        )
        self.assertEqual(result["resource_id"], "fixture")
        self.assertEqual(result["logical_name"], "fixture")
        self.assertEqual(result["corpus"]["name"], "fixture")

    def test_pagination_arguments_are_validated_before_resolution(self):
        greek = ResourceSpec(
            id="greek",
            name="Greek fixture",
            plugin="context-fabric",
            provider="context-fabric",
            kind="collection",
            repository="unused",
            languages=("greek",),
            disciplines=("classics",),
            member_index="unused",
        )
        service = ContextFabricService(Catalog([greek]), FakeResolver(), FakeLoader())

        with self.assertRaisesRegex(ValueError, "offset"):
            service.list_members("greek", offset=-1)
        with self.assertRaisesRegex(ValueError, "limit"):
            service.list_members("greek", limit=0)


if __name__ == "__main__":
    unittest.main()
