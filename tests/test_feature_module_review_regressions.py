from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog, ResourceSpec
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.mcp_tools import register_tools
from agora_context_fabric.resolver import ContextFabricResolver
from agora_context_fabric.service import ContextFabricService
from scripts.audit_context_fabric_sources import audit_catalog


class _Loader:
    def load(self, path: str, name: str | None = None, features=None):
        return {"path": path, "name": name, "features": features}


class _MCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name=None):
        def decorator(func):
            self.tools[name or func.__name__] = func
            return func

        return decorator


class FeatureModuleReviewRegressionTests(unittest.TestCase):
    @staticmethod
    def _init_repo(path: Path) -> None:
        path.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.name", "Agora Tests"], cwd=path, check=True)

    @staticmethod
    def _commit(path: Path) -> None:
        subprocess.run(["git", "add", "."], cwd=path, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=path, check=True)

    def _parent_repo(self, root: Path) -> Path:
        source = root / "parent"
        self._init_repo(source)
        for version in ("c", "2021"):
            tf = source / "tf" / version
            tf.mkdir(parents=True)
            (tf / "otype.tf").write_text(
                "@node\n"
                "@dataset=BHSA\n"
                f"@version={version}\n"
                "@valueType=str\n"
                "\n"
                "1-10\tword\n",
                encoding="utf-8",
            )
            (tf / "oslots.tf").write_text(
                "@edge\n@valueType=str\n\n10\t1\n",
                encoding="utf-8",
            )
            (tf / "word.tf").write_text(
                "@node\n"
                "@coreData=BHSA\n"
                f"@coreVersion={version}\n"
                "@valueType=str\n"
                "\n"
                f"1\tparent-{version}\n",
                encoding="utf-8",
            )
        self._commit(source)
        return source

    def _module_repo(
        self,
        root: Path,
        *,
        warp: bool = False,
        core_data: str = "BHSA",
        core_version: str = "c",
        node: int = 5,
        name: str = "module",
    ) -> Path:
        source = root / name
        self._init_repo(source)
        tf = source / "tf" / "c"
        tf.mkdir(parents=True)
        (tf / "actor.tf").write_text(
            "@node\n"
            f"@coreData={core_data}\n"
            f"@coreVersion={core_version}\n"
            "@valueType=str\n"
            "\n"
            f"{node}\tactor\n",
            encoding="utf-8",
        )
        if warp:
            (tf / "otype.tf").write_text("@node\n", encoding="utf-8")
        self._commit(source)
        return source

    @staticmethod
    def _module_spec(module_id: str, module_repo: Path, *, parent_versions=("c",)) -> ResourceSpec:
        return ResourceSpec(
            id=module_id,
            name=f"{module_id} annotations",
            plugin="context-fabric",
            provider="context-fabric",
            kind="feature-module",
            repository=str(module_repo),
            languages=("hebrew",),
            disciplines=("biblical-studies",),
            tf_path="tf/c",
            parent="bhsa",
            parent_versions=parent_versions,
            module_path=f"example/{module_id}/tf",
            module_status="legacy",
        )

    @classmethod
    def _catalog(cls, parent_repo: Path, module_repo: Path, parent_versions=("c",)) -> Catalog:
        return Catalog(
            [
                ResourceSpec(
                    id="bhsa",
                    name="BHSA fixture",
                    plugin="context-fabric",
                    provider="context-fabric",
                    kind="corpus",
                    repository=str(parent_repo),
                    languages=("hebrew",),
                    disciplines=("biblical-studies",),
                ),
                cls._module_spec(
                    "bhsa-participants-actor",
                    module_repo,
                    parent_versions=parent_versions,
                ),
            ]
        )

    def test_global_feature_module_schema_is_provider_neutral(self):
        schema = json.loads((ROOT / "registry/schema/resources.schema.json").read_text(encoding="utf-8"))
        document = {
            "schema_version": 1,
            "resources": [
                {
                    "id": "generic-addon",
                    "name": "Generic addon",
                    "plugin": "example-plugin",
                    "provider": "example-provider",
                    "kind": "feature-module",
                    "parent": "example-parent",
                    "compatibility": {"parent_versions": ["1"]},
                    "module": {"status": "optional"},
                    "languages": ["english"],
                    "disciplines": ["history"],
                    "description": "A provider-neutral child module.",
                    "upstream": {"repository": "example/module"},
                    "acquisition": {"strategy": "repository"},
                    "licenses": {"data": "unknown"},
                    "verification": {"status": "experimental"},
                }
            ],
        }
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(document)), [])

    def test_context_fabric_parser_requires_tf_specific_module_paths(self):
        document = {
            "resources": [
                {
                    "id": "bad-addon",
                    "name": "Bad addon",
                    "plugin": "context-fabric",
                    "provider": "context-fabric",
                    "kind": "feature-module",
                    "languages": ["hebrew"],
                    "disciplines": ["biblical-studies"],
                    "upstream": {"repository": "example/module"},
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "requires upstream.module, upstream.tf_path"):
            Catalog._resources_from_document(document)

    def test_frozen_v01_scope_still_exact_for_corpora_and_collections(self):
        catalog = Catalog.from_registry(ROOT)
        with (ROOT / "registry" / "v0.1.yaml").open("r", encoding="utf-8") as fh:
            scope = yaml.safe_load(fh)
        core_ids = {
            resource.id
            for resource in catalog.resources()
            if resource.kind in {"corpus", "collection"}
        }
        self.assertEqual(core_ids, set(scope["required_resources"]))
        self.assertEqual(len(catalog.search(kind="feature-module")), 21)

    def test_default_discovery_excludes_non_loadable_feature_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog = self._catalog(self._parent_repo(root), self._module_repo(root))
            resolver = ContextFabricResolver(catalog, GitStore(root / "cache"))
            service = ContextFabricService(catalog, resolver, _Loader())

            self.assertEqual([item["id"] for item in service.list_resources()], ["bhsa"])
            self.assertEqual(
                [item["id"] for item in service.list_resources(kind="feature-module")],
                ["bhsa-participants-actor"],
            )
            with self.assertRaisesRegex(ValueError, "must be selected while preparing its parent"):
                resolver.prepare("bhsa-participants-actor")

    def test_legacy_module_can_be_loaded_by_selecting_compatible_parent_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog = self._catalog(self._parent_repo(root), self._module_repo(root))
            resolver = ContextFabricResolver(catalog, GitStore(root / "cache"))

            with self.assertRaisesRegex(ValueError, "not compatible"):
                resolver.prepare_with_modules("bhsa", modules=["bhsa-participants-actor"])

            prepared = resolver.prepare_with_modules(
                "bhsa",
                version="c",
                modules=["bhsa-participants-actor"],
            )
            self.assertEqual(prepared.version, "c")
            self.assertEqual(prepared.relative_path, "tf/c")
            self.assertEqual(prepared.logical_name, "bhsa@c+bhsa-participants-actor")
            self.assertTrue((prepared.path / "actor.tf").is_file())

    def test_module_combinations_have_distinct_ordered_logical_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = self._parent_repo(root)
            first_repo = self._module_repo(root, name="module-one")
            second_repo = self._module_repo(root, name="module-two")
            catalog = Catalog(
                [
                    ResourceSpec(
                        id="bhsa",
                        name="BHSA fixture",
                        plugin="context-fabric",
                        provider="context-fabric",
                        kind="corpus",
                        repository=str(parent),
                        languages=("hebrew",),
                        disciplines=("biblical-studies",),
                    ),
                    self._module_spec("module-one", first_repo),
                    self._module_spec("module-two", second_repo),
                ]
            )
            resolver = ContextFabricResolver(catalog, GitStore(root / "cache"))
            first = resolver.prepare_with_modules("bhsa", version="c", modules=["module-one"])
            second = resolver.prepare_with_modules("bhsa", version="c", modules=["module-two"])
            ordered = resolver.prepare_with_modules(
                "bhsa", version="c", modules=["module-one", "module-two"]
            )
            reversed_order = resolver.prepare_with_modules(
                "bhsa", version="c", modules=["module-two", "module-one"]
            )
            self.assertEqual(first.logical_name, "bhsa@c+module-one")
            self.assertEqual(second.logical_name, "bhsa@c+module-two")
            self.assertNotEqual(ordered.logical_name, reversed_order.logical_name)

    def test_parent_description_is_offline_when_default_version_is_unpinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog = self._catalog(self._parent_repo(root), self._module_repo(root))

            class NoNetworkResolver:
                def default_corpus_version(self, resource_id):
                    raise AssertionError("describe_resource must not resolve upstream")

            service = ContextFabricService(catalog, NoNetworkResolver(), _Loader())
            description = service.describe_resource("bhsa")
            self.assertIsNone(description["default_version"])
            self.assertIsNone(description["available_modules"])
            self.assertEqual(len(description["registered_modules"]), 1)
            registered = description["registered_modules"][0]
            self.assertEqual(registered["compatible_parent_versions"], ["c"])
            self.assertIsNone(registered["compatible_with_default"])

    def test_mcp_load_forwards_explicit_parent_version(self):
        class Service:
            def __init__(self):
                self.kwargs = None

            def load(self, resource_id, **kwargs):
                self.kwargs = (resource_id, kwargs)
                return {"resource_id": resource_id}

            def prepare(self, resource_id, **kwargs):
                return {"resource_id": resource_id, **kwargs}

            def list_resources(self, *args, **kwargs):
                return []

            def describe_resource(self, resource_id):
                return {"id": resource_id}

            def list_members(self, *args, **kwargs):
                return {"members": []}

        mcp = _MCP()
        service = Service()
        register_tools(mcp, service)
        mcp.tools["load_corpus"](
            "bhsa",
            version="c",
            modules=["bhsa-participants-actor"],
        )
        self.assertEqual(
            service.kwargs,
            (
                "bhsa",
                {
                    "member_id": None,
                    "features": None,
                    "modules": ["bhsa-participants-actor"],
                    "version": "c",
                },
            ),
        )

    def test_feature_module_with_parent_warp_is_rejected_before_materialization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._module_repo(root, warp=True)
            store = GitStore(root / "cache")
            repo = store.ensure_metadata(str(source), cache_key="bad-module")
            with self.assertRaisesRegex(ValueError, "parent warp file"):
                store.feature_files(repo, "tf/c")
            with self.assertRaisesRegex(ValueError, "parent warp file"):
                store.materialize_feature_module(repo, "tf/c")
            self.assertFalse((repo / "tf/c/actor.tf").exists())

    def test_source_audit_verifies_core_identity_version_and_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = self._parent_repo(root)
            module = self._module_repo(root)
            catalog = self._catalog(parent, module)
            report = audit_catalog(catalog, GitStore(root / "audit-cache"))
            self.assertTrue(report["ok"], report)
            item = next(value for value in report["resources"] if value["kind"] == "feature-module")
            self.assertEqual(item["verified_parent_versions"], ["c"])
            self.assertEqual(item["core_data"], "BHSA")
            self.assertEqual(item["core_version_evidence"], ["c"])
            self.assertEqual(item["max_referenced_node"], 5)
            self.assertIn("warp_fingerprint", item["parent_compatibility_evidence"]["c"])

            wrong_core = self._module_repo(root, core_data="OTHER", name="wrong-core")
            wrong_report = audit_catalog(
                self._catalog(parent, wrong_core), GitStore(root / "wrong-core-cache")
            )
            self.assertFalse(wrong_report["ok"])
            self.assertIn(
                "does not match parent",
                next(v for v in wrong_report["resources"] if v["kind"] == "feature-module")["error"],
            )

            wrong_version = self._module_repo(root, core_version="2021", name="wrong-version")
            version_report = audit_catalog(
                self._catalog(parent, wrong_version), GitStore(root / "wrong-version-cache")
            )
            self.assertFalse(version_report["ok"])
            self.assertIn(
                "core-version metadata conflicts",
                next(v for v in version_report["resources"] if v["kind"] == "feature-module")["error"],
            )

            out_of_bounds = self._module_repo(root, node=11, name="out-of-bounds")
            bounds_report = audit_catalog(
                self._catalog(parent, out_of_bounds), GitStore(root / "bounds-cache")
            )
            self.assertFalse(bounds_report["ok"])
            self.assertIn(
                "beyond parent",
                next(v for v in bounds_report["resources"] if v["kind"] == "feature-module")["error"],
            )

    def test_source_audit_rejects_nonexistent_declared_parent_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = self._parent_repo(root)
            module = self._module_repo(root)
            broken = self._catalog(parent, module, parent_versions=("missing",))
            broken_report = audit_catalog(broken, GitStore(root / "broken-audit-cache"))
            self.assertFalse(broken_report["ok"])
            broken_item = next(
                value for value in broken_report["resources"] if value["kind"] == "feature-module"
            )
            self.assertIn("does not expose declared compatible version", broken_item["error"])


if __name__ == "__main__":
    unittest.main()
