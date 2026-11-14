"""#300: standalone index generation must supervise all Git child processes."""
from __future__ import annotations

import importlib.util
import math
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.gitstore_long_ops import GitStore as SupervisedGitStore
from agora_context_fabric.operation import (
    AcquisitionTimeout,
    OperationControl,
    current_operation,
    operation_scope,
)

MODULE_PATH = ROOT / "scripts" / "generate_context_fabric_collection_indexes.py"
SPEC = importlib.util.spec_from_file_location("generator_index_300", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


class _Resource:
    def __init__(self, name, path):
        self.id = name
        self.kind = "collection"
        self.member_index_path = path


class _Catalog:
    def __init__(self, root):
        self.root = root

    def get(self, name):
        return _Resource(name, self.root / f"{name}.yaml")


class _HangingGit:
    def __init__(self):
        self.killed = False
        self.returncode = None

    def communicate(self, timeout=None):
        if self.killed:
            self.returncode = -9
            return "", ""
        time.sleep(min(timeout or 0.001, 0.005))
        raise subprocess.TimeoutExpired(["git", "fetch"], timeout or 0)

    def kill(self):
        self.killed = True
        self.returncode = -9

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if not self.killed:
            raise subprocess.TimeoutExpired(["git", "fetch"], timeout or 0)
        return self.returncode


class GeneratorAcquisitionDeadline300(unittest.TestCase):
    def test_generator_uses_existing_supervised_gitstore(self):
        self.assertIs(generator.GitStore, SupervisedGitStore)

    def test_per_resource_deadlines_are_distinct_and_restore_parent_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            operations = []
            def generate(resource, *, source_revision, store):
                operation = current_operation()
                self.assertIsInstance(operation, OperationControl)
                self.assertGreater(operation.remaining_acquisition_seconds(), 0)
                self.assertEqual(operation.acquisition_timeout_seconds, 1.2)
                self.assertIsInstance(store, SupervisedGitStore)
                operations.append(operation)
                return f"index-{resource.id}"
            parent = OperationControl(acquisition_timeout_seconds=900)
            with (
                patch.object(generator.Catalog, "from_registry", return_value=_Catalog(root)),
                patch.object(generator, "configured_revision", return_value="a" * 40),
                patch.object(generator, "generate_resource_index", side_effect=generate),
                patch.object(generator, "preserve_canonical_verification", side_effect=lambda i, _: i),
                patch.object(generator, "dump_collection_index", side_effect=lambda i: i),
                operation_scope(parent),
            ):
                self.assertEqual(
                    generator.generate_documents(
                        root, resource_ids=("first", "second"),
                        cache_dir=root / "cache", max_acquire_minutes=0.02,
                    ),
                    {"first": "index-first", "second": "index-second"},
                )
                self.assertIs(current_operation(), parent)
            self.assertIsNone(current_operation())
            self.assertEqual(len(operations), 2)
            self.assertIsNot(operations[0], operations[1])

    def test_failure_restores_parent_context_and_does_not_declare_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with (
                patch.object(generator.Catalog, "from_registry", return_value=_Catalog(root)),
                patch.object(generator, "configured_revision", return_value="a" * 40),
                patch.object(generator, "generate_resource_index", side_effect=AcquisitionTimeout("fixture")),
            ):
                with self.assertRaisesRegex(AcquisitionTimeout, "fixture"):
                    generator.generate_documents(
                        root, resource_ids=("first",), cache_dir=root / "cache",
                        max_acquire_minutes=0.02,
                    )
            self.assertIsNone(current_operation())

    def test_invalid_generator_budget_is_rejected_before_creating_store(self):
        for bad in (0.0, -1.0, float("nan"), float("inf"), -float("inf")):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as tmp:
                with patch.object(generator, "GitStore") as store:
                    with self.assertRaises(ValueError):
                        generator.generate_documents(
                            Path(tmp), resource_ids=("bible",),
                            cache_dir=Path(tmp) / "cache", max_acquire_minutes=bad,
                        )
                    store.assert_not_called()

    def test_supervised_transport_enforces_deadline_and_kills_owned_process(self):
        process = _HangingGit()
        with tempfile.TemporaryDirectory() as tmp:
            store = generator.GitStore(Path(tmp) / "cache")
            control = OperationControl(acquisition_timeout_seconds=0.025)
            with (
                patch("agora_context_fabric.gitstore_long_ops.tracked_process_tree", return_value=nullcontext()),
                patch("agora_context_fabric.gitstore_long_ops.kill_process_tree", side_effect=lambda p: p.kill()) as kill,
                patch("agora_context_fabric.gitstore.subprocess.Popen", return_value=process),
                operation_scope(control),
            ):
                with self.assertRaises(AcquisitionTimeout):
                    store._run("fetch", "--quiet", "origin", "HEAD")
                self.assertTrue(process.killed)
                kill.assert_called_once_with(process)
            self.assertIsNone(current_operation())


if __name__ == "__main__":
    unittest.main()
