"""RED-first contracts for Agora #205: opt-in sparse, pinned Git TT acquisition."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.agora_materialize import (
    AcquisitionError,
    ManifestError,
    acquire_git_source,
    acquire_source,
    load_manifest,
)

GIT = shutil.which("git")
SPARSE = ["/*/*_TT/**", "/*/*_TT.zip"]


def _manifest(ref: str, *, sparse: list[str] | None) -> dict:
    strategy = {
        "type": "git",
        "url": "https://github.com/CopticScriptorium/corpora.git",
        "ref": ref,
        "subpath": ".",
    }
    if sparse is not None:
        strategy["sparse_patterns"] = sparse
    return {
        "schema_version": 1,
        "plugin": {"id": "copticscriptorium-tf", "name": "Coptic", "version": "0.1"},
        "materializers": [{
            "id": "tt-to-tf", "description": "TT only",
            "acquisition": [strategy, {
                "type": "user-local", "path_type": "directory",
                "prompt": "Select a local TT corpus tree",
            }],
            "input": {
                "type": "directory", "required_globs": ["*/*_TT*"],
                "allow_symlinks": False,
            },
            "execution": {
                "type": "python-module", "module": "tt.cli",
                "args": ["{source}", "{output}"], "network": "deny",
            },
            "output": {
                "format": "text-fabric", "required_paths": ["tf/otype.tf"],
            },
        }],
    }


class SparseManifestContracts(unittest.TestCase):
    def check(self, doc: dict) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agora.materializer.json"
            path.write_text(json.dumps(doc), encoding="utf-8")
            return load_manifest(path)

    def test_valid_pinned_tt_sparse_contract(self):
        doc = _manifest("3ac067f1709a0012daf39ea8da2fac79980176a5", sparse=SPARSE)
        loaded = self.check(doc)
        self.assertEqual(loaded["materializers"][0]["acquisition"][0]["sparse_patterns"], SPARSE)

    def test_sparse_disallows_mutable_or_abbreviated_refs(self):
        for ref in ("main", "3ac067f", "A" * 40, "3ac067f1709a0012daf39ea8da2fac79980176a5~1"):
            with self.subTest(ref=ref):
                with self.assertRaises(ManifestError):
                    self.check(_manifest(ref, sparse=SPARSE))

    def test_sparse_rejects_unsafe_patterns(self):
        for patterns in ([], ["!/*/*_TT/**"], ["/../*"], ["/*/../x"],
                         ["/*/.git/**"], ["/*/x[abc]/**"], ["/*/x\\n/**"],
                         ["../../foo"], ["-x"], ["/*/*_TT/**", ""]):
            with self.subTest(patterns=patterns):
                with self.assertRaises(ManifestError):
                    self.check(_manifest("a" * 40, sparse=patterns))

    def test_legacy_full_git_contract_retained(self):
        loaded = self.check(_manifest("main", sparse=None))
        self.assertNotIn("sparse_patterns", loaded["materializers"][0]["acquisition"][0])


@unittest.skipUnless(GIT, "Git is required for acquisition tests")
class SparseGitAcquisitionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.remote = self.work / "upstream"
        self.remote.mkdir()
        self.git("-C", str(self.remote), "init", "-q")
        self._file("AP/story_TT/part1.tt", "TT doc 1")
        self._file("AP/story_TT/sub/chapter.tt", "TT doc 2")
        self._file("sahidica.nt/NT_TT.zip", "TT archive")
        self._file("AP/story_ANNIS/part1.annis", "not TT")
        self._file("AP/story_CONLLU/part1.conllu", "not TT")
        self._file("sahidica.nt/NT_PAULA/doc.xml", "not TT")
        self.git("-C", str(self.remote), "add", ".")
        self.git("-C", str(self.remote), "-c", "user.email=test@invalid",
                 "-c", "user.name=test", "commit", "-qm", "test")
        self.commit = self.git("-C", str(self.remote), "rev-parse", "HEAD").strip()
        self.strategy = {
            "type": "git", "url": str(self.remote), "ref": self.commit,
            "subpath": ".", "sparse_patterns": SPARSE,
        }
        self.spec = _manifest(self.commit, sparse=SPARSE)["materializers"][0]

    def git(self, *args):
        return subprocess.check_output([GIT, *args], text=True)

    def _file(self, relative, contents):
        target = self.remote / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8")

    def test_real_git_selects_tt_files_and_zip_but_no_other_source_formats(self):
        from scripts import agora_materialize as module
        seen: list[list[str]] = []
        original = module._run_git

        def record(command, **kwargs):
            seen.append(command)
            return original(command, **kwargs)

        with mock.patch.object(module, "_run_git", side_effect=record):
            prepared = acquire_git_source(self.strategy, self.spec)
        try:
            self.assertEqual(
                sorted(p.relative_to(prepared.path).as_posix()
                       for p in prepared.path.rglob("*") if p.is_file()
                       and ".git" not in p.relative_to(prepared.path).parts),
                ["AP/story_TT/part1.tt", "AP/story_TT/sub/chapter.tt",
                 "sahidica.nt/NT_TT.zip"],
            )
            self.assertEqual(prepared.provenance["requested_ref"], self.commit)
            self.assertEqual(prepared.provenance["resolved_commit"], self.commit)
            self.assertEqual(prepared.provenance["sparse_patterns"], SPARSE)
            fetch_index = next(i for i, c in enumerate(seen) if "fetch" in c)
            sparse_index = next(i for i, c in enumerate(seen) if "sparse-checkout" in c)
            checkout_index = next(i for i, c in enumerate(seen) if "checkout" in c)
            self.assertIn("--filter=blob:none", seen[fetch_index])
            self.assertLess(fetch_index, sparse_index)
            self.assertLess(sparse_index, checkout_index)
        finally:
            prepared.cleanup()
        self.assertFalse(prepared.cleanup_root.exists())

    def test_sparse_requires_exact_commit_after_checkout_and_cleans_up(self):
        from scripts import agora_materialize as module
        original = module._run_git
        original_make = module.tempfile.mkdtemp
        acquired_roots = []

        def record_dir(*args, **kwargs):
            path = Path(original_make(*args, **kwargs))
            acquired_roots.append(path)
            return str(path)

        def wrong_revision(command, **kwargs):
            if "rev-parse" in command and "HEAD" in command:
                return "0" * 40
            return original(command, **kwargs)

        with (mock.patch.object(module._run_git.__module__ and module,
                                "_run_git", side_effect=wrong_revision),
              mock.patch.object(module.tempfile, "mkdtemp", side_effect=record_dir)):
            with self.assertRaises(AcquisitionError) as raised:
                acquire_git_source(self.strategy, self.spec)
        self.assertIn("commit", str(raised.exception).lower())
        self.assertTrue(acquired_roots)
        self.assertTrue(all(not path.exists() for path in acquired_roots))

    def test_legacy_fetch_remains_complete(self):
        traditional = {k: v for k, v in self.strategy.items() if k != "sparse_patterns"}
        prepared = acquire_git_source(traditional, self.spec)
        try:
            self.assertTrue((prepared.path / "AP/story_ANNIS/part1.annis").is_file())
            self.assertTrue((prepared.path / "AP/story_TT/part1.tt").is_file())
            self.assertNotIn("sparse_patterns", prepared.provenance)
        finally:
            prepared.cleanup()

    def test_explicit_user_source_still_bypasses_auto_git(self):
        self.spec["acquisition"][0]["url"] = "https://unreachable.invalid/corpus.git"
        with mock.patch("scripts.agora_materialize.acquire_git_source") as git_fetch:
            prepared = acquire_source(self.spec, source_override=self.remote)
        try:
            self.assertEqual(prepared.provenance["type"], "user-local")
            git_fetch.assert_not_called()
        finally:
            prepared.cleanup()


if __name__ == "__main__":
    unittest.main()
