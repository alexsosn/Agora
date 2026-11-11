"""#294: collection-index matrix must remain complete except proven corpus-only edits."""
from __future__ import annotations

import copy
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.ci_collection_index_scope import classify_resource_diff, classify_pr_checkout

ROOT = Path(__file__).resolve().parents[1]
S1, S2 = b"a" * 40, b"b" * 40


def raw(status: bytes = b"M", path: bytes = b"registry/resources.yaml",
        old: bytes = b"100644", new: bytes = b"100644") -> bytes:
    return (b":" + old + b" " + new + b" " + S1 + b" " + S2
            + b" " + status + b"\0" + path + b"\0")


def registry() -> str:
    return (ROOT / "registry/resources.yaml").read_text(encoding="utf-8")


def edited(change) -> str:
    doc = yaml.safe_load(registry())
    change(doc["resources"])
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def corpus_edit(rows) -> None:
    next(row for row in rows if row["id"] == "aleppo")["description"] += " 2026"


class CollectionIndexCiScope294(unittest.TestCase):
    def test_actual_corpus_only_registry_edit_skips_expensive_matrix(self):
        before = registry()
        after = edited(corpus_edit)
        self.assertEqual("skip", classify_resource_diff(raw(), before, after))
        self.assertEqual("skip", classify_resource_diff(
            raw() + raw(b"M", b"wiki/guides/installation.md"), before, after
        ))
        self.assertEqual("skip", classify_resource_diff(
            raw() + raw(b"A", b"research/issue-294/RESEARCH_PLAN.md",
                        b"000000", b"100644"), before, after
        ))

    def test_every_collection_change_requires_full_regeneration(self):
        changes = {
            "member index": lambda rows: next(r for r in rows if r["id"] == "bible")["collection"].update(member_index="registry/collections/changed.yaml"),
            "rename": lambda rows: next(r for r in rows if r["id"] == "bible").update(id="bible-renamed"),
            "remove": lambda rows: rows.__delitem__(next(i for i, r in enumerate(rows) if r["id"] == "patristics")),
            "reorder": lambda rows: rows.reverse(),
            "convert corpus to collection": lambda rows: next(r for r in rows if r["id"] == "aleppo").update(kind="collection"),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                self.assertEqual("full", classify_resource_diff(raw(), registry(), edited(change)))

    def test_unrelated_change_without_resource_diff_cannot_skip(self):
        self.assertEqual("full", classify_resource_diff(raw(path=b"registry/collections/bible.yaml"), registry(), registry()))
        self.assertEqual("full", classify_resource_diff(raw(), registry(), registry()))

    def test_unreviewed_or_executable_mixed_change_fails_closed(self):
        after = edited(corpus_edit)
        for path in (
            b"registry/collections/bible.yaml", b"registry/plugins.yaml",
            b"plugins/context-fabric/src/agora_context_fabric/gitstore.py",
            b"plugins/context-fabric/src/agora_context_fabric/catalog.py",
            b"scripts/generate_context_fabric_collection_indexes.py",
            b"scripts/ci_collection_index_scope.py",
            b"tests/test_ci_collection_index_scope_294.py",
            b".github/workflows/context-fabric-collection-index-generation.yml",
            b"unknown/README.md", b"README.md\nregistry/collections/bible.yaml",
            b"wiki/guides/../guides/installation.md", b"/tmp/wiki/guides/README.md",
        ):
            with self.subTest(path=path):
                self.assertEqual("full", classify_resource_diff(raw() + raw(path=path), registry(), after))

    def test_nonregular_files_renames_invalid_status_and_corrupt_raw_fail_closed(self):
        after = edited(corpus_edit)
        for delta in (
            raw(old=b"100644", new=b"100755"),
            raw(b"A", old=b"000000", new=b"120000"),
            raw(b"D", old=b"120000", new=b"000000"),
            raw(b"R100"),
            raw()[:-1],
            b"bad\0registry/resources.yaml\0",
            b"",
        ):
            with self.subTest(delta=delta):
                self.assertEqual("full", classify_resource_diff(delta, registry(), after))

    def test_malformed_duplicate_unknown_resource_documents_fail_closed(self):
        before = registry()
        malformed = (
            "schema_version: 1\nresources: [",
            "schema_version: 1\nresources: {}\n",
            "schema_version: 2\nresources: []\n",
            "schema_version: 1\nresources:\n- id: x\n  kind: corpus\n  kind: collection\n",
            "schema_version: 1\nresources:\n- id: x\n  kind: unknown\n",
            "schema_version: 1\nresources:\n- &x {id: x, kind: corpus}\n- *x\n",
            "schema_version: 1\nresources:\n- {id: 7, kind: corpus}\n",
        )
        for doc in malformed:
            with self.subTest(doc=doc):
                self.assertEqual("full", classify_resource_diff(raw(), before, doc))
                self.assertEqual("full", classify_resource_diff(raw(), doc, before))
        self.assertEqual("full", classify_resource_diff(raw(), before, edited(
            lambda rows: rows.append(copy.deepcopy(rows[0]))
        )))

    def test_matrix_status_names_preserved_and_manual_full(self):
        workflow = (ROOT / ".github/workflows/context-fabric-collection-index-generation.yml").read_text()
        for resource in ("bible", "patristics", "greek_literature", "translatin-manif"):
            self.assertIn(f"- {resource}", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("timeout-minutes:", workflow)
        self.assertIn("continue-on-error: true", workflow)
        self.assertIn("if: github.event_name == 'pull_request'", workflow)
        self.assertRegex(workflow, r"(?m)^  generate:\n")
        self.assertRegex(workflow, r"(?m)^    needs: scope\n")
        self.assertNotRegex(workflow, r"(?m)^  generate:.*\n(?:.*\n)*?    if:")
        self.assertIn("git show HEAD^1:scripts/ci_collection_index_scope.py", workflow)
        self.assertIn("if: needs.scope.outputs.regenerate == 'true'", workflow)
        self.assertIn("if: needs.scope.outputs.regenerate == 'false'", workflow)
        self.assertIn('GITHUB_EVENT_NAME: ${{ github.event_name }}', workflow)

    @unittest.skipUnless(shutil.which("git"), "requires local Git CLI")
    def test_real_synthetic_merge_checkout_compares_trusted_first_parent(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)
            def git(*args):
                return subprocess.run(["git", *args], cwd=repo, check=True,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            git("init", "-q", "-b", "main")
            git("config", "user.name", "CI Fixture")
            git("config", "user.email", "ci@example.invalid")
            (repo / "registry").mkdir()
            (repo / "registry/resources.yaml").write_text(registry())
            git("add", ".")
            git("commit", "-qm", "base")
            git("checkout", "-qb", "feature")
            (repo / "registry/resources.yaml").write_text(edited(corpus_edit))
            git("add", ".")
            git("commit", "-qm", "corpus edit")
            git("checkout", "main")
            git("merge", "--no-ff", "-qm", "PR merge", "feature")
            def runner(args, **kwargs):
                return subprocess.run(args, cwd=repo, **kwargs)
            self.assertEqual("skip", classify_pr_checkout(git_runner=runner))
            git("checkout", "feature")
            self.assertEqual("full", classify_pr_checkout(git_runner=runner),
                             "Nonmerge HEAD must not claim a safe PR scope")


if __name__ == "__main__":
    unittest.main()
