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

from agora_context_fabric.collection_index import CollectionIndexManager
from agora_context_fabric.gitstore import GitStore


REVISION = "a" * 40


class HeaderOnlyMetadataTests(unittest.TestCase):
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

    def test_collection_manager_uses_header_only_git_reader_for_identity_and_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls: list[str] = []

            class HeaderOnlyStore:
                cache_dir = Path(tmp)

                @staticmethod
                def tf_header_metadata(_repo, relative_path, revision):
                    calls.append(relative_path)
                    self.assertEqual(revision, REVISION)
                    if relative_path == "tf/1.0/_book.tf":
                        return {"author": "Homer", "title": "Iliad"}
                    if relative_path == "tf/1.0/otext.tf":
                        return {
                            "structureTypes": "_book,book,card,card,_sentence,_phrase",
                            "structureFeatures": "_book,book,card,card,_sentence,_phrase",
                        }
                    raise AssertionError(f"unexpected metadata path: {relative_path}")

                @staticmethod
                def tf_feature_summary(*_args, **_kwargs):
                    raise AssertionError("collection metadata must not scan the feature body")

            manager = CollectionIndexManager(HeaderOnlyStore())
            self.assertEqual(
                manager._metadata_for(Path("unused"), "tf/1.0", REVISION),
                {
                    "author": "Homer",
                    "title": "Iliad",
                    "structureTypes": "_book,book,card,card,_sentence,_phrase",
                    "structureFeatures": "_book,book,card,card,_sentence,_phrase",
                },
            )
            self.assertEqual(calls, ["tf/1.0/_book.tf", "tf/1.0/otext.tf"])

    def test_git_header_reader_stops_before_invalid_feature_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            self.git(source, "init", "-q", "-b", "main")
            self.git(source, "config", "user.email", "tests@example.invalid")
            self.git(source, "config", "user.name", "Agora Tests")
            tf = source / "tf" / "1.0"
            tf.mkdir(parents=True)
            (tf / "_book.tf").write_text(
                "@edge\n"
                "@author=Homer\n"
                "@title=Iliad\n"
                "@urn=urn:cts:greekLit:fixture.iliad\n"
                "\n"
                "1\tnot-a-node-spec\n",
                encoding="utf-8",
            )
            self.git(source, "add", ".")
            self.git(source, "commit", "-qm", "fixture")

            store = GitStore(root / "cache")
            repo = store.ensure_metadata(str(source), cache_key="fixture")
            revision = store.selected_revision(repo)

            with self.assertRaises(ValueError):
                store.tf_feature_summary(repo, "tf/1.0/_book.tf", revision)

            self.assertEqual(
                store.tf_header_metadata(repo, "tf/1.0/_book.tf", revision),
                {
                    "author": "Homer",
                    "title": "Iliad",
                    "urn": "urn:cts:greekLit:fixture.iliad",
                },
            )


class CollectionIndexWorkflowTests(unittest.TestCase):
    def test_generation_workflow_checks_canonical_freshness_for_resource_changes(self):
        workflow = (
            ROOT / ".github" / "workflows" / "context-fabric-collection-index-generation.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('"registry/resources.yaml"', workflow)
        self.assertIn("--check", workflow)

    def test_generation_workflow_uploads_evidence_before_freshness_check(self):
        workflow = (
            ROOT / ".github" / "workflows" / "context-fabric-collection-index-generation.yml"
        ).read_text(encoding="utf-8")
        upload_position = workflow.index("- name: Upload generated index")
        check_position = workflow.index("- name: Verify canonical collection index is fresh")
        self.assertLess(upload_position, check_position)


if __name__ == "__main__":
    unittest.main()
