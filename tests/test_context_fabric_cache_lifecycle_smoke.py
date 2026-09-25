"""Offline tests for the load-smoke cache lifecycle (unload/remove/prune/reload)
and its CI wiring, including the BHSA feature-module regression case."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts import smoke_context_fabric_resources as smoke

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

WORKFLOW = ROOT / ".github" / "workflows" / "context-fabric-load-smoke.yml"


class _FakeStore:
    def __init__(self, cache_dir: Path, objects: dict[str, list[Path]]):
        self.cache_dir = cache_dir
        self.objects = objects

    def cache_entries(self, resource_id: str):
        return [
            {
                "kind": "corpus-snapshot",
                "resource_id": resource_id,
                "relative_path": "tf/2021",
                "path": str(path),
                "size_bytes": smoke._tree_bytes(path),
            }
            for path in self.objects.get(resource_id, [])
            if path.exists()
        ]


class _FakeService:
    def __init__(self, store: _FakeStore, *, delete: bool = True, complete: bool = True):
        self.store = store
        self.delete = delete
        self.complete = complete
        self.calls: list[str] = []

    def cache_status(self):
        self.calls.append("status")
        total = sum(
            int(entry["size_bytes"])
            for resource_id in self.store.objects
            for entry in self.store.cache_entries(resource_id)
        )
        return {"cache_bytes": total, "loaded_corpora": []}

    def remove_cached(self, resource_id, *, member_id=None):
        self.calls.append(f"remove:{resource_id}")
        entries = self.store.cache_entries(resource_id)
        removed = sum(int(entry["size_bytes"]) for entry in entries)
        if self.delete:
            for entry in entries:
                shutil.rmtree(entry["path"])
        return {
            "matched_entries": len(entries),
            "removed_entries": len(entries),
            "removed_bytes": removed,
            "complete": self.complete,
        }

    def prune_cache(self):
        self.calls.append("prune")
        return {"removed_entries": 0, "removed_bytes": 0, "after_bytes": 0}


def _make_object(root: Path, name: str, size: int) -> Path:
    path = root / "snapshots" / name
    path.mkdir(parents=True)
    (path / "otype.tf").write_bytes(b"x" * size)
    return path


class CacheLifecycleTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.case = smoke.LOAD_CASES["bhsa-phono"]
        self.store = _FakeStore(
            self.root,
            {
                "bhsa": [_make_object(self.root, "bhsa", 4096)],
                "bhsa-phono": [_make_object(self.root, "phono", 1024)],
            },
        )
        self.first = {"source_revision": "abc"}
        self.reloads = 0

    def tearDown(self):
        self._tmp.cleanup()

    def _reload(self, revision: str = "abc"):
        def reload_and_check():
            self.reloads += 1
            return {"source_revision": revision}, [{"feature": "phono", "node": 1}]

        return reload_and_check

    def _run(self, service, reload_and_check=None):
        return smoke.exercise_cache_lifecycle(
            "bhsa-phono",
            self.case,
            service,
            self.store,
            member_id=None,
            first_result=self.first,
            reload_and_check=reload_and_check or self._reload(),
        )

    def test_removes_parent_and_module_prunes_and_reloads(self):
        service = _FakeService(self.store)
        report = self._run(service)

        self.assertEqual(report["status"], "ok")
        self.assertEqual(
            [item["resource_id"] for item in report["removals"]], ["bhsa", "bhsa-phono"]
        )
        self.assertEqual(report["removed_bytes"], 4096 + 1024)
        self.assertGreaterEqual(report["reclaimed_on_disk_bytes"], 4096 + 1024)
        self.assertEqual(report["cache_bytes_after_remove"], 0)
        self.assertEqual(self.reloads, 1)
        self.assertLess(service.calls.index("remove:bhsa-phono"), service.calls.index("prune"))

    def test_incomplete_removal_fails(self):
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            self._run(_FakeService(self.store, complete=False))
        self.assertEqual(self.reloads, 0)

    def test_reported_removal_that_leaves_files_on_disk_fails(self):
        with self.assertRaisesRegex(RuntimeError, "still exist"):
            self._run(_FakeService(self.store, delete=False))
        self.assertEqual(self.reloads, 0)

    def test_reload_resolving_another_revision_fails(self):
        with self.assertRaisesRegex(RuntimeError, "reload resolved"):
            self._run(_FakeService(self.store), self._reload("def"))

    def test_still_loaded_corpus_fails_before_removal(self):
        service = _FakeService(self.store)
        service.cache_status = lambda: {"cache_bytes": 1, "loaded_corpora": [{"logical_name": "bhsa"}]}
        with self.assertRaisesRegex(RuntimeError, "still loaded"):
            self._run(service)
        self.assertEqual(service.calls, [])

    def test_cache_status_still_counting_removed_bytes_fails(self):
        service = _FakeService(self.store)
        original = service.cache_status
        statuses = iter([original(), {"cache_bytes": 5120, "loaded_corpora": []}])
        service.cache_status = lambda: next(statuses)
        with self.assertRaisesRegex(RuntimeError, "still counts removed bytes"):
            self._run(service)


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

    def test_feature_module_registry_changes_retrigger_smoke(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(text.count("      - 'registry/feature-modules.yaml'"), 2)


if __name__ == "__main__":
    unittest.main()
