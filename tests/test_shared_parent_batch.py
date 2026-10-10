"""#228 RED4a: identical corpus parent is prepared and leased exactly once."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts import agora_compose_feature_module as compose
from scripts import agora_materialize_registered as registered


REVISION = "a" * 40


class SharedParentBatchRed4a(unittest.TestCase):
    def setUp(self):
        self.fn = getattr(compose, "materialize_requested_feature_modules", None)
        self.assertTrue(callable(self.fn), "RED4a: batch publisher is missing")

    def requests(self):
        return [
            {"module_id": "module-a", "plugin_id": "plugin-a",
             "materializer_id": "producer-a", "source": Path("source-a")},
            {"module_id": "module-b", "plugin_id": "plugin-b",
             "materializer_id": "producer-b", "source": Path("source-b")},
        ]

    def fixture(self, root: Path):
        state = {"prepare": 0, "lease": 0, "leased": False, "execution": []}
        store = SimpleNamespace()
        store.cache_dir = root
        store.locks_dir = root / "locks"
        store.locks_dir.mkdir(parents=True)
        store.safe_cache_key = lambda x: x
        @contextmanager
        def lease(path):
            state["lease"] += 1
            self.assertEqual(path, root / "snapshots" / "parent")
            self.assertFalse(state["leased"])
            state["leased"] = True
            try:
                yield
            finally:
                state["leased"] = False
        store.acquire_cache_lease = lease
        parent = SimpleNamespace(id="cuc", kind="corpus", ref=REVISION, tf_path="tf/0.2.8")
        catalog = mock.Mock()
        catalog.get.return_value = parent
        resolver = SimpleNamespace(store=store, catalog=catalog)
        bind = SimpleNamespace(
            path=root / "snapshots" / "parent",
            resource_id="cuc", version="0.2.8", source_revision=REVISION,
            relative_path="tf/0.2.8", trusted=True,
        )
        plans = {}
        for mod in ("a", "b"):
            name = "module-" + mod
            plans[name] = SimpleNamespace(
                module_id=name, plugin_id="plugin-" + mod,
                materializer_id="producer-" + mod,
                source=Path("source-" + mod),
                parent_id="cuc", parent_revision=REVISION,
                version="0.2.8", output=root / "published" / name,
                lock_path=store.locks_dir / (name + ".lock"),
                spec={"parent_input": {"resource": "cuc", "parent_versions": ["0.2.8"]},
                      "output": {"composition": {"kind": "feature-module", "parent": "cuc",
                                                "compatibility": {"parent_versions": ["0.2.8"]}}}},
            )
        def resolve(spec, fake, requested_version):
            self.assertIs(fake, resolver)
            self.assertEqual(requested_version, "0.2.8")
            state["prepare"] += 1
            return bind
        def execute(**kwargs):
            self.assertTrue(state["leased"])
            self.assertIs(kwargs["parent"], bind)
            self.assertEqual(kwargs["sandbox"], "required")
            state["execution"].append(kwargs["materializer_id"])
            return kwargs["output"]
        return state, resolver, plans, resolve, execute

    def test_two_producers_one_prepared_parent_one_lease(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, resolver, plans, resolve, execute = self.fixture(root)
            with (
                mock.patch.object(compose, "_bundled_context_fabric_resolver", return_value=resolver),
                mock.patch.object(compose, "_candidate_versions_for_request",
                                  return_value=("cuc", {"0.2.8"})),
                mock.patch.object(compose, "_plan_requested_feature_module",
                                  side_effect=lambda **kw: plans[kw["module_id"]]),
                mock.patch.object(compose, "resolve_managed_parent", side_effect=resolve),
                mock.patch.object(registered, "materialize_registered", side_effect=execute),
                mock.patch("scripts.agora_install_materializer._lock") as lock,
            ):
                lock.return_value.__enter__.return_value = None
                result = self.fn(self.requests(), cache_dir=root)
            self.assertEqual(result, {n: plans[n].output for n in plans})
            self.assertEqual(state["prepare"], 1)
            self.assertEqual(state["lease"], 1)
            self.assertEqual(state["execution"], ["producer-a", "producer-b"])
            self.assertFalse(state["leased"])

    def test_preflight_second_producer_failure_does_not_prepare_or_publish_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, resolver, plans, resolve, execute = self.fixture(root)
            def plan(**kw):
                if kw["module_id"] == "module-b":
                    raise ValueError("second producer not installed")
                return plans[kw["module_id"]]
            with (
                mock.patch.object(compose, "_bundled_context_fabric_resolver", return_value=resolver),
                mock.patch.object(compose, "_candidate_versions_for_request",
                                  return_value=("cuc", {"0.2.8"})),
                mock.patch.object(compose, "_plan_requested_feature_module", side_effect=plan),
                mock.patch.object(compose, "resolve_managed_parent", side_effect=resolve),
                mock.patch.object(registered, "materialize_registered", side_effect=execute),
            ):
                with self.assertRaisesRegex(ValueError, "second producer"):
                    self.fn(self.requests(), cache_dir=root)
            self.assertEqual(state["prepare"], 0)
            self.assertEqual(state["execution"], [])

    def test_duplicate_module_is_rejected_before_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with (
                mock.patch.object(compose, "_bundled_context_fabric_resolver") as build,
                mock.patch.object(registered, "materialize_registered") as run,
            ):
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    self.fn([self.requests()[0], self.requests()[0]], cache_dir=root)
                build.assert_not_called()
                run.assert_not_called()

    def test_later_converter_failure_reports_published_module_truthfully(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, resolver, plans, resolve, execute = self.fixture(root)
            def fail_second(**kw):
                if kw["materializer_id"] == "producer-b":
                    raise RuntimeError("second failed")
                return execute(**kw)
            with (
                mock.patch.object(compose, "_bundled_context_fabric_resolver", return_value=resolver),
                mock.patch.object(compose, "_candidate_versions_for_request",
                                  return_value=("cuc", {"0.2.8"})),
                mock.patch.object(compose, "_plan_requested_feature_module",
                                  side_effect=lambda **kw: plans[kw["module_id"]]),
                mock.patch.object(compose, "resolve_managed_parent", side_effect=resolve),
                mock.patch.object(registered, "materialize_registered", side_effect=fail_second),
                mock.patch("scripts.agora_install_materializer._lock"),
            ):
                error_type = getattr(compose, "BatchMaterializationError", RuntimeError)
                with self.assertRaises(error_type) as caught:
                    self.fn(self.requests(), cache_dir=root)
            err = caught.exception
            self.assertEqual(err.failed_module_id, "module-b")
            self.assertEqual(err.published, {"module-a": plans["module-a"].output})
            self.assertFalse(state["leased"])

    def test_unique_common_version_is_selected_across_individually_ambiguous_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, resolver, plans, resolve, execute = self.fixture(root)
            def candidates(_resolver, entry, *, install_root=None, registry_path=None):
                return (
                    "cuc",
                    {"0.2.7", "0.2.8"} if entry["module_id"] == "module-a"
                    else {"0.2.8"},
                )
            def plan(**kw):
                self.assertEqual(kw["requested_version"], "0.2.8")
                return plans[kw["module_id"]]
            with (
                mock.patch.object(compose, "_bundled_context_fabric_resolver", return_value=resolver),
                mock.patch.object(compose, "_candidate_versions_for_request", side_effect=candidates),
                mock.patch.object(compose, "_plan_requested_feature_module", side_effect=plan),
                mock.patch.object(compose, "resolve_managed_parent", side_effect=resolve),
                mock.patch.object(registered, "materialize_registered", side_effect=execute),
                mock.patch("scripts.agora_install_materializer._lock"),
            ):
                result = self.fn(self.requests(), cache_dir=root)
            self.assertEqual(len(result), 2)
            self.assertEqual(state["prepare"], 1)
            self.assertEqual(state["lease"], 1)

    def test_disjoint_parent_version_sets_fail_before_plan_or_acquisition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, resolver, plans, resolve, execute = self.fixture(root)
            with (
                mock.patch.object(compose, "_bundled_context_fabric_resolver", return_value=resolver),
                mock.patch.object(compose, "_candidate_versions_for_request",
                                  side_effect=[("cuc", {"0.2.7"}), ("cuc", {"0.2.8"})]),
                mock.patch.object(compose, "_plan_requested_feature_module") as plan,
                mock.patch.object(compose, "resolve_managed_parent", side_effect=resolve),
                mock.patch.object(registered, "materialize_registered", side_effect=execute),
            ):
                with self.assertRaisesRegex(ValueError, "common|incompatible|version"):
                    self.fn(self.requests(), cache_dir=root)
                plan.assert_not_called()
            self.assertEqual(state["prepare"], 0)
            self.assertEqual(state["execution"], [])

    def test_second_parent_prepare_failure_has_no_partial_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, resolver, plans, resolve, execute = self.fixture(root)
            plans["module-b"].parent_id = "bhsa"
            plans["module-b"].version = "2021"
            plans["module-b"].parent_revision = "b" * 40
            def resolution(spec, fake, *, requested_version):
                if requested_version == "2021":
                    raise ValueError("second parent snapshot unavailable")
                return resolve(spec, fake, requested_version)
            with (
                mock.patch.object(compose, "_bundled_context_fabric_resolver", return_value=resolver),
                mock.patch.object(compose, "_candidate_versions_for_request",
                                  side_effect=[("cuc", {"0.2.8"}), ("bhsa", {"2021"})]),
                mock.patch.object(compose, "_plan_requested_feature_module",
                                  side_effect=lambda **kw: plans[kw["module_id"]]),
                mock.patch.object(compose, "resolve_managed_parent", side_effect=resolution),
                mock.patch.object(registered, "materialize_registered", side_effect=execute) as run,
                mock.patch("scripts.agora_install_materializer._lock"),
            ):
                with self.assertRaisesRegex(ValueError, "second parent"):
                    self.fn(self.requests(), cache_dir=root)
            run.assert_not_called()
            self.assertEqual(state["execution"], [])
            self.assertEqual(state["lease"], 1)

    @unittest.skipUnless(shutil.which("git"), "Git needed for real shared-parent snapshot test")
    def test_real_git_parent_single_prepare_with_two_independent_module_overlays(self):
        root_dir = Path(__file__).resolve().parents[1]
        cf_src = root_dir / "plugins" / "context-fabric" / "src"
        if str(cf_src) not in sys.path:
            sys.path.insert(0, str(cf_src))
        from agora_context_fabric.catalog import Catalog, ResourceSpec
        from agora_context_fabric.gitstore import GitStore
        from agora_context_fabric.resolver import ContextFabricResolver

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            upstream = root / "cuc-git"
            upstream.mkdir()
            for args in (
                ["git", "init", "-q"], ["git", "config", "user.name", "Agora"],
                ["git", "config", "user.email", "agora@example.invalid"],
            ):
                subprocess.run(args, cwd=upstream, check=True, capture_output=True)
            dataset = upstream / "tf" / "0.2.8"
            dataset.mkdir(parents=True)
            tf_warp = {
                "otype.tf": "@node\\n@valueType=str\\n\\n1-3\\tword\\n4\\ttablet\\n",
                "oslots.tf": "@edge\\n@valueType=str\\n\\n4\\t1-3\\n",
                "otext.tf": "@config\\n@sectionFeatures=tablet\\n",
            }
            for name, content in tf_warp.items():
                (dataset / name).write_text(content, encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=upstream, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=upstream, check=True)
            revision = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=upstream, text=True
            ).strip()
            resources = [ResourceSpec(
                id="cuc", name="Synthetic CUC", plugin="context-fabric",
                provider="context-fabric", kind="corpus", repository=str(upstream),
                languages=("ugaritic",), disciplines=(), ref=revision,
                tf_path="tf/0.2.8",
            )]
            for mod in ("module-a", "module-b"):
                resources.append(ResourceSpec(
                    id=mod, name=mod, plugin="context-fabric", provider="context-fabric",
                    kind="feature-module", repository="fixture/local-module",
                    languages=("ugaritic",), disciplines=(), parent="cuc",
                    parent_versions=("0.2.8",), tf_path="tf/0.2.8",
                    acquisition_strategy="local-module",
                    module_path=mod+"/tf", dependencies=(
                        {"role": "parent-base", "ref": revision},
                    ),
                ))
            store = GitStore(root / "cache", min_free_bytes=0)
            resolver = ContextFabricResolver(Catalog(resources), store)
            plans = {}
            for mod in ("module-a", "module-b"):
                plans[mod] = SimpleNamespace(
                    module_id=mod, plugin_id=mod, materializer_id="make-"+mod,
                    source=root / mod / "source", parent_id="cuc",
                    parent_revision=revision, version="0.2.8",
                    output=store.local_feature_module_path(mod, "tf/0.2.8"),
                    lock_path=store.locks_dir / (mod+".lock"),
                    spec={"parent_input": {"resource": "cuc",
                                          "parent_versions": ["0.2.8"],
                                          "required_paths": ["otype.tf","oslots.tf","otext.tf"]}},
                )
            requests = [
                {"module_id": mod, "plugin_id": mod,
                 "materializer_id": "make-"+mod, "source": plans[mod].source}
                for mod in plans
            ]
            def publish(**kw):
                self.assertTrue(kw["parent"].path.is_dir())
                self.assertEqual(kw["parent"].source_revision, revision)
                self.assertFalse((kw["output"] / "otype.tf").exists())
                kw["output"].mkdir(parents=True)
                (kw["output"] / (kw["materializer_id"] + ".tf")).write_text(
                    "@node\\n@valueType=str\\n\\n1\\tx\\n", encoding="utf-8"
                )
                return kw["output"]
            with (
                mock.patch.object(compose, "_bundled_context_fabric_resolver",
                                  return_value=resolver),
                mock.patch.object(compose, "_candidate_versions_for_request",
                                  return_value=("cuc", {"0.2.8"})),
                mock.patch.object(compose, "_plan_requested_feature_module",
                                  side_effect=lambda **kw: plans[kw["module_id"]]),
                mock.patch.object(resolver, "prepare", wraps=resolver.prepare) as prep,
                mock.patch.object(store, "acquire_cache_lease",
                                  wraps=store.acquire_cache_lease) as lease,
                mock.patch.object(registered, "materialize_registered",
                                  side_effect=publish),
            ):
                outputs = self.fn(requests, cache_dir=store.cache_dir)
                self.assertEqual(prep.call_count, 1)
                self.assertEqual(lease.call_count, 1)
            self.assertEqual(set(outputs), {"module-a", "module-b"})
            composed = resolver.prepare_with_modules(
                "cuc", version="0.2.8", modules=["module-a", "module-b"]
            )
            self.assertEqual(len(composed.modules), 2)
            for filename, content in tf_warp.items():
                self.assertEqual((composed.path / filename).read_text(), content)
                self.assertEqual((dataset / filename).read_text(), content)
            self.assertTrue((composed.path / "make-module-a.tf").is_file())
            self.assertTrue((composed.path / "make-module-b.tf").is_file())

    def test_batch_has_no_raw_output_parent_or_resolver_injection(self):
        import inspect
        signature = inspect.signature(self.fn)
        for field in ("resolver", "parent_path", "output", "trusted", "catalog"):
            self.assertNotIn(field, signature.parameters)
        self.assertNotIn(inspect.Parameter.VAR_KEYWORD,
                         {p.kind for p in signature.parameters.values()})


if __name__ == "__main__":
    unittest.main()
