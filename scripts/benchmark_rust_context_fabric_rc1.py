#!/usr/bin/env python3
"""One-off, reproducible native TF vs Rust CF benchmark on Agora's pinned OCP release.

Produces machine-readable evidence; does not change Agora runtime/version pins.
Run on Linux + Python 3.13 after installing text-fabric==13.1.0 and
context-fabric==0.6.0rc1. No hidden fixture or generated synthetic corpus.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from importlib.metadata import version
from pathlib import Path

ASSET = "https://github.com/alexsosn/Pseudepigrapha-TF/releases/download/v1.0.0/tf-1.0.zip"
EXPECTED_SHA256 = "d2dfad7e643699617a9493b9f5d724868f8027dd5f2e88bd558451e3e7819b7a"
METRICS = (
    "load_seconds", "peak_rss_mib",
    "lookup_10000_median_seconds", "search_50_median_seconds"
)


def known_legacy_warm_cache_failure(engine: str, iteration: int, stderr: str) -> bool:
    """Only classify the exact #263 empty-feature cache failure as known.

    A missing file in any other feature, format, or engine is an unexpected
    failure and remains a blocking regression. Never repair upstream data.
    """
    return (
        engine == "legacy"
        and iteration > 0
        and "FileNotFoundError" in stderr
        and "No such file or directory" in stderr
        and any(
            suffix in stderr
            for suffix in (
                "/.cfm/1/features/ellipsis_text_strings.npy",
                "/.cfm/1/features/prefix_utf8_strings.npy",
            )
        )
    )


def summarize_attempts(attempts: list[dict]) -> dict:
    """Keep success sample counts visible; missing warm runs are not zero."""
    cold = next(
        (a["metrics"] for a in attempts if a["iteration"] == 0 and a["status"] == "ok"),
        None,
    )
    warm = [
        a["metrics"] for a in attempts
        if a["iteration"] > 0 and a["status"] == "ok"
    ]
    return {
        "cold": {k: cold[k] for k in METRICS} if cold else None,
        "cold_n": int(cold is not None),
        "warm_median": {
            k: round(statistics.median(item[k] for item in warm), 6)
            for k in METRICS
        } if warm else None,
        "warm_n": len(warm),
        "known_failures": sum(a["status"] == "known_upstream_failure" for a in attempts),
    }


def bytes_under(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def worker(engine: str, corpus: Path, output: Path) -> None:
    if engine == "tf":
        from tf.fabric import Fabric
        package = "text-fabric"
    elif engine == "legacy":
        from cfabric.core import Fabric
        package = "context-fabric"
    else:
        from cfabric import Fabric
        package = "context-fabric"

    started = time.perf_counter()
    api = Fabric(locations=str(corpus), silent="deep").loadAll()
    load_s = time.perf_counter() - started
    if api is None:
        raise RuntimeError(f"{engine}: loadAll() returned None")

    F, L, S = api.F, api.L, api.S
    otype = str(F.otype.v(1))
    nodes = range(1, 257)
    t = time.perf_counter()
    signatures = [
        [n, F.otype.v(n), list(L.u(n))[:8]] for n in nodes
    ]
    traversal_s = time.perf_counter() - t
    lookup_samples = []
    for _ in range(5):
        t = time.perf_counter()
        for n in range(1, 10001):
            F.otype.v((n - 1) % 256 + 1)
        lookup_samples.append(time.perf_counter() - t)

    search_samples = []
    search_signature = None
    for _ in range(5):
        t = time.perf_counter()
        found = list(S.search(otype, limit=50))
        search_samples.append(time.perf_counter() - t)
        sig = [list(row) for row in found]
        if search_signature is None:
            search_signature = sig
        elif sig != search_signature:
            raise RuntimeError(f"{engine}: nondeterministic result content")

    result = {
        "engine": engine,
        "package_version": version(package),
        "python": sys.version.split()[0],
        "load_seconds": round(load_s, 6),
        "traversal_256_seconds": round(traversal_s, 6),
        "lookup_10000_median_seconds": round(statistics.median(lookup_samples), 6),
        "search_50_median_seconds": round(statistics.median(search_samples), 6),
        "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
        "signature": signatures,
        "search_signature": search_signature,
        "slot_type": otype,
    }
    output.write_text(json.dumps(result), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", choices=["tf", "legacy", "rust"])
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--legacy-python", type=Path)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker, args.corpus, args.output)
        return
    if not args.legacy_python:
        parser.error("--legacy-python is required for the actual Agora baseline")

    report = {
        "dataset": "Pseudepigrapha-TF v1.0.0 / tf-1.0.zip (registered Agora corpus)",
        "asset_url": ASSET,
        "asset_sha256": EXPECTED_SHA256,
        "comparisons": {},
        "errors": [],
        "known_upstream_failures": [],
        "environment": {
            "python": sys.version.split()[0],
            "system": platform.platform(),
            "machine": platform.machine(),
            "method": "isolated subprocesses: 1 cold + 2 warm, per-process peak ru_maxrss",
            "warning": "Process RSS is not aggregate Agora server + worker RSS",
        },
    }
    report_file = Path("rust-cfabric-rc1-benchmark.json")
    try:
        with tempfile.TemporaryDirectory(prefix="agora-cfabric-bench-") as temp:
            work = Path(temp)
            downloaded = work / "tf-1.0.zip"
            urllib.request.urlretrieve(ASSET, downloaded)
            actual = hashlib.sha256(downloaded.read_bytes()).hexdigest()
            if actual != EXPECTED_SHA256:
                raise RuntimeError(f"Asset checksum mismatch: {actual}")

            extracted = work / "extracted"
            extracted.mkdir()
            with zipfile.ZipFile(downloaded) as z:
                for item in z.infolist():
                    dest = (extracted / item.filename).resolve()
                    if not dest.is_relative_to(extracted.resolve()):
                        raise ValueError(f"Unsafe archive member {item.filename}")
                z.extractall(extracted)

            candidates = sorted({
                p.parent for p in extracted.rglob("otype.tf")
                if (p.parent / "oslots.tf").exists()
            })
            if len(candidates) != 1:
                raise RuntimeError(f"Expected one native TF dataset, found {candidates}")
            source = candidates[0]
            source_bytes = bytes_under(source)
            report["source_tf_bytes"] = sum(p.stat().st_size for p in source.glob("*.tf"))
            report["source_tree_bytes"] = source_bytes
            report["archive_bytes"] = downloaded.stat().st_size

            for engine in ("tf", "legacy", "rust"):
                corpus = work / engine / "corpus"
                corpus.parent.mkdir()
                shutil.copytree(source, corpus)
                home = work / engine / "home"
                home.mkdir()
                env = dict(os.environ, HOME=str(home), CFABRIC_CACHE=str(home / "cfabric-cache"))
                results = []
                attempts = []
                for iteration in range(3):
                    metric_file = work / f"{engine}-{iteration}.json"
                    python = args.legacy_python if engine == "legacy" else Path(sys.executable)
                    cmd = [str(python), __file__, "--worker", engine,
                           "--corpus", str(corpus), "--output", str(metric_file)]
                    try:
                        proc = subprocess.run(
                            cmd, text=True, capture_output=True, env=env, timeout=600
                        )
                        if proc.returncode:
                            detail = proc.stderr[-3000:]
                            if known_legacy_warm_cache_failure(engine, iteration, detail):
                                item = {
                                    "iteration": iteration, "status": "known_upstream_failure",
                                    "issue": "https://github.com/alexsosn/Agora/issues/263",
                                    "stderr_tail": detail,
                                }
                                report["known_upstream_failures"].append(
                                    {"engine": engine, "iteration": iteration, "issue": item["issue"]}
                                )
                            else:
                                item = {"iteration": iteration, "status": "failed",
                                        "exit_code": proc.returncode, "stderr_tail": detail}
                                report["errors"].append(
                                    f"{engine}[{iteration}]: exit={proc.returncode}; {detail}"
                                )
                            attempts.append(item)
                            continue
                        sample = json.loads(metric_file.read_text(encoding="utf-8"))
                        results.append(sample)
                        attempts.append({"iteration": iteration, "status": "ok", "metrics": sample})
                    except Exception as exc:
                        attempts.append({"iteration": iteration, "status": "failed",
                                         "exception": repr(exc)})
                        report["errors"].append(f"{engine}[{iteration}]: {exc}")

                sizes = {
                    "cfr_bytes": bytes_under(corpus / ".cfr"),
                    "cfm_bytes": bytes_under(corpus / ".cfm"),
                    "created_home_cache_bytes": bytes_under(home),
                }
                sizes["created_corpus_bytes"] = bytes_under(corpus) - source_bytes
                sizes["other_created_corpus_bytes"] = (
                    sizes["created_corpus_bytes"] - sizes["cfr_bytes"] - sizes["cfm_bytes"]
                )
                report["comparisons"][engine] = {
                    "runs": results,
                    "attempts": attempts,
                    **sizes,
                    **summarize_attempts(attempts),
                }
            a = report["comparisons"]["tf"]["runs"]
            b = report["comparisons"]["rust"]["runs"]
            c = report["comparisons"]["legacy"]["runs"]
            if a and b:
                left = a[0]["signature"]
                right = b[0]["signature"]
                report["equal_first_256_nodes_and_upward_locality"] = left == right
                report["equal_first_256_nodes_and_upward_locality_as_sets"] = all(
                    x[0] == y[0] and x[1] == y[1] and sorted(x[2]) == sorted(y[2])
                    for x, y in zip(left, right)
                ) and len(left) == len(right)
                differences = [(x, y) for x, y in zip(left, right) if x != y]
                report["graph_mismatch_count"] = len(differences)
                report["graph_mismatch_examples"] = [
                    {"tf": x, "rust": y} for x, y in differences[:6]
                ]
                report["equal_first_50_search_results"] = (
                    sorted(a[0]["search_signature"]) == sorted(b[0]["search_signature"])
                )
                if not report["equal_first_256_nodes_and_upward_locality_as_sets"] or not report["equal_first_50_search_results"]:
                    report["errors"].append("TF/Rust CF semantic result mismatch")
            if a and c:
                report["legacy_vs_tf_equal_first_256_as_sets"] = all(
                    x[0] == y[0] and x[1] == y[1] and sorted(x[2]) == sorted(y[2])
                    for x, y in zip(a[0]["signature"], c[0]["signature"])
                )
                report["legacy_vs_tf_equal_first_50_search_results"] = (
                    sorted(a[0]["search_signature"]) == sorted(c[0]["search_signature"])
                )
                if not report["legacy_vs_tf_equal_first_256_as_sets"] or not report["legacy_vs_tf_equal_first_50_search_results"]:
                    report["errors"].append("TF/legacy CF semantic result mismatch")
    except Exception as e:
        report["errors"].append(f"harness: {e}")
    finally:
        report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({
            "report": str(report_file),
            "dataset": report["dataset"],
            "source_tf_bytes": report.get("source_tf_bytes"),
            "results": {
                k: {kk: vv for kk, vv in v.items() if kk not in {"runs", "attempts"}}
                for k, v in report["comparisons"].items()
            },
            "semantic_equal": (
                report.get("equal_first_256_nodes_and_upward_locality"),
                report.get("equal_first_50_search_results")
            ),
            "errors": report["errors"],
            "known_upstream_failures": report["known_upstream_failures"],
        }, indent=2))
    if report["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
