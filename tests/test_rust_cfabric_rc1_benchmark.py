"""Focused behavioral regressions for the opt-in Rust CF research benchmark.

These tests exercise only the harness's reporting/fail-closed boundary and do
not assert third-party corpus engine semantics.
"""
import unittest
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_rust_context_fabric_rc1.py"
spec = importlib.util.spec_from_file_location("cfbench_research", SOURCE)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


MISSING_EMPTY_STRINGS = (
    "FileNotFoundError: [Errno 2] No such file or directory: "
    "'/tmp/bench/legacy/corpus/.cfm/1/features/ellipsis_text_strings.npy'"
)


class BenchmarkHarnessTests(unittest.TestCase):
    def test_classify_only_missing_cache_of_actually_empty_tf_feature(self):
        with TemporaryDirectory() as temp:
            corpus = Path(temp)
            (corpus / "resource_name.tf").write_text("@node\n@valueType=str\n\n")
            missing = (
                f"FileNotFoundError: [Errno 2] No such file or directory: "
                f"'{corpus}/.cfm/1/features/resource_name_strings.npy'"
            )
            assert benchmark.known_legacy_warm_cache_failure("legacy", 1, missing, corpus)
            assert not benchmark.known_legacy_warm_cache_failure("rust", 1, missing, corpus)
            assert not benchmark.known_legacy_warm_cache_failure("legacy", 0, missing, corpus)
            assert not benchmark.known_legacy_warm_cache_failure(
                "legacy", 1, missing.replace("FileNotFoundError", "PermissionError"), corpus
            )
            (corpus / "resource_name.tf").write_text("@node\n@valueType=str\n\n1\tvalue\n")
            assert not benchmark.known_legacy_warm_cache_failure("legacy", 1, missing, corpus)
            (corpus / "resource_name.tf").unlink()
            assert not benchmark.known_legacy_warm_cache_failure("legacy", 1, missing, corpus)
            (corpus / "other.tf").write_text("@node\n@valueType=str\n\n")
            assert not benchmark.known_legacy_warm_cache_failure(
                "legacy", 1, missing.replace("resource_name", "../other"), corpus
            )

    def test_per_engine_attempts_preserve_gaps_without_inventing_warm_numbers(self):
        attempts = [
            {"iteration": 0, "status": "ok", "metrics": {
                "load_seconds": 10.0,
                "peak_rss_mib": 800.0,
                "lookup_10000_median_seconds": 0.1,
                "search_50_median_seconds": 0.2,
            }},
            {"iteration": 1, "status": "known_upstream_failure"},
            {"iteration": 2, "status": "ok", "metrics": {
                "load_seconds": 0.5,
                "peak_rss_mib": 200.0,
                "lookup_10000_median_seconds": 0.05,
                "search_50_median_seconds": 0.06,
            }}
        ]
        out = benchmark.summarize_attempts(attempts)
        assert out["cold"]["load_seconds"] == 10
        assert out["warm_median"]["load_seconds"] == 0.5
        assert out["warm_n"] == 1
        assert out["known_failures"] == 1
    
    def test_warm_cache_missing_does_not_get_fabricated_statistics(self):
        out = benchmark.summarize_attempts([
            {"iteration": 0, "status": "ok", "metrics": {
                "load_seconds": 10.0, "peak_rss_mib": 100.0,
                "lookup_10000_median_seconds": 0.1,
                "search_50_median_seconds": 0.2,
            }},
            {"iteration": 1, "status": "known_upstream_failure"},
            {"iteration": 2, "status": "known_upstream_failure"},
        ])
        assert out["warm_n"] == 0
        assert out["warm_median"] is None
        assert out["known_failures"] == 2
    