from __future__ import annotations

import multiprocessing
import shutil
import sys
import tempfile
import threading
import time
import types
import unittest
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog, ResourceSpec
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.resolver import PreparedCorpus
from agora_context_fabric.service import ContextFabricService


class _DiskUsage:
    def __init__(self, free: int):
        self.free = free


class _NeverEndingProcess:
    def __init__(self, on_poll=None):
        self.returncode = None
        self.on_poll = on_poll
        self.polls = 0
        self.terminated = False
        self.killed = False
        self.waited = False

    def poll(self):
        self.polls += 1
        if self.on_poll is not None:
            self.on_poll(self.polls)
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        self.waited = True
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


class _ImmediateProcess(_NeverEndingProcess):
    def __init__(self, returncode=0, on_poll=None):
        super().__init__(on_poll=on_poll)
        self.returncode = returncode


class ColdCompileWorkerContractTests(unittest.TestCase):
    def test_worker_calls_upstream_loader_without_reinterpreting_arguments(self):
        from agora_context_fabric.compile_worker import run_payload

        class Manager:
            def __init__(self):
                self.calls = []

            def load(self, path, name=None, features=None):
                self.calls.append((path, name, features))
                return {"ignored": True}

        manager = Manager()
        fake_module = types.ModuleType("cfabric_mcp")
        fake_module.corpus_manager = manager
        with unittest.mock.patch.dict(sys.modules, {"cfabric_mcp": fake_module}):
            run_payload(
                {
                    "path": "/tmp/exact-corpus",
                    "name": "fixture@1.0",
                    "features": ["lemma", "g_cons"],
                }
            )

        self.assertEqual(
            manager.calls,
            [("/tmp/exact-corpus", "fixture@1.0", ["lemma", "g_cons"])],
        )


