from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .load_safety import cfm_version_dir, directory_bytes


@dataclass(frozen=True)
class ColdCompileResult:
    elapsed_seconds: float
    observed_compiled_bytes: int
    observed_free_bytes: int


class ColdCompileError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        reason: str,
        observed_compiled_bytes: int = 0,
        observed_free_bytes: int | None = None,
        elapsed_seconds: float = 0.0,
        worker_exit_code: int | None = None,
        diagnostic: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.observed_compiled_bytes = observed_compiled_bytes
        self.observed_free_bytes = observed_free_bytes
        self.elapsed_seconds = elapsed_seconds
        self.worker_exit_code = worker_exit_code
        self.diagnostic = diagnostic


class ColdCompileLimitError(ColdCompileError):
    """A configured observed resource threshold prevented/terminated a compile."""


class ColdCompileCancelled(ColdCompileError):
    """The caller explicitly requested cancellation of an active cold compile."""


class ColdCompileWorkerError(ColdCompileError):
    """The contained upstream loader exited unsuccessfully."""


class ColdCompileSupervisor:
    """Run one cold Context-Fabric load behind observable process boundaries.

    Output-size and free-space checks are polling guardrails. They intentionally
    describe *observed* threshold crossings rather than pretending to be an
    operating-system quota. The configured host free-space reserve supplies the
    headroom for writes that can occur between samples.
    """

    def __init__(
        self,
        *,
        cfm_version: str,
        poll_interval: float = 0.5,
        terminate_grace_seconds: float = 2.0,
        popen: Callable[..., Any] | None = None,
        disk_usage: Callable[[Path], Any] | None = None,
        monotonic: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        if poll_interval < 0:
            raise ValueError("poll_interval must be >= 0")
        if terminate_grace_seconds < 0:
            raise ValueError("terminate_grace_seconds must be >= 0")
        if not cfm_version:
            raise ValueError("cfm_version is required")
        self.cfm_version = str(cfm_version)
        self.poll_interval = float(poll_interval)
        self.terminate_grace_seconds = float(terminate_grace_seconds)
        self._popen = popen or subprocess.Popen
        self._disk_usage = disk_usage or shutil.disk_usage
        self._monotonic = monotonic or time.monotonic
        self._sleep = sleep or time.sleep

    def _free_bytes(self, path: Path) -> int:
        return int(self._disk_usage(path).free)

    def _observations(self, path: Path, started: float) -> dict[str, Any]:
        return {
            "elapsed_seconds": max(0.0, self._monotonic() - started),
            "observed_compiled_bytes": directory_bytes(
                cfm_version_dir(path, self.cfm_version)
            ),
            "observed_free_bytes": self._free_bytes(path),
        }

    @staticmethod
    def _read_diagnostic(path: Path) -> dict[str, Any] | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def _wait_after_stop(self, process: Any) -> None:
        """Confirm process death; escalate from terminate to kill when necessary."""

        try:
            process.terminate()
        except (OSError, ProcessLookupError):
            pass

        deadline = self._monotonic() + self.terminate_grace_seconds
        while process.poll() is None and self._monotonic() < deadline:
            remaining = max(0.0, deadline - self._monotonic())
            self._sleep(min(max(self.poll_interval, 0.01), remaining))

        if process.poll() is None:
            try:
                process.kill()
            except (OSError, ProcessLookupError):
                pass
        process.wait()

    @staticmethod
    def _limit_message(
        reason: str,
        *,
        compiled: int,
        budget: int,
        free: int,
        reserve: int,
        elapsed: float,
        timeout: float,
    ) -> str:
        if reason == "compiled-output-budget":
            return (
                "observed Context-Fabric compiled output crossed the configured cold-load "
                f"threshold ({compiled} > {budget} bytes); the worker was stopped. "
                "This is a polling guardrail, so writes may occur between observations. "
                "Inspect corpus_cache_status and prune_corpus_cache before retrying."
            )
        if reason == "observed-free-space":
            return (
                "observed free space fell below the configured Context-Fabric host reserve "
                f"({free} < {reserve} bytes); the worker was stopped. This is an observed "
                "polling threshold, not a byte-perfect filesystem limit. Inspect "
                "corpus_cache_status and prune_corpus_cache before retrying."
            )
        if reason == "timeout":
            return (
                "observed Context-Fabric cold-load elapsed time crossed the configured "
                f"threshold ({elapsed:.3f} >= {timeout:.3f} seconds); the worker was stopped."
            )
        return f"Context-Fabric cold-load safety limit triggered: {reason}"

    def run(
        self,
        *,
        path: Path,
        logical_name: str,
        features: str | list[str] | None,
        compile_budget_bytes: int,
        timeout_seconds: float,
        min_free_bytes: int,
        cancel_event: threading.Event,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> ColdCompileResult:
        path = Path(path)
        if compile_budget_bytes <= 0:
            raise ValueError("compile_budget_bytes must be > 0")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        if min_free_bytes < 0:
            raise ValueError("min_free_bytes must be >= 0")

        preflight_free = self._free_bytes(path)
        required = min_free_bytes + compile_budget_bytes
        if preflight_free < required:
            raise ColdCompileLimitError(
                "insufficient disk space before Context-Fabric cold compilation: "
                f"observed {preflight_free} bytes free, need {compile_budget_bytes} writable "
                f"bytes while preserving {min_free_bytes} bytes of configured host reserve; "
                "inspect corpus_cache_status and prune_corpus_cache before retrying",
                reason="preflight-free-space",
                observed_compiled_bytes=directory_bytes(
                    cfm_version_dir(path, self.cfm_version)
                ),
                observed_free_bytes=preflight_free,
                elapsed_seconds=0.0,
            )
        if cancel_event.is_set():
            raise ColdCompileCancelled(
                "Context-Fabric cold compilation was cancelled before worker start",
                reason="cancelled",
                observed_compiled_bytes=0,
                observed_free_bytes=preflight_free,
                elapsed_seconds=0.0,
            )

        payload = json.dumps(
            {
                "path": str(path),
                "name": logical_name,
                "features": features,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        started = self._monotonic()
        with tempfile.TemporaryDirectory(prefix="agora-cfabric-compile-") as diagnostic_root:
            diagnostic_path = Path(diagnostic_root) / "diagnostic.json"
            command = [
                sys.executable,
                "-m",
                "agora_context_fabric.compile_worker",
                "--payload",
                payload,
                "--diagnostic",
                str(diagnostic_path),
            ]
            process = self._popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            while True:
                return_code = process.poll()
                observation = self._observations(path, started)
                if progress is not None:
                    progress(dict(observation))

                compiled = int(observation["observed_compiled_bytes"])
                free = int(observation["observed_free_bytes"])
                elapsed = float(observation["elapsed_seconds"])

                reason: str | None = None
                if compiled > compile_budget_bytes:
                    reason = "compiled-output-budget"
                elif free < min_free_bytes:
                    reason = "observed-free-space"
                elif elapsed >= timeout_seconds:
                    reason = "timeout"

                if reason is not None:
                    if return_code is None:
                        self._wait_after_stop(process)
                    else:
                        process.wait()
                    raise ColdCompileLimitError(
                        self._limit_message(
                            reason,
                            compiled=compiled,
                            budget=compile_budget_bytes,
                            free=free,
                            reserve=min_free_bytes,
                            elapsed=elapsed,
                            timeout=timeout_seconds,
                        ),
                        reason=reason,
                        observed_compiled_bytes=compiled,
                        observed_free_bytes=free,
                        elapsed_seconds=elapsed,
                    )

                if return_code is not None:
                    process.wait()
                    if return_code == 0:
                        return ColdCompileResult(
                            elapsed_seconds=elapsed,
                            observed_compiled_bytes=compiled,
                            observed_free_bytes=free,
                        )
                    diagnostic = self._read_diagnostic(diagnostic_path)
                    detail = ""
                    if diagnostic:
                        kind = diagnostic.get("type")
                        message = diagnostic.get("message")
                        rendered = ": ".join(
                            str(value) for value in (kind, message) if value
                        )
                        if rendered:
                            detail = f" ({rendered})"
                    raise ColdCompileWorkerError(
                        f"contained Context-Fabric cold-load worker exited with code "
                        f"{return_code}{detail}",
                        reason="worker-error",
                        observed_compiled_bytes=compiled,
                        observed_free_bytes=free,
                        elapsed_seconds=elapsed,
                        worker_exit_code=int(return_code),
                        diagnostic=diagnostic,
                    )

                if cancel_event.is_set():
                    self._wait_after_stop(process)
                    raise ColdCompileCancelled(
                        "Context-Fabric cold compilation cancelled; worker death was confirmed",
                        reason="cancelled",
                        observed_compiled_bytes=compiled,
                        observed_free_bytes=free,
                        elapsed_seconds=elapsed,
                    )

                self._sleep(self.poll_interval)
