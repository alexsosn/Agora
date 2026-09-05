from __future__ import annotations

import shutil
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
from agora_context_fabric.collection_index import (
    build_collection_index,
    dump_collection_index,
)
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.resolver import ContextFabricResolver
from agora_context_fabric.service import ContextFabricService


class CountingGitStore(GitStore):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dataset_root_calls = 0

    def dataset_roots(self, repo: Path, revision: str | None = None) -> list[str]:
        self.dataset_root_calls += 1
        return super().dataset_roots(repo, revision)


class CollectionIndexRuntimeTests(unittest.TestCase):
    @staticmethod
    def git(source: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=source,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.stdout.strip()

    def commit(self, source: Path, message: str) -> str:
        self.git(source, "add", "-A")
        self.git(source, "commit", "-qm", message)
        return self.git(source, "rev-parse", "HEAD")

    def make_source(self, root: Path, *, include_neutral: bool = False) -> tuple[Path, str]:
        source = root / "source"
        source.mkdir()
        self.git(source, "init", "-q", "-b", "main")
        self.git(source, "config", "user.email", "tests@example.invalid")
        self.git(source, "config", "user.name", "Agora Tests")
        for name, title in (("Iliad", "Iliad"), ("Odyssey", "Odyssey")):
            tf = source / "Homer" / name / "tf" / "1.0"
            tf.mkdir(parents=True)
            (tf / "otype.tf").write_text("@node\n\n1\tword\n", encoding="utf-8")
            (tf / "_book.tf").write_text(
                "@node\n"
                "@author=Homer\n"
                f"@_book={title}\n"
                f"@urn=urn:cts:greekLit:fixture.{name.casefold()}\n"
                f"@edition=Fixture {title} edition\n"
                "\n1\t" + title + "\n",
                encoding="utf-8",
            )
        if include_neutral:
            tf = source / "Archive" / "Volume" / "tf" / "1.0"
            tf.mkdir(parents=True)
            (tf / "otype.tf").write_text("@node\n\n1\tword\n", encoding="utf-8")
        return source, self.commit(source, "snapshot A")

    @staticmethod
    def catalog(source: Path, *, member_index: str | None = None) -> Catalog:
        return Catalog(
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
                    member_index=member_index,
                    collection_discovery="indexed",
                )
            ]
        )

    def test_generated_index_scans_once_then_list_search_and_prepare_reuse_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, revision = self.make_source(root)
            store = CountingGitStore(root / "cache")
            resolver = ContextFabricResolver(self.catalog(source), store)

            first = resolver.resolve_members("greek")
            self.assertEqual(first.source_revision, revision)
            self.assertEqual(store.dataset_root_calls, 1)
            self.assertEqual(first.members[0].author, "Homer")

            second = resolver.resolve_members("greek", query="Iliad")
            self.assertEqual(len(second.members), 1)
            self.assertEqual(store.dataset_root_calls, 1)

            resolver.prepare(
                "greek",
                member_id=second.members[0].id,
                source_revision=revision,
            )
            self.assertEqual(store.dataset_root_calls, 1)

    def test_collection_search_exposes_semantic_canonical_edition_and_neutral_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, revision = self.make_source(root, include_neutral=True)
            store = CountingGitStore(root / "cache")
            catalog = self.catalog(source)
            resolver = ContextFabricResolver(catalog, store)
            service = ContextFabricService(catalog, resolver, object())

            for query in (
                "Homer",
                "Iliad",
                "urn:cts:greekLit:fixture.iliad",
                "Homer/Iliad",
                "Fixture Iliad edition",
            ):
                result = service.list_members("greek", query=query)
                self.assertEqual(result["source_revision"], revision)
                self.assertTrue(
                    any(member["title"] == "Iliad" for member in result["members"]),
                    (query, result),
                )

            iliad_page = service.list_members("greek", query="Iliad", limit=1)
            iliad = iliad_page["members"][0]
            self.assertEqual(iliad["author"], "Homer")
            self.assertEqual(iliad["title"], "Iliad")
            self.assertEqual(iliad["canonical_id"], "urn:cts:greekLit:fixture.iliad")
            self.assertEqual(iliad["edition"], "Fixture Iliad edition")
            self.assertEqual(
                iliad["verification"],
                {"status": "community", "evidence": [], "notes": []},
            )
            self.assertEqual(iliad["identity_path"], "Homer/Iliad")
            self.assertEqual(iliad["relative_path"], "Homer/Iliad/tf/1.0")
            self.assertEqual(iliad["source_revision"], revision)

            neutral_page = service.list_members("greek", query="Archive/Volume")
            self.assertEqual(neutral_page["total"], 1)
            neutral = neutral_page["members"][0]
            self.assertEqual(neutral["identity_path"], "Archive/Volume")
            self.assertIsNone(neutral["author"])
            self.assertIsNone(neutral["title"])
            self.assertIsNone(neutral["canonical_id"])
            self.assertIsNone(neutral["edition"])

            first_page = service.list_members("greek", query="Homer", limit=1)
            second_page = service.list_members(
                "greek",
                query="Homer",
                source_revision=first_page["source_revision"],
                offset=1,
                limit=1,
            )
            self.assertEqual(first_page["source_revision"], revision)
            self.assertEqual(second_page["source_revision"], revision)
            self.assertEqual(first_page["total"], 2)
            self.assertEqual(second_page["total"], 2)

    def test_generated_index_persists_across_resolver_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, revision = self.make_source(root)
            cache = root / "cache"

            first_store = CountingGitStore(cache)
            first = ContextFabricResolver(self.catalog(source), first_store)
            first_result = first.resolve_members("greek")
            self.assertEqual(first_result.source_revision, revision)
            self.assertEqual(first_store.dataset_root_calls, 1)

            second_store = CountingGitStore(cache)
            second = ContextFabricResolver(self.catalog(source), second_store)
            result = second.resolve_members("greek", source_revision=revision)
            self.assertEqual(result.source_revision, revision)
            self.assertEqual(second_store.dataset_root_calls, 0)
            self.assertTrue((cache / "collection-indexes" / "greek" / f"{revision}.yaml").is_file())

    def test_new_upstream_revision_gets_new_index_while_pinned_old_revision_reuses_old_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, revision_a = self.make_source(root)
            store = CountingGitStore(root / "cache")
            resolver = ContextFabricResolver(self.catalog(source), store)

            page_a = resolver.resolve_members("greek", query="Iliad")
            member_a = page_a.members[0]
            self.assertEqual(store.dataset_root_calls, 1)

            shutil.move(source / "Homer" / "Iliad", source / "Homer" / "Ilias")
            header = source / "Homer" / "Ilias" / "tf" / "1.0" / "_book.tf"
            header.write_text(
                header.read_text(encoding="utf-8")
                .replace("@_book=Iliad", "@_book=Ilias")
                .replace("fixture.iliad", "fixture.ilias"),
                encoding="utf-8",
            )
            revision_b = self.commit(source, "snapshot B")

            page_b = resolver.resolve_members("greek", query="Ilias")
            self.assertEqual(page_b.source_revision, revision_b)
            self.assertEqual(len(page_b.members), 1)
            self.assertEqual(store.dataset_root_calls, 2)

            pinned_a = resolver.resolve_members(
                "greek",
                query="Iliad",
                source_revision=revision_a,
            )
            self.assertEqual(pinned_a.source_revision, revision_a)
            self.assertEqual(pinned_a.members[0].id, member_a.id)
            self.assertEqual(store.dataset_root_calls, 2)

    def test_matching_installed_index_is_fast_path_and_wrong_revision_is_not_substituted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, revision_a = self.make_source(root)
            installed = root / "installed-index.yaml"
            installed_index = build_collection_index(
                collection_id="greek",
                source_revision=revision_a,
                roots=["Homer/Iliad/tf/1.0", "Homer/Odyssey/tf/1.0"],
                languages=("greek",),
                metadata_reader=lambda path: {
                    "author": "Homer",
                    "_book": "Iliad" if "Iliad" in path else "Odyssey",
                },
            )
            installed.write_text(dump_collection_index(installed_index), encoding="utf-8")

            store = CountingGitStore(root / "cache")
            resolver = ContextFabricResolver(
                self.catalog(source, member_index=str(installed)),
                store,
            )
            result_a = resolver.resolve_members("greek")
            self.assertEqual(result_a.source_revision, revision_a)
            self.assertEqual(store.dataset_root_calls, 0)

            pinned_a = resolver.resolve_members("greek", source_revision=revision_a)
            self.assertEqual(pinned_a.source_revision, revision_a)
            self.assertEqual(store.dataset_root_calls, 0)

            shutil.move(source / "Homer" / "Iliad", source / "Homer" / "Ilias")
            revision_b = self.commit(source, "snapshot B")
            result_b = resolver.resolve_members("greek", source_revision=None)
            self.assertEqual(result_b.source_revision, revision_b)
            self.assertTrue(any("Ilias" in member.relative_path for member in result_b.members))
            self.assertEqual(store.dataset_root_calls, 1)


if __name__ == "__main__":
    unittest.main()
