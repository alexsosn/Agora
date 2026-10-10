"""#219 RED3e: publish requested feature modules through the existing local-module store."""
from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CF_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(CF_SRC) not in sys.path:
    sys.path.insert(0, str(CF_SRC))

from agora_context_fabric.gitstore import GitStore
from scripts import agora_compose_feature_module as compose
from scripts import agora_materialize_registered as registered


REVISION = "0408967b1808c1f22c69e299d302b1e7b5e26354"


def fixture(root: Path):
    store = GitStore(root / "cache", min_free_bytes=0)
    manifest = root / "agora.materializer.json"
    spec = {
        "id": "burns-cuc-module",
        "description": "Synthetic feature module",
        "acquisition": [{"type": "user-local", "path_type": "directory",
                         "prompt": "Burns data"}],
        "input": {"type": "directory", "required_globs": ["*.csv"], "allow_symlinks": False},
        "parent_input": {"resource": "cuc", "parent_versions": ["0.2.8"],
                         "required_paths": ["otype.tf", "oslots.tf", "otext.tf"]},
        "execution": {"type": "python-module", "module": "fake.cli",
                      "args": ["{source}", "{parent}", "{output}"], "network": "deny"},
        "output": {"format": "text-fabric", "required_paths": ["burns_headword_1.tf"],
                   "composition": {"kind": "feature-module", "parent": "cuc",
                                   "compatibility": {"parent_versions": ["0.2.8"]}}},
    }
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "plugin": {"id": "fixture", "name": "Fixture", "version": "1.0.0"},
        "materializers": [spec],
    }))
    module = SimpleNamespace(
        id="cuc-burns", kind="feature-module", parent="cuc",
        acquisition_strategy="local-module", tf_path="tf/0.2.8",
        parent_versions=("0.2.8",),
        dependencies=({"role": "parent-base", "ref": REVISION},),
        materializer={"plugin": "fixture", "id": "burns-cuc-module"},
    )
    parent = SimpleNamespace(id="cuc", kind="corpus", ref=REVISION, tf_path="tf/0.2.8")
    catalog = mock.Mock()
    catalog.get.side_effect = {"cuc-burns": module, "cuc": parent}.__getitem__
    resolver = SimpleNamespace(catalog=catalog, store=store)
    target = store.local_feature_module_path("cuc-burns", "tf/0.2.8")
    return store, resolver, module, parent, manifest, target


