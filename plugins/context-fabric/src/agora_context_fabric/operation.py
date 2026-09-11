from __future__ import annotations

import math
import os
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

DEFAULT_ACQUISITION_MAX_MINUTES = 15.0


class OperationCancelled(RuntimeError):
    """Raised when an Agora-owned long operation is cooperatively cancelled."""


class AcquisitionTimeout(TimeoutError):
    """Raised when source acquisition/materialization exceeds its wall-clock budget."""


def _positive_number(value: float | int, *, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return number


def acquisition_timeout_seconds(*, max_acquire_minutes: float | None = None) -> float:
    """Return the wall-clock budget for source acquisition/materialization.

    This is intentionally independent from cold-compile time limits: Git/source
    acquisition can hang before an active Text-Fabric compile exists, and should
    not inherit the much larger compile budget.
    """

    if max_acquire_minutes is not None:
        minutes = _positive_number(max_acquire_minutes, name="max_acquire_minutes")
    else:
        raw = os.environ.get("AGORA_CORPUS_ACQUISITION_MAX_MINUTES")
        if raw is None:
            minutes = DEFAULT_ACQUISITION_MAX_MINUTES
        else:
            try:
                minutes = _positive_number(
                    float(raw),
                    name="AGORA_CORPUS_ACQUISITION_MAX_MINUTES",
                )
            except ValueError as exc:
                raise ValueError(
                    "AGORA_CORPUS_ACQUISITION_MAX_MINUTES must be a positive finite number"
                ) from exc
    return minutes * 60.0


@dataclass
class OperationControl:
    """Process-local control for one prepare/load request.

    The same cancellation event can be shared with the contained cold compiler.
    Git/source acquisition observes ``acquisition_deadline`` through the
    operation ContextVar, while stage callbacks remain transport-neutral.
    """

    acquisition_timeout_seconds: float = field(default_factory=acquisition_timeout_seconds)
    on_stage: Callable[[str], None] | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    started_monotonic: float = field(default_factory=time.monotonic)
    current_stage: str | None = None
    _stage_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        self.acquisition_timeout_seconds = _positive_number(
            self.acquisition_timeout_seconds,
            name="acquisition_timeout_seconds",
        )

    @property
    def acquisition_deadline(self) -> float:
        return self.started_monotonic + self.acquisition_timeout_seconds

    @property
    def cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def cancel(self) -> None:
        self.cancel_event.set()

    def stage(self, name: str) -> None:
        stage = str(name).strip()
        if not stage:
            raise ValueError("operation stage must be non-empty")
        with self._stage_lock:
            self.current_stage = stage
        if self.on_stage is not None:
            self.on_stage(stage)

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            stage = self.current_stage or "unknown"
            raise OperationCancelled(
                "Context-Fabric operation cancelled during "
                f"{stage}; Agora waited for owned work to stop before returning"
            )

    def remaining_acquisition_seconds(self) -> float:
        self.raise_if_cancelled()
        remaining = self.acquisition_deadline - time.monotonic()
        if remaining <= 0:
            stage = self.current_stage or "acquiring/materializing"
            raise AcquisitionTimeout(
                "Context-Fabric acquisition/materialization exceeded the configured "
                f"{self.acquisition_timeout_seconds:.3f}-second limit during {stage}; "
                "inspect network/cache state before retrying"
            )
        return remaining


_CURRENT_OPERATION: ContextVar[OperationControl | None] = ContextVar(
    "agora_context_fabric_operation",
    default=None,
)


def current_operation() -> OperationControl | None:
    return _CURRENT_OPERATION.get()


@contextmanager
def operation_scope(operation: OperationControl | None) -> Iterator[OperationControl | None]:
    if operation is None:
        yield None
        return
    token = _CURRENT_OPERATION.set(operation)
    try:
        yield operation
    finally:
        _CURRENT_OPERATION.reset(token)


@contextmanager
def watch_subprocess(process: Any) -> Iterator[None]:
    """Kill a streaming Git subprocess if the current operation expires/cancels.

    Ordinary subprocess calls can poll directly. Streaming reads may block on a
    pipe, so a tiny watchdog is required to make the same operation deadline
    observable without platform-specific nonblocking pipe code.
    """

    operation = current_operation()
    if operation is None:
        yield
        return

    stopped = threading.Event()
    failures: list[BaseException] = []

    def monitor() -> None:
        while not stopped.wait(0.02):
            try:
                operation.remaining_acquisition_seconds()
            except BaseException as exc:
                failures.append(exc)
                try:
                    process.kill()
                except (OSError, ProcessLookupError):
                    pass
                return

    watcher = threading.Thread(
        target=monitor,
        name="agora-cfabric-git-watchdog",
        daemon=True,
    )
    watcher.start()
    try:
        yield
    finally:
        stopped.set()
        watcher.join(0.25)
        if failures:
            raise failures[0]
