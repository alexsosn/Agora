from __future__ import annotations

import gc
import sys
import unittest
import warnings
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

import test_context_fabric_load_safety_runtime as runtime_tests


SUCCESSFUL_LOAD_CASES = (
    "test_warm_marker_bypasses_cold_compiler_and_limits",
    "test_successful_cold_worker_is_followed_by_parent_warm_load",
    "test_active_status_exposes_progress_and_cancel_fields",
    "test_local_duplicate_is_fail_fast_and_does_not_spawn_second_worker",
    "test_cold_warm_race_rechecks_marker_after_compile_lock",
    "test_cache_transition_is_not_held_during_cold_worker",
)


class ContextFabricLockLifetimeRegressionTests(unittest.TestCase):
    def _run_case_and_capture_cache_lock_warnings(self, method_name: str) -> list[str]:
        result = unittest.TestResult()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            case = runtime_tests.ServiceColdCompileRuntimeTests(method_name)
            case.run(result)
            del case
            gc.collect()

        self.assertEqual(result.errors, [], f"nested runtime case errored: {method_name}")
        self.assertEqual(result.failures, [], f"nested runtime case failed: {method_name}")
        self.assertEqual(result.skipped, [], f"nested runtime case skipped: {method_name}")

        leaks: list[str] = []
        for warning in caught:
            if not issubclass(warning.category, ResourceWarning):
                continue
            message = str(warning.message).replace("\\", "/")
            if "unclosed file" in message and "cache/locks/cache-objects/" in message:
                leaks.append(message)
        return leaks

    def test_successful_load_cases_do_not_leak_cache_object_lock_handles(self):
        leaking: dict[str, list[str]] = {}
        for method_name in SUCCESSFUL_LOAD_CASES:
            with self.subTest(method=method_name):
                leaks = self._run_case_and_capture_cache_lock_warnings(method_name)
                if leaks:
                    leaking[method_name] = leaks

        self.assertEqual(
            leaking,
            {},
            "successful service loads must unload before their temporary cache roots disappear",
        )


if __name__ == "__main__":
    unittest.main()