class RegisteredLocalPublicationRed3e(unittest.TestCase):
    def publish(self, **kw):
        fn = getattr(compose, "materialize_requested_feature_module", None)
        self.assertTrue(callable(fn), "RED3e: explicit-by-id publication function missing")
        return fn(**kw)

    def invoke(self, root, *, mutate=None, producer=None):
        store, resolver, module, parent, manifest, target = fixture(root)
        if mutate:
            mutate(module, parent, store)
        with (
            mock.patch.object(compose, "_bundled_context_fabric_resolver", return_value=resolver),
            mock.patch.object(registered, "resolve_installed_manifest", return_value=manifest),
            mock.patch.object(compose, "materialize_managed_feature_module",
                              side_effect=producer) as materializer,
        ):
            try:
                result = self.publish(
                    module_id="cuc-burns", plugin_id="fixture",
                    materializer_id="burns-cuc-module", source=root / "input",
                    cache_dir=store.cache_dir,
                )
            except Exception as exc:
                return store, target, materializer, exc
        return store, target, materializer, result

    def test_explicit_id_publishes_directly_to_existing_local_module_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def produce(**kw):
                self.assertEqual(kw["output"], root / "cache/local-modules/cuc-burns/tf/0.2.8")
                self.assertEqual(kw["requested_version"], "0.2.8")
                self.assertEqual(kw["resolver"].store.cache_dir, root / "cache")
                kw["output"].mkdir(parents=True)
                (kw["output"] / "burns_headword_1.tf").write_text("@node\n@valueType=str\n\n1\tkt\n")
                return kw["output"]
            store, target, materializer, result = self.invoke(root, producer=produce)
            self.assertEqual(result, target)
            self.assertEqual(materializer.call_count, 1)
            snap, revision = store.local_feature_module("cuc-burns", "tf/0.2.8")
            self.assertTrue(revision.startswith("local-"))
            self.assertTrue((snap / "burns_headword_1.tf").is_file())
            self.assertFalse((snap / "otype.tf").exists())
            self.assertFalse((snap / "oslots.tf").exists())

    def test_bad_catalog_and_producer_mappings_fail_before_execution(self):
        cases = [
            ("kind", lambda m,p,s: setattr(m, "kind", "corpus")),
            ("local-module", lambda m,p,s: setattr(m, "acquisition_strategy", "repository")),
            ("parent-version", lambda m,p,s: setattr(m, "parent_versions", ("0.2.7",))),
            ("parent-ref", lambda m,p,s: setattr(p, "ref", "f"*40)),
            ("parent-kind", lambda m,p,s: setattr(p, "kind", "collection")),
            ("missing-tf-path", lambda m,p,s: setattr(m, "tf_path", None)),
            ("traversal-tf-path", lambda m,p,s: setattr(m, "tf_path", "../escape")),
        ]
        for label, mutate in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                store, target, materializer, result = self.invoke(Path(tmp), mutate=mutate)
                self.assertIsInstance(result, (ValueError, KeyError), result)
                materializer.assert_not_called()
                self.assertFalse(target.exists())

    def test_producer_mismatched_parent_or_output_kind_fails_before_execution(self):
        for field, replace in (
            ("parent resource", lambda x: x["parent_input"].update(resource="bhsa")),
            ("composition parent", lambda x: x["output"]["composition"].update(parent="bhsa")),
            ("composition kind", lambda x: x["output"]["composition"].update(kind="standalone")),
            ("producer versions", lambda x: x["parent_input"].update(parent_versions=["0.2.7"])),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                store, resolver, module, parent, manifest, target = fixture(root)
                data = json.loads(manifest.read_text())
                replace(data["materializers"][0])
                manifest.write_text(json.dumps(data))
                with (
                    mock.patch.object(compose, "_bundled_context_fabric_resolver", return_value=resolver),
                    mock.patch.object(registered, "resolve_installed_manifest", return_value=manifest),
                    mock.patch.object(compose, "materialize_managed_feature_module") as run,
                ):
                    with self.assertRaises((ValueError, KeyError)):
                        self.publish(module_id="cuc-burns", plugin_id="fixture",
                                     materializer_id="burns-cuc-module", source=root / "input",
                                     cache_dir=store.cache_dir)
                    run.assert_not_called()
                self.assertFalse(target.exists())

    def test_missing_or_mismatched_producer_binding_must_never_impersonate_module_id(self):
        for binding in (
            None,
            {},
            {"plugin": "unrelated", "id": "burns-cuc-module"},
            {"plugin": "fixture", "id": "unrelated-module"},
        ):
            with self.subTest(binding=binding), tempfile.TemporaryDirectory() as tmp:
                def mutate(module, parent, store):
                    module.materializer = binding
                store, target, run, result = self.invoke(Path(tmp), mutate=mutate)
                self.assertIsInstance(result, ValueError)
                run.assert_not_called()
                self.assertFalse(target.exists())

    def test_preexisting_even_empty_or_symlink_destination_never_overwritten(self):
        for mode in ("empty", "occupied", "symlink"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                store, resolver, module, parent, manifest, target = fixture(root)
                target.parent.mkdir(parents=True)
                if mode == "symlink":
                    outside = root / "outside"
                    outside.mkdir()
                    target.symlink_to(outside, target_is_directory=True)
                else:
                    target.mkdir()
                    if mode == "occupied":
                        (target / "burns.tf").write_text("original")
                with (
                    mock.patch.object(compose, "_bundled_context_fabric_resolver", return_value=resolver),
                    mock.patch.object(registered, "resolve_installed_manifest", return_value=manifest),
                    mock.patch.object(compose, "materialize_managed_feature_module") as run,
                ):
                    with self.assertRaises(ValueError):
                        self.publish(module_id="cuc-burns", plugin_id="fixture",
                                     materializer_id="burns-cuc-module", source=root / "input",
                                     cache_dir=store.cache_dir)
                    run.assert_not_called()
                self.assertTrue(target.exists())

    def test_symlinked_local_module_ancestor_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store, resolver, module, parent, manifest, target = fixture(root)
            outside = root / "outside"
            outside.mkdir()
            store.local_modules_dir.symlink_to(outside, target_is_directory=True)
            with (
                mock.patch.object(compose, "_bundled_context_fabric_resolver", return_value=resolver),
                mock.patch.object(registered, "resolve_installed_manifest", return_value=manifest),
                mock.patch.object(compose, "materialize_managed_feature_module") as run,
            ):
                with self.assertRaises(ValueError):
                    self.publish(module_id="cuc-burns", plugin_id="fixture",
                                 materializer_id="burns-cuc-module", source=root / "input",
                                 cache_dir=store.cache_dir)
                run.assert_not_called()

    def test_external_path_resolver_or_trust_bit_cannot_be_injected(self):
        fn = getattr(compose, "materialize_requested_feature_module", None)
        self.assertTrue(callable(fn), "RED3e: missing publication facade")
        sig = inspect.signature(fn)
        for param in ("resolver", "output", "parent_path", "trusted", "catalog"):
            self.assertNotIn(param, sig.parameters)
        self.assertNotIn(inspect.Parameter.VAR_KEYWORD, [p.kind for p in sig.parameters.values()])


if __name__ == "__main__":
    unittest.main()
