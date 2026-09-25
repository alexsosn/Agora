"""Offline tests for the load-smoke cache lifecycle (unload/remove/prune/reload)
and its CI wiring, including the BHSA feature-module regression case.

Each lifecycle guard has a test that trips it on its own, and one test runs
the lifecycle against the real GitStore/ContextFabricService with a corpus
snapshot, a hard-linked feature-module overlay and a module snapshot."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from scripts import smoke_context_fabric_resources as smoke

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.resolver import ContextFabricResolver
from agora_context_fabric.service import ContextFabricService

WORKFLOW = ROOT / ".github" / "workflows" / "context-fabric-load-smoke.yml"
REVISION = "4db00e2157915495e1a4d3d57e41223df24775da"


def _reload(revision: str = REVISION):
    calls: list[int] = []

    def reload_and_check():
        calls.append(1)
        return {"source_revision": revision}, [{"feature": "phono", "node": 1}]

    return reload_and_check, calls


class RealStoreLifecycleTests(unittest.TestCase):
    """The lifecycle against the real store/service contract (no network)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        cache = Path(self._tmp.name) / "cache"
        self.store = GitStore(cache, min_free_bytes=0)
        catalog = Catalog.from_registry(ROOT)
        self.service = ContextFabricService(
            catalog, ContextFabricResolver(catalog, self.store), loader=None
        )
        corpus = self.store.snapshots_dir / "bhsa" / REVISION / "corpora" / "tf" / "2021"
        corpus.mkdir(parents=True)
        (corpus / "otype.tf").write_bytes(b"@node\n" + b"x" * 8192)
        (corpus / "g_cons.tf").write_bytes(b"@node\n" + b"y" * 4096)
        module = self.store.snapshots_dir / "bhsa-phono" / "abc123" / "feature-modules" / "tf" / "2021"
        module.mkdir(parents=True)
        (module / "phono.tf").write_bytes(b"@node\n" + b"z" * 1024)
        overlay = self.store.overlays_dir / "bhsa" / REVISION / "digest"
        overlay.mkdir(parents=True)
        for name in ("otype.tf", "g_cons.tf"):
            os.link(corpus / name, overlay / name)
        os.link(module / "phono.tf", overlay / "phono.tf")
        for path in (corpus, module, overlay):
            self.store.touch_cache_object(path)
        self.paths = (corpus, module, overlay)

    def tearDown(self):
        self._tmp.cleanup()

    def test_removes_snapshot_overlay_and_module_then_reloads(self):
        reload_and_check, calls = _reload()
        report = smoke.exercise_cache_lifecycle(
            "bhsa-phono",
            smoke.LOAD_CASES["bhsa-phono"],
            self.service,
            self.store,
            member_id=None,
            first_result={"source_revision": REVISION},
            reload_and_check=reload_and_check,
        )

        by_resource = {item["resource_id"]: item for item in report["removals"]}
        self.assertEqual(by_resource["bhsa"]["removed_entries"], 2, "snapshot + overlay")
        self.assertEqual(by_resource["bhsa-phono"]["removed_entries"], 1)
        for path in self.paths:
            self.assertFalse(path.exists(), path)
        self.assertEqual(report["cache_bytes_after_remove"], 0)
        self.assertEqual(self.service.cache_status()["cache_bytes"], 0)
        self.assertGreaterEqual(report["reclaimed_apparent_bytes"], report["removed_bytes"])
        self.assertEqual(calls, [1])

    def test_leased_object_makes_removal_incomplete_and_stops_before_reload(self):
        reload_and_check, calls = _reload()
        lease = self.store.acquire_cache_lease(self.paths[0])
        try:
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                smoke.exercise_cache_lifecycle(
                    "bhsa-phono",
                    smoke.LOAD_CASES["bhsa-phono"],
                    self.service,
                    self.store,
                    member_id=None,
                    first_result={"source_revision": REVISION},
                    reload_and_check=reload_and_check,
                )
        finally:
            lease.release()
        self.assertEqual(calls, [])


