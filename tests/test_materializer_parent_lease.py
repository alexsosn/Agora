"""#135 RED3c: Context-Fabric lease across registered parent-bound execution.

The resolver and materializer are fakes. No source data, network or plugin Python
is acquired/executed by these unit contracts; the integration path is tested in
its own required-sandbox suite.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts import agora_compose_feature_module as compose
from scripts import agora_materialize as host
from scripts import agora_materialize_registered as registered


REV = "a" * 40


def _fixtures(root: Path, allowed_versions=("0.2.8",)):
    plugin = root / "plugin"
    plugin.mkdir()
    spec = {
        "id": "produce-burns-module",
        "description": "Synthetic module producer",
        "acquisition": [{"type": "user-local", "path_type": "directory",
                         "prompt": "Select Burns data"}],
        "input": {"type": "directory", "required_globs": ["*.xml"], "allow_symlinks": False},
        "parent_input": {"resource": "cuc", "parent_versions": list(allowed_versions),
                         "required_paths": ["otype.tf", "oslots.tf", "otext.tf"]},
        "execution": {"type": "python-module", "module": "burns.cli",
                      "args": ["{source}", "{parent}", "{parent_version}", "{parent_revision}", "{output}"],
                      "network": "deny"},
        "output": {"format": "text-fabric", "required_paths": ["burns.tf"],
                   "composition": {"kind": "feature-module", "parent": "cuc",
                                   "compatibility": {"parent_versions": list(allowed_versions)}}},
    }
    manifest = plugin / "agora.materializer.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "plugin": {"id": "fixture", "name": "Fixture", "version": "1.0.0"},
        "materializers": [spec],
    }))
    snapshots = root / "cache" / "snapshots"
    parent = snapshots / "cuc" / REV / "corpora" / "tf" / "0.2.8"
    parent.mkdir(parents=True)
    for name in ("otype.tf", "oslots.tf", "otext.tf"):
        (parent / name).write_text("fixed", encoding="utf-8")
    resolver = mock.Mock()
    resolver.catalog.get.return_value = SimpleNamespace(kind="corpus", id="cuc")
    resolver.prepare.return_value = SimpleNamespace(
        resource_id="cuc", member_id=None, version="0.2.8",
        source_revision=REV, relative_path="tf/0.2.8", path=parent,
    )
    resolver.store.snapshots_dir = snapshots
    resolver.store.safe_cache_key.side_effect = lambda item: item
    return manifest, parent, resolver


class ManagedParentLeasingRed3c(unittest.TestCase):
    def _run(self, **kwargs):
        fn = getattr(compose, "materialize_managed_feature_module", None)
        self.assertTrue(callable(fn), "RED3c: missing leased parent orchestration")
        return fn(**kwargs)

    @unittest.skipUnless(shutil.which("git"), "Git is needed for the real snapshot lease test")
    def test_real_gitstore_snapshot_lease_prevents_eviction_during_registered_run(self):
        """Use GitStore's actual cache, immutable commit and OS-backed lease."""
        plugin_src = Path(__file__).resolve().parents[1] / "plugins" / "context-fabric" / "src"
        if str(plugin_src) not in sys.path:
            sys.path.insert(0, str(plugin_src))
        from agora_context_fabric.gitstore import GitStore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_repo = root / "actual-upstream"
            source_repo.mkdir()
            for args in (
                ["git", "init", "-q", "-b", "main"],
                ["git", "config", "user.email", "agora-tests@example.invalid"],
                ["git", "config", "user.name", "Agora Tests"],
            ):
                subprocess.run(args, cwd=source_repo, check=True, capture_output=True)
            dataset = source_repo / "tf" / "0.2.8"
            dataset.mkdir(parents=True)
            for name in ("otype.tf", "oslots.tf", "otext.tf"):
                (dataset / name).write_text("real snapshot " + name, encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=source_repo, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=source_repo, check=True)

            store = GitStore(root / "real-cache", min_free_bytes=0)
            repo = store.ensure_metadata(str(source_repo), cache_key="cuc")
            snapshot = store.materialize(repo, "tf/0.2.8")
            revision = store.selected_revision(repo)

            fixture_root = root / "fixture"
            fixture_root.mkdir()
            manifest, _unused_parent, resolver = _fixtures(fixture_root)
            resolver.store = store
            resolver.prepare.return_value = SimpleNamespace(
                resource_id="cuc", member_id=None, version="0.2.8",
                source_revision=revision, relative_path="tf/0.2.8", path=snapshot,
            )
            publication = root / "published"
            def converter(**kwargs):
                self.assertEqual(kwargs["parent"].path, snapshot.resolve())
                self.assertEqual(kwargs["parent"].source_revision, revision)
                self.assertEqual(kwargs["sandbox"], "required")
                result = store.remove_cache_object(snapshot)
                self.assertEqual(result["removed_entries"], 0)
                self.assertEqual(result["skipped_in_use"], 1)
                self.assertTrue(snapshot.exists())
                return publication

            with (
                mock.patch.object(registered, "resolve_installed_manifest", return_value=manifest),
                mock.patch.object(registered, "materialize_registered", side_effect=converter),
            ):
                result = self._run(
                    resolver=resolver, plugin_id="fixture",
                    materializer_id="produce-burns-module",
                    source=root / "source", output=publication,
                )
            self.assertEqual(result, publication)
            removed = store.remove_cache_object(snapshot)
            self.assertEqual(removed["removed_entries"], 1)
            self.assertFalse(snapshot.exists())

    def test_acquires_lease_on_exact_prepared_snapshot_and_keeps_it_for_converter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, parent, resolver = _fixtures(root)
            state = {"leased": False, "closed": False}
            @contextmanager
            def lease(path):
                self.assertEqual(path, parent.resolve())
                self.assertFalse(state["leased"])
                state["leased"] = True
                try:
                    yield
                finally:
                    state["leased"] = False
                    state["closed"] = True

            resolver.store.acquire_cache_lease.side_effect = lease
            expected = root / "output"
            def run_converter(**kw):
                self.assertTrue(state["leased"], "cache lease lost during converter execution")
                self.assertEqual(kw["parent"].resource_id, "cuc")
                self.assertEqual(kw["parent"].version, "0.2.8")
                self.assertEqual(kw["parent"].source_revision, REV)
                self.assertEqual(kw["parent"].relative_path, "tf/0.2.8")
                self.assertEqual(kw["parent"].path, parent.resolve())
                self.assertEqual(kw["sandbox"], "required")
                return expected
            with (
                mock.patch.object(registered, "resolve_installed_manifest", return_value=manifest),
                mock.patch.object(registered, "materialize_registered", side_effect=run_converter) as actual,
            ):
                result = self._run(resolver=resolver, plugin_id="fixture",
                                   materializer_id="produce-burns-module",
                                   source=root / "source", output=expected)
            self.assertEqual(result, expected)
            self.assertEqual(actual.call_count, 1)
            self.assertTrue(state["closed"])
            self.assertFalse(state["leased"])
            resolver.store.acquire_cache_lease.assert_called_once_with(parent.resolve())

    def test_converter_failure_releases_lease_and_does_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _parent, resolver = _fixtures(root)
            state = {"active": False, "closed": False}
            @contextmanager
            def lease(path):
                state["active"] = True
                try:
                    yield
                finally:
                    state["active"] = False
                    state["closed"] = True
            resolver.store.acquire_cache_lease.side_effect = lease
            with (
                mock.patch.object(registered, "resolve_installed_manifest", return_value=manifest),
                mock.patch.object(registered, "materialize_registered", side_effect=RuntimeError("converter failed")),
            ):
                with self.assertRaisesRegex(RuntimeError, "converter failed"):
                    self._run(resolver=resolver, plugin_id="fixture",
                              materializer_id="produce-burns-module",
                              source=root / "source", output=root / "published")
            self.assertTrue(state["closed"])
            self.assertFalse(state["active"])
            self.assertFalse((root / "published").exists())

    def test_incompatible_parent_version_fails_before_acquisition_lease_or_converter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _parent, resolver = _fixtures(root)
            with (
                mock.patch.object(registered, "resolve_installed_manifest", return_value=manifest),
                mock.patch.object(registered, "materialize_registered") as materialize,
            ):
                with self.assertRaisesRegex(ValueError, "version|compatible"):
                    self._run(resolver=resolver, plugin_id="fixture",
                              materializer_id="produce-burns-module",
                              requested_version="1935", source=root / "source",
                              output=root / "published")
            resolver.prepare.assert_not_called()
            resolver.store.acquire_cache_lease.assert_not_called()
            materialize.assert_not_called()
            self.assertFalse((root / "published").exists())

    def test_missing_managed_installation_fails_before_parent_preparation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _manifest, _parent, resolver = _fixtures(root)
            with (
                mock.patch.object(registered, "resolve_installed_manifest",
                                  side_effect=RuntimeError("not installed")),
                mock.patch.object(registered, "materialize_registered") as materialize,
            ):
                with self.assertRaisesRegex(RuntimeError, "not installed"):
                    self._run(resolver=resolver, plugin_id="fixture",
                              materializer_id="produce-burns-module",
                              source=root / "source", output=root / "published")
            resolver.prepare.assert_not_called()
            resolver.store.acquire_cache_lease.assert_not_called()
            materialize.assert_not_called()

    def test_corrupt_parent_after_resolution_is_refused_by_real_lease_before_converter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, parent, resolver = _fixtures(root)
            def fail_lease(path):
                self.assertEqual(path, parent.resolve())
                raise FileNotFoundError("snapshot evicted or corrupt")
            resolver.store.acquire_cache_lease.side_effect = fail_lease
            with (
                mock.patch.object(registered, "resolve_installed_manifest", return_value=manifest),
                mock.patch.object(registered, "materialize_registered") as materialize,
            ):
                with self.assertRaisesRegex(FileNotFoundError, "snapshot evicted"):
                    self._run(resolver=resolver, plugin_id="fixture",
                              materializer_id="produce-burns-module",
                              source=root / "source", output=root / "published")
            materialize.assert_not_called()
            self.assertFalse((root / "published").exists())

    def test_parentless_materializer_is_not_silently_promoted_to_managed_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _parent, resolver = _fixtures(root)
            doc = json.loads(manifest.read_text())
            del doc["materializers"][0]["parent_input"]
            doc["materializers"][0]["execution"]["args"] = ["{source}", "{output}"]
            del doc["materializers"][0]["output"]["composition"]
            manifest.write_text(json.dumps(doc))
            with (
                mock.patch.object(registered, "resolve_installed_manifest", return_value=manifest),
                mock.patch.object(registered, "materialize_registered") as materialize,
            ):
                with self.assertRaisesRegex(ValueError, "parent_input|feature.module"):
                    self._run(resolver=resolver, plugin_id="fixture",
                              materializer_id="produce-burns-module",
                              source=root / "source", output=root / "published")
            resolver.prepare.assert_not_called()
            materialize.assert_not_called()


if __name__ == "__main__":
    unittest.main()
