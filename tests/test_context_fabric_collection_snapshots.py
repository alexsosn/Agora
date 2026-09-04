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
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.resolver import ContextFabricResolver
from agora_context_fabric.service import ContextFabricService


class SnapshotLoader:
    def __init__(self):
        self.calls: list[tuple[str, str | None, object]] = []

    def load(self, path: str, name: str | None = None, features=None):
        self.calls.append((path, name, features))
        return {
            "name": name,
            "text": (Path(path) / "text.tf").read_text(encoding="utf-8"),
        }

    def unload(self, _name: str) -> None:
        return None


class CollectionSnapshotTests(unittest.TestCase):
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

    def _make_source(self, root: Path) -> Path:
        source = root / "collection-source"
        source.mkdir()
        self._git(source, "init", "-q", "-b", "main")
        self._git(source, "config", "user.email", "tests@example.invalid")
        self._git(source, "config", "user.name", "Agora Tests")
        for dataset in (
            "Homer/Iliad/tf/1.0",
            "Homer/Iliad/tf/2.0",
            "Homer/Odyssey/tf/1.0",
        ):
            tf = source / dataset
            tf.mkdir(parents=True)
            (tf / "otype.tf").write_text("@node\n", encoding="utf-8")
            (tf / "text.tf").write_text(f"A:{dataset}\n", encoding="utf-8")
        self._commit(source, "snapshot A")
        return source

    def _commit(self, source: Path, message: str) -> str:
        self._git(source, "add", "-A")
        self._git(source, "commit", "-qm", message)
        return self._git(source, "rev-parse", "HEAD")

    @staticmethod
    def _catalog(source: Path) -> Catalog:
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
                )
            ]
        )

    def test_discovery_token_pins_pagination_prepare_and_load_after_upstream_moves_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = self._make_source(tmp_path)
            revision_a = self._git(source, "rev-parse", "HEAD")
            loader = SnapshotLoader()
            resolver = ContextFabricResolver(self._catalog(source), GitStore(tmp_path / "cache"))
            service = ContextFabricService(self._catalog(source), resolver, loader)

            page_a = service.list_collection_members("greek", query="Iliad", limit=10)
            self.assertEqual(page_a["source_revision"], revision_a)
            self.assertEqual(len(page_a["items"]), 1)
            iliad_a = page_a["items"][0]
            self.assertEqual(iliad_a["source_revision"], revision_a)
            self.assertEqual(iliad_a["relative_path"], "Homer/Iliad/tf/2.0")

            shutil.move(str(source / "Homer" / "Iliad"), str(source / "Homer" / "Ilias"))
            for text_file in (source / "Homer" / "Ilias").glob("tf/*/text.tf"):
                text_file.write_text(
                    text_file.read_text(encoding="utf-8").replace("A:Homer/Iliad", "B:Homer/Ilias"),
                    encoding="utf-8",
                )
            revision_b = self._commit(source, "snapshot B moves Iliad")
            self.assertNotEqual(revision_b, revision_a)

            page_b = service.list_collection_members("greek", query="Ilias", limit=10)
            self.assertEqual(page_b["source_revision"], revision_b)
            self.assertEqual(page_b["items"][0]["relative_path"], "Homer/Ilias/tf/2.0")

            pinned_page = service.list_collection_members(
                "greek",
                query="Iliad",
                source_revision=revision_a,
                limit=10,
            )
            self.assertEqual(pinned_page["source_revision"], revision_a)
            self.assertEqual(pinned_page["items"][0]["id"], iliad_a["id"])
            self.assertEqual(pinned_page["items"][0]["relative_path"], "Homer/Iliad/tf/2.0")

            prepared = service.prepare(
                "greek",
                member_id=iliad_a["id"],
                source_revision=revision_a,
            )
            self.assertEqual(prepared["source_revision"], revision_a)
            self.assertEqual(prepared["relative_path"], "Homer/Iliad/tf/2.0")
            self.assertTrue(Path(prepared["path"], "text.tf").read_text(encoding="utf-8").startswith("A:"))

            loaded = service.load(
                "greek",
                member_id=iliad_a["id"],
                source_revision=revision_a,
            )
            self.assertEqual(loaded["source_revision"], revision_a)
            self.assertTrue(loaded["corpus"]["text"].startswith("A:Homer/Iliad"))

            with self.assertRaisesRegex(KeyError, "unknown member"):
                service.prepare("greek", member_id=iliad_a["id"])

    def test_supplied_revision_must_be_an_available_immutable_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = self._make_source(tmp_path)
            resolver = ContextFabricResolver(self._catalog(source), GitStore(tmp_path / "cache"))
            service = ContextFabricService(self._catalog(source), resolver, SnapshotLoader())
            page = service.list_collection_members("greek", query="Iliad")
            member_id = page["items"][0]["id"]

            with self.assertRaisesRegex(ValueError, "immutable commit"):
                service.prepare("greek", member_id=member_id, source_revision="main")
            with self.assertRaisesRegex(ValueError, "not available"):
                service.prepare("greek", member_id=member_id, source_revision="f" * 40)

    def test_pinned_empty_search_still_returns_snapshot_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = self._make_source(tmp_path)
            resolver = ContextFabricResolver(self._catalog(source), GitStore(tmp_path / "cache"))
            service = ContextFabricService(self._catalog(source), resolver, SnapshotLoader())
            first = service.list_collection_members("greek", limit=1)
            revision = first["source_revision"]

            empty = service.list_collection_members(
                "greek",
                query="does-not-exist",
                source_revision=revision,
            )
            self.assertEqual(empty["source_revision"], revision)
            self.assertEqual(empty["total"], 0)
            self.assertEqual(empty["items"], [])


if __name__ == "__main__":
    unittest.main()