class _FakeStore:
    def __init__(self, cache_dir: Path, objects: dict[str, list[Path]], *, stale_index: bool = False):
        self.cache_dir = cache_dir
        self.objects = objects
        self.stale_index = stale_index

    def cache_entries(self, resource_id: str):
        return [
            {
                "kind": "corpus-snapshot",
                "resource_id": resource_id,
                "revision": REVISION,
                "relative_path": "tf/2021",
                "path": str(path),
                "size_bytes": smoke._tree_bytes(path) if path.exists() else 0,
                "in_use": False,
            }
            for path in self.objects.get(resource_id, [])
            if self.stale_index or path.exists()
        ]


class _FakeService:
    """Models ContextFabricService's result fields; behaviour is overridable."""

    def __init__(self, store: _FakeStore):
        self.store = store
        self.calls: list[str] = []
        self.removal_overrides: dict[str, object] = {}
        self.prune_result = {"removed_entries": 0, "removed_bytes": 0, "after_bytes": 0,
                             "skipped_in_use": 0, "blocked_by_transition": 0}
        self.keep_bytes_in: Path | None = None
        self.stale_cache_bytes: int | None = None
        self._status_calls = 0

    def cache_status(self):
        self.calls.append("status")
        self._status_calls += 1
        total = sum(
            int(entry["size_bytes"])
            for resource_id in self.store.objects
            for entry in self.store.cache_entries(resource_id)
        )
        if self.stale_cache_bytes is not None and self._status_calls > 1:
            total = self.stale_cache_bytes
        return {"cache_bytes": total, "loaded_corpora": []}

    def remove_cached(self, resource_id, *, member_id=None):
        self.calls.append(f"remove:{resource_id}")
        entries = self.store.cache_entries(resource_id)
        removed = sum(int(entry["size_bytes"]) for entry in entries)
        for entry in entries:
            path = Path(entry["path"])
            if self.keep_bytes_in is not None:
                self.keep_bytes_in.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(self.keep_bytes_in / path.name))
            elif path.exists():
                shutil.rmtree(path)
        result = {
            "matched_entries": len(entries),
            "removed_entries": len(entries),
            "removed_bytes": removed,
            "skipped_in_use": 0,
            "blocked_by_transition": 0,
            "complete": True,
        }
        result.update(self.removal_overrides)
        return result

    def prune_cache(self):
        self.calls.append("prune")
        return dict(self.prune_result)