class ColdCompileSupervisorContractTests(unittest.TestCase):
    def _supervisor(self, *, popen, disk_usage, monotonic=None):
        from agora_context_fabric.cold_compile import ColdCompileSupervisor

        return ColdCompileSupervisor(
            cfm_version="1",
            poll_interval=0,
            terminate_grace_seconds=0,
            popen=popen,
            disk_usage=disk_usage,
            monotonic=monotonic or time.monotonic,
            sleep=lambda _seconds: None,
        )

    def test_low_space_preflight_refuses_before_worker_spawn(self):
        from agora_context_fabric.cold_compile import ColdCompileLimitError

        spawned = []
        supervisor = self._supervisor(
            popen=lambda *args, **kwargs: spawned.append((args, kwargs)),
            disk_usage=lambda _path: _DiskUsage(free=999),
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ColdCompileLimitError) as raised:
                supervisor.run(
                    path=Path(tmp),
                    logical_name="fixture",
                    features=None,
                    compile_budget_bytes=600,
                    timeout_seconds=60,
                    min_free_bytes=500,
                    cancel_event=threading.Event(),
                )
        self.assertEqual(spawned, [])
        self.assertEqual(raised.exception.reason, "preflight-free-space")
        self.assertEqual(raised.exception.observed_free_bytes, 999)

    def test_output_threshold_stops_worker_and_waits_for_death(self):
        from agora_context_fabric.cold_compile import ColdCompileLimitError

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            process = _NeverEndingProcess(
                on_poll=lambda _count: (
                    (root / ".cfm" / "1").mkdir(parents=True, exist_ok=True),
                    (root / ".cfm" / "1" / "partial.bin").write_bytes(b"x" * 101),
                )
            )
            supervisor = self._supervisor(
                popen=lambda *args, **kwargs: process,
                disk_usage=lambda _path: _DiskUsage(free=10_000),
            )
            with self.assertRaises(ColdCompileLimitError) as raised:
                supervisor.run(
                    path=root,
                    logical_name="fixture",
                    features=None,
                    compile_budget_bytes=100,
                    timeout_seconds=60,
                    min_free_bytes=10,
                    cancel_event=threading.Event(),
                )

        self.assertEqual(raised.exception.reason, "compiled-output-budget")
        self.assertGreaterEqual(raised.exception.observed_compiled_bytes, 101)
        self.assertTrue(process.terminated or process.killed)
        self.assertTrue(process.waited)

    def test_runtime_free_space_threshold_stops_worker(self):
        from agora_context_fabric.cold_compile import ColdCompileLimitError

        frees = iter((10_000, 100))
        process = _NeverEndingProcess()
        supervisor = self._supervisor(
            popen=lambda *args, **kwargs: process,
            disk_usage=lambda _path: _DiskUsage(free=next(frees, 100)),
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ColdCompileLimitError) as raised:
                supervisor.run(
                    path=Path(tmp),
                    logical_name="fixture",
                    features=None,
                    compile_budget_bytes=1_000,
                    timeout_seconds=60,
                    min_free_bytes=500,
                    cancel_event=threading.Event(),
                )
        self.assertEqual(raised.exception.reason, "observed-free-space")
        self.assertTrue(process.waited)
        self.assertNotIn("quota", str(raised.exception).lower())
        self.assertIn("observed", str(raised.exception).lower())

    def test_timeout_stops_worker(self):
        from agora_context_fabric.cold_compile import ColdCompileLimitError

        class Clock:
            def __init__(self):
                self.value = -1.0

            def __call__(self):
                self.value += 1.0
                return self.value

        process = _NeverEndingProcess()
        supervisor = self._supervisor(
            popen=lambda *args, **kwargs: process,
            disk_usage=lambda _path: _DiskUsage(free=10_000),
            monotonic=Clock(),
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ColdCompileLimitError) as raised:
                supervisor.run(
                    path=Path(tmp),
                    logical_name="fixture",
                    features=None,
                    compile_budget_bytes=1_000,
                    timeout_seconds=2,
                    min_free_bytes=10,
                    cancel_event=threading.Event(),
                )
        self.assertEqual(raised.exception.reason, "timeout")
        self.assertTrue(process.waited)

    def test_cancellation_stops_worker(self):
        from agora_context_fabric.cold_compile import ColdCompileCancelled

        cancel = threading.Event()
        process = _NeverEndingProcess(on_poll=lambda _count: cancel.set())
        supervisor = self._supervisor(
            popen=lambda *args, **kwargs: process,
            disk_usage=lambda _path: _DiskUsage(free=10_000),
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ColdCompileCancelled):
                supervisor.run(
                    path=Path(tmp),
                    logical_name="fixture",
                    features=None,
                    compile_budget_bytes=1_000,
                    timeout_seconds=60,
                    min_free_bytes=10,
                    cancel_event=cancel,
                )
        self.assertTrue(process.waited)

    def test_success_reports_final_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfm = root / ".cfm" / "1"
            cfm.mkdir(parents=True)
            (cfm / "payload.bin").write_bytes(b"x" * 25)
            process = _ImmediateProcess(returncode=0)
            supervisor = self._supervisor(
                popen=lambda *args, **kwargs: process,
                disk_usage=lambda _path: _DiskUsage(free=9_000),
            )
            result = supervisor.run(
                path=root,
                logical_name="fixture",
                features="lemma",
                compile_budget_bytes=1_000,
                timeout_seconds=60,
                min_free_bytes=10,
                cancel_event=threading.Event(),
            )
        self.assertEqual(result.observed_compiled_bytes, 25)
        self.assertEqual(result.observed_free_bytes, 9_000)
        self.assertTrue(process.waited)


class _Lease:
    def __init__(self, path: Path):
        self.path = path
        self.released = False

    def release(self):
        self.released = True


class _Loader:
    def __init__(self):
        self.calls = []
        self.unloaded = []

    def load(self, path: str, name=None, features=None):
        self.calls.append((path, name, features))
        return {"path": path, "name": name}

    def unload(self, name: str):
        self.unloaded.append(name)


class _Resolver:
    def __init__(self, store: GitStore, prepared: PreparedCorpus):
        self.store = store
        self.prepared = prepared

    def prepare_with_modules(self, _resource_id: str, **_kwargs):
        return self.prepared