class LifecycleGuardTests(unittest.TestCase):
    """Each guard in exercise_cache_lifecycle trips on its own failure."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.objects = {
            "bhsa": [self._object("bhsa", 4096)],
            "bhsa-phono": [self._object("phono", 1024)],
        }

    def tearDown(self):
        self._tmp.cleanup()

    def _object(self, name: str, size: int) -> Path:
        path = self.root / "snapshots" / name
        path.mkdir(parents=True)
        (path / "otype.tf").write_bytes(b"x" * size)
        return path

    def _run(self, service, store, revision: str = REVISION):
        reload_and_check, calls = _reload(revision)
        self.reload_calls = calls
        return smoke.exercise_cache_lifecycle(
            "bhsa-phono",
            smoke.LOAD_CASES["bhsa-phono"],
            service,
            store,
            member_id=None,
            first_result={"source_revision": REVISION},
            reload_and_check=reload_and_check,
        )

    def test_happy_path_removes_parent_then_module_then_prunes(self):
        store = _FakeStore(self.root, self.objects)
        service = _FakeService(store)
        report = self._run(service, store)
        self.assertEqual([item["resource_id"] for item in report["removals"]], ["bhsa", "bhsa-phono"])
        self.assertLess(service.calls.index("remove:bhsa-phono"), service.calls.index("prune"))
        self.assertEqual(self.reload_calls, [1])

    def test_still_loaded_corpus_fails_before_removal(self):
        store = _FakeStore(self.root, self.objects)
        service = _FakeService(store)
        service.cache_status = lambda: {"cache_bytes": 1, "loaded_corpora": [{"logical_name": "bhsa"}]}
        with self.assertRaisesRegex(RuntimeError, "still loaded"):
            self._run(service, store)
        self.assertEqual(service.calls, [])

    def test_missing_cache_objects_fail(self):
        store = _FakeStore(self.root, {"bhsa": self.objects["bhsa"]})
        with self.assertRaisesRegex(RuntimeError, "no cache objects found for 'bhsa-phono'"):
            self._run(_FakeService(store), store)

    def test_incomplete_removal_fails(self):
        store = _FakeStore(self.root, self.objects)
        service = _FakeService(store)
        service.removal_overrides = {"complete": False}
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            self._run(service, store)

    def test_partial_removal_count_fails(self):
        store = _FakeStore(self.root, self.objects)
        service = _FakeService(store)
        service.removal_overrides = {"matched_entries": 2}
        with self.assertRaisesRegex(RuntimeError, "not every matched"):
            self._run(service, store)

    def test_removal_reclaiming_no_bytes_fails(self):
        store = _FakeStore(self.root, self.objects)
        service = _FakeService(store)
        service.removal_overrides = {"removed_bytes": 0}
        with self.assertRaisesRegex(RuntimeError, "reclaimed no bytes"):
            self._run(service, store)

    def test_removed_paths_still_on_disk_fail(self):
        store = _FakeStore(self.root, self.objects)
        service = _FakeService(store)
        service.remove_cached = lambda resource_id, member_id=None: {
            "matched_entries": 1, "removed_entries": 1, "removed_bytes": 1, "complete": True,
        }
        with self.assertRaisesRegex(RuntimeError, "still exist"):
            self._run(service, store)

    def test_stale_index_after_removal_fails(self):
        store = _FakeStore(self.root, self.objects, stale_index=True)
        with self.assertRaisesRegex(RuntimeError, "still indexes removed"):
            self._run(_FakeService(store), store)

    def test_cache_status_still_counting_removed_bytes_fails(self):
        store = _FakeStore(self.root, self.objects)
        service = _FakeService(store)
        service.stale_cache_bytes = 5120
        with self.assertRaisesRegex(RuntimeError, "still counts removed bytes"):
            self._run(service, store)

    def test_bytes_that_never_leave_the_cache_directory_fail(self):
        store = _FakeStore(self.root, self.objects)
        service = _FakeService(store)
        service.keep_bytes_in = self.root / "tmp" / "trash"
        with self.assertRaisesRegex(RuntimeError, "left the cache directory"):
            self._run(service, store)

    def test_blocked_prune_fails(self):
        store = _FakeStore(self.root, self.objects)
        service = _FakeService(store)
        service.prune_result["blocked_by_transition"] = 1
        with self.assertRaisesRegex(RuntimeError, "prune was blocked"):
            self._run(service, store)
        self.assertEqual(self.reload_calls, [])

    def test_prune_growing_the_cache_fails(self):
        store = _FakeStore(self.root, self.objects)
        service = _FakeService(store)
        service.prune_result["after_bytes"] = 1
        with self.assertRaisesRegex(RuntimeError, "cache grew during prune"):
            self._run(service, store)

    def test_reload_resolving_another_revision_fails(self):
        store = _FakeStore(self.root, self.objects)
        with self.assertRaisesRegex(RuntimeError, "reload resolved"):
            self._run(_FakeService(store), store, revision="def")


class _RecordingService:
    instances: list["_RecordingService"] = []

    def __init__(self, catalog, resolver, loader):
        self.loads: list[tuple[str, dict]] = []
        _RecordingService.instances.append(self)

    def load(self, resource_id, **kwargs):
        self.loads.append((resource_id, kwargs))
        dataset = Path(tempfile.mkdtemp())
        (dataset / "otype.tf").write_text("@node\n", encoding="utf-8")
        return {
            "logical_name": "bhsa+bhsa-phono",
            "resource_id": resource_id,
            "relative_path": "tf/2021",
            "path": str(dataset),
            "source_revision": REVISION,
            "corpus": {"name": "bhsa"},
        }

    def unload(self, logical_name):
        return {"was_loaded": True}


class RunCaseModuleWiringTests(unittest.TestCase):
    def test_module_case_passes_modules_to_load_and_reports_them(self):
        values = {
            "g_cons": {1: "B"},
            "phono": {1: "bᵊ", 2: "rēšˌîṯ"},
        }
        api = types.SimpleNamespace(
            F=types.SimpleNamespace(
                **{
                    name: types.SimpleNamespace(v=lambda node, data=data: data.get(node))
                    for name, data in values.items()
                }
            )
        )
        fake_cfabric = types.ModuleType("cfabric_mcp")
        fake_cfabric.corpus_manager = types.SimpleNamespace(get_api=lambda _name: api)
        _RecordingService.instances.clear()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            sys.modules, {"cfabric_mcp": fake_cfabric}
        ), patch("agora_context_fabric.service.ContextFabricService", _RecordingService):
            report = smoke.run_case("bhsa-phono", Path(tmp) / "cache")

        (service,) = _RecordingService.instances
        (resource_id, kwargs) = service.loads[0]
        self.assertEqual(resource_id, "bhsa")
        self.assertEqual(kwargs.get("modules"), ["bhsa-phono"])
        self.assertEqual(report["modules"], ["bhsa-phono"])
        self.assertEqual(report["status"], "ok")


class FeatureModuleCaseTests(unittest.TestCase):
    def test_bhsa_phono_case_loads_parent_with_module_and_checks_module_feature(self):
        case = smoke.LOAD_CASES["bhsa-phono"]
        self.assertEqual(case.resource_id, "bhsa")
        self.assertEqual(case.modules, ("bhsa-phono",))
        features = {item.feature for item in smoke.SEMANTIC_EXPECTATIONS["bhsa-phono"]}
        self.assertIn("phono", features)
        self.assertTrue(features <= set(case.features))

    def test_module_case_cannot_be_bound_to_registry_evidence(self):
        with self.assertRaisesRegex(RuntimeError, "no registry verification check"):
            smoke.validate_case_check_binding("bhsa-phono", "resource-load/bhsa", member_id=None)


class LifecycleWorkflowTests(unittest.TestCase):
    @staticmethod
    def _jobs():
        return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]

    @staticmethod
    def _runs(job):
        return [step.get("run", "") for step in job.get("steps", []) if isinstance(step, dict)]

    def test_representative_loads_exercise_cache_lifecycle(self):
        runs = self._runs(self._jobs()["representative-loads"])
        smoke_runs = [run for run in runs if "smoke_context_fabric_resources.py" in run]
        self.assertEqual(len(smoke_runs), 1)
        self.assertIn("--lifecycle", smoke_runs[0])

    def test_feature_module_job_loads_bhsa_phono_with_lifecycle(self):
        job = self._jobs()["feature-module-load"]
        runs = [run for run in self._runs(job) if "smoke_context_fabric_resources.py" in run]
        self.assertEqual(len(runs), 1)
        self.assertIn("bhsa-phono", runs[0])
        self.assertIn("--lifecycle", runs[0])
        self.assertNotIn("--check-id", runs[0])

    def test_feature_module_registry_and_lifecycle_tests_retrigger_smoke(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for watched in (
            "registry/feature-modules.yaml",
            "tests/test_context_fabric_cache_lifecycle_smoke.py",
        ):
            self.assertEqual(text.count(f"      - '{watched}'"), 2, watched)


if __name__ == "__main__":
    unittest.main()