class _SuccessfulColdCompiler:
    def __init__(self, *, create_marker=True, block_until: threading.Event | None = None):
        self.create_marker = create_marker
        self.block_until = block_until
        self.calls = []
        self.entered = threading.Event()

    def run(self, **kwargs):
        self.calls.append(kwargs)
        self.entered.set()
        if self.block_until is not None:
            self.block_until.wait(3)
        path = Path(kwargs["path"])
        cfm = path / ".cfm" / "1"
        cfm.mkdir(parents=True, exist_ok=True)
        (cfm / "payload.bin").write_bytes(b"compiled")
        if self.create_marker:
            (cfm / "meta.json").write_text("{}", encoding="utf-8")
        progress = kwargs.get("progress")
        if progress is not None:
            progress(
                {
                    "elapsed_seconds": 0.25,
                    "observed_compiled_bytes": 8,
                    "observed_free_bytes": 10_000,
                }
            )
        return types.SimpleNamespace(
            elapsed_seconds=0.25,
            observed_compiled_bytes=8,
            observed_free_bytes=10_000,
        )


class _CancellingColdCompiler:
    def __init__(self):
        self.entered = threading.Event()

    def run(self, **kwargs):
        from agora_context_fabric.cold_compile import ColdCompileCancelled

        self.entered.set()
        cancel = kwargs["cancel_event"]
        while not cancel.wait(0.01):
            pass
        raise ColdCompileCancelled(
            "cold compilation cancelled",
            reason="cancelled",
            observed_compiled_bytes=0,
            observed_free_bytes=10_000,
            elapsed_seconds=0.1,
        )


def _hold_compile_lock(cache_dir: str, path: str, ready, release):
    store = GitStore(Path(cache_dir), snapshot_soft_limit_bytes=10_000, min_free_bytes=0)
    with store.compile_lock(Path(path), timeout=1):
        ready.set()
        release.wait(3)


class ServiceColdCompileRuntimeTests(unittest.TestCase):
    @staticmethod
    def _resource() -> ResourceSpec:
        return ResourceSpec(
            id="fixture",
            name="Fixture",
            plugin="context-fabric",
            provider="context-fabric",
            kind="corpus",
            repository="unused/repository",
            languages=("test",),
            disciplines=("testing",),
        )

    def _fixture(self, root: Path):
        store = GitStore(root / "cache", snapshot_soft_limit_bytes=10_000, min_free_bytes=0)
        path = store.snapshots_dir / "fixture" / "a" * 40 / "corpora" / "tf" / "1.0"
        path.mkdir(parents=True)
        (path / "otype.tf").write_text("@node\n", encoding="utf-8")
        (path / "word.tf").write_text("abc", encoding="utf-8")
        store.touch_cache_object(path)
        prepared = PreparedCorpus(
            "fixture",
            None,
            "fixture@1.0",
            "tf/1.0",
            path,
            "1.0",
            "a" * 40,
        )
        return store, path, prepared

    def _service(self, store, prepared, loader, cold_compiler):
        return ContextFabricService(
            Catalog([self._resource()]),
            _Resolver(store, prepared),
            loader,
            cold_compiler=cold_compiler,
            cfm_version="1",
        )

    def test_warm_marker_bypasses_cold_compiler_and_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, path, prepared = self._fixture(Path(tmp))
            marker = path / ".cfm" / "1" / "meta.json"
            marker.parent.mkdir(parents=True)
            marker.write_text("{}", encoding="utf-8")
            loader = _Loader()
            cold = _SuccessfulColdCompiler()
            service = self._service(store, prepared, loader, cold)
            result = service.load(
                "fixture",
                max_compile_gb=0.000000001,
                max_compile_minutes=0.000000001,
            )
            self.assertEqual(result["logical_name"], "fixture@1.0")
            self.assertEqual(cold.calls, [])
            self.assertEqual(len(loader.calls), 1)

    def test_successful_cold_worker_is_followed_by_parent_warm_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, path, prepared = self._fixture(Path(tmp))
            loader = _Loader()
            cold = _SuccessfulColdCompiler()
            service = self._service(store, prepared, loader, cold)
            result = service.load(
                "fixture",
                features=["lemma"],
                max_compile_gb=1,
                max_compile_minutes=2,
            )
            self.assertEqual(result["logical_name"], "fixture@1.0")
            self.assertEqual(len(cold.calls), 1)
            call = cold.calls[0]
            self.assertEqual(Path(call["path"]), path)
            self.assertEqual(call["logical_name"], "fixture@1.0")
            self.assertEqual(call["features"], ["lemma"])
            self.assertEqual(len(loader.calls), 1)
            self.assertTrue((path / ".cfm" / "1" / "meta.json").is_file())
            self.assertEqual(service.cache_status()["active_loads"], [])

    def test_zero_exit_without_marker_fails_closed_and_cleans_current_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, path, prepared = self._fixture(Path(tmp))
            loader = _Loader()
            cold = _SuccessfulColdCompiler(create_marker=False)
            service = self._service(store, prepared, loader, cold)
            with self.assertRaisesRegex(RuntimeError, "completion marker"):
                service.load("fixture")
            self.assertEqual(loader.calls, [])
            self.assertFalse((path / ".cfm" / "1").exists())
            self.assertTrue((path / "otype.tf").is_file())
            self.assertEqual(store.remove_cache_object(path)["removed_entries"], 1)

    def test_failure_cleanup_preserves_source_and_other_cfm_versions(self):
        from agora_context_fabric.cold_compile import ColdCompileLimitError

        class FailingCompiler:
            def run(self, **kwargs):
                path = Path(kwargs["path"])
                current = path / ".cfm" / "1"
                current.mkdir(parents=True)
                (current / "partial.bin").write_bytes(b"partial")
                raise ColdCompileLimitError(
                    "observed compiled output crossed configured threshold",
                    reason="compiled-output-budget",
                    observed_compiled_bytes=7,
                    observed_free_bytes=10_000,
                    elapsed_seconds=0.1,
                )

        with tempfile.TemporaryDirectory() as tmp:
            store, path, prepared = self._fixture(Path(tmp))
            old = path / ".cfm" / "0" / "meta.json"
            old.parent.mkdir(parents=True)
            old.write_text("old", encoding="utf-8")
            service = self._service(store, prepared, _Loader(), FailingCompiler())
            with self.assertRaises(ColdCompileLimitError):
                service.load("fixture")
            self.assertFalse((path / ".cfm" / "1").exists())
            self.assertEqual(old.read_text(encoding="utf-8"), "old")
            self.assertTrue((path / "word.tf").is_file())
            self.assertEqual(service.cache_status()["active_loads"], [])

    def test_active_status_exposes_progress_and_cancel_fields(self):
        release = threading.Event()
        with tempfile.TemporaryDirectory() as tmp:
            store, _path, prepared = self._fixture(Path(tmp))
            cold = _SuccessfulColdCompiler(block_until=release)
            service = self._service(store, prepared, _Loader(), cold)
            errors = []
            thread = threading.Thread(
                target=lambda: self._capture(errors, service.load, "fixture"),
                daemon=True,
            )
            thread.start()
            self.assertTrue(cold.entered.wait(1))
            active = service.cache_status()["active_loads"]
            self.assertEqual(len(active), 1)
            record = active[0]
            for key in (
                "load_id",
                "resource_id",
                "member_id",
                "logical_name",
                "phase",
                "elapsed_seconds",
                "source_bytes",
                "observed_compiled_bytes",
                "compile_budget_bytes",
                "observed_free_bytes",
                "min_free_bytes",
                "cancellation_capable",
                "cancellation_requested",
            ):
                self.assertIn(key, record)
            self.assertEqual(record["phase"], "compiling")
            self.assertTrue(record["cancellation_capable"])
            release.set()
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])

    @staticmethod
    def _capture(errors, func, *args, **kwargs):
        try:
            func(*args, **kwargs)
        except BaseException as exc:  # deliberately capture thread outcome for assertions
            errors.append(exc)

    def test_local_duplicate_is_fail_fast_and_does_not_spawn_second_worker(self):
        release = threading.Event()
        with tempfile.TemporaryDirectory() as tmp:
            store, _path, prepared = self._fixture(Path(tmp))
            cold = _SuccessfulColdCompiler(block_until=release)
            service = self._service(store, prepared, _Loader(), cold)
            errors = []
            thread = threading.Thread(
                target=lambda: self._capture(errors, service.load, "fixture"),
                daemon=True,
            )
            thread.start()
            self.assertTrue(cold.entered.wait(1))
            started = time.monotonic()
            with self.assertRaisesRegex(RuntimeError, "already active"):
                service.load("fixture")
            self.assertLess(time.monotonic() - started, 0.5)
            self.assertEqual(len(cold.calls), 1)
            release.set()
            thread.join(2)
            self.assertEqual(errors, [])

    def test_cancel_api_stops_active_worker_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, path, prepared = self._fixture(Path(tmp))
            cold = _CancellingColdCompiler()
            service = self._service(store, prepared, _Loader(), cold)
            errors = []
            thread = threading.Thread(
                target=lambda: self._capture(errors, service.load, "fixture"),
                daemon=True,
            )
            thread.start()
            self.assertTrue(cold.entered.wait(1))
            load_id = service.cache_status()["active_loads"][0]["load_id"]
            first = service.cancel_load(load_id)
            second = service.cancel_load(load_id)
            self.assertTrue(first["found"])
            self.assertTrue(first["cancellation_requested"])
            self.assertTrue(second["cancellation_requested"])
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(len(errors), 1)
            from agora_context_fabric.cold_compile import ColdCompileCancelled

            self.assertIsInstance(errors[0], ColdCompileCancelled)
            self.assertFalse((path / ".cfm" / "1").exists())
            self.assertEqual(service.cache_status()["active_loads"], [])
            missing = service.cancel_load(load_id)
            self.assertFalse(missing["found"])

    def test_compile_lock_is_cross_process_exclusive_and_crash_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, path, _prepared = self._fixture(Path(tmp))
            ctx = multiprocessing.get_context("spawn")
            ready = ctx.Event()
            release = ctx.Event()
            holder = ctx.Process(
                target=_hold_compile_lock,
                args=(str(store.cache_dir), str(path), ready, release),
            )
            holder.start()
            self.assertTrue(ready.wait(3))
            with self.assertRaises(TimeoutError):
                with store.compile_lock(path, timeout=0.1):
                    pass
            release.set()
            holder.join(5)
            self.assertEqual(holder.exitcode, 0)
            with store.compile_lock(path, timeout=0.5):
                pass

    def test_cold_warm_race_rechecks_marker_after_compile_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, path, prepared = self._fixture(Path(tmp))
            cold = _SuccessfulColdCompiler()
            loader = _Loader()
            original = store.compile_lock

            @contextmanager
            def completes_before_lock_body(candidate, timeout=0.25):
                with original(candidate, timeout=timeout):
                    marker = path / ".cfm" / "1" / "meta.json"
                    marker.parent.mkdir(parents=True, exist_ok=True)
                    marker.write_text("{}", encoding="utf-8")
                    yield

            store.compile_lock = completes_before_lock_body
            service = self._service(store, prepared, loader, cold)
            service.load("fixture")
            self.assertEqual(cold.calls, [])
            self.assertEqual(len(loader.calls), 1)

    def test_cache_transition_is_not_held_during_cold_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, _path, prepared = self._fixture(Path(tmp))
            other = GitStore(store.cache_dir, snapshot_soft_limit_bytes=10_000, min_free_bytes=0)

            class Compiler(_SuccessfulColdCompiler):
                def run(self, **kwargs):
                    with other.cache_transition(exclusive=True, timeout=0.1):
                        pass
                    return super().run(**kwargs)

            service = self._service(store, prepared, _Loader(), Compiler())
            service.load("fixture")


if __name__ == "__main__":
    unittest.main()
