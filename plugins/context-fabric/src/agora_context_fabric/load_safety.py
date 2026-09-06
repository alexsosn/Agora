from __future__ import annotations

import math
import os
from pathlib import Path

MIB = 1024**2
GIB = 1024**3
DEFAULT_COMPILE_MULTIPLIER = 16.0
DEFAULT_COMPILE_MIN_GB = 0.25
DEFAULT_COMPILE_MAX_MINUTES = 60.0


def _positive_number(value: float | int, *, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return number


def _positive_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return _positive_number(float(raw), name=name)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive finite number") from exc


def source_tf_bytes(path: Path) -> int:
    """Return bytes in direct Text-Fabric source files compiled from ``path``.

    Context-Fabric's cold compile reads the direct ``*.tf`` files in the selected
    dataset directory. Repository metadata, nested directories and unrelated
    files therefore must not inflate or deflate the compile budget.
    """

    root = Path(path)
    total = 0
    for candidate in root.glob("*.tf"):
        try:
            if candidate.is_file() and not candidate.is_symlink():
                total += candidate.stat().st_size
        except FileNotFoundError:
            # A managed cache lease should make this rare, but a concurrent
            # filesystem mutation must not turn accounting into an incorrect
            # negative or partially reused value.
            continue
    return total


def compile_budget_bytes(source_bytes: int, *, max_compile_gb: float | None = None) -> int:
    """Return the observed compiled-output budget for one cold load."""

    if source_bytes < 0:
        raise ValueError("source_bytes must be >= 0")
    if max_compile_gb is not None:
        return int(_positive_number(max_compile_gb, name="max_compile_gb") * GIB)

    multiplier = _positive_env(
        "AGORA_CORPUS_COMPILE_MAX_MULTIPLIER",
        DEFAULT_COMPILE_MULTIPLIER,
    )
    minimum_gb = _positive_env(
        "AGORA_CORPUS_COMPILE_MIN_GB",
        DEFAULT_COMPILE_MIN_GB,
    )
    return max(int(minimum_gb * GIB), int(source_bytes * multiplier))


def compile_timeout_seconds(*, max_compile_minutes: float | None = None) -> float:
    """Return the wall-clock limit for one contained cold compile."""

    minutes = (
        _positive_number(max_compile_minutes, name="max_compile_minutes")
        if max_compile_minutes is not None
        else _positive_env(
            "AGORA_CORPUS_COMPILE_MAX_MINUTES",
            DEFAULT_COMPILE_MAX_MINUTES,
        )
    )
    return minutes * 60.0


def _validated_cfm_version(version: str) -> str:
    value = str(version)
    if not value or value in {".", ".."} or Path(value).name != value:
        raise ValueError(f"invalid Context-Fabric CFM version: {version!r}")
    return value


def cfm_version_dir(path: Path, version: str) -> Path:
    return Path(path) / ".cfm" / _validated_cfm_version(version)


def cfm_marker(path: Path, version: str) -> Path:
    return cfm_version_dir(path, version) / "meta.json"


def current_cfm_version() -> str:
    """Read the storage-format version from the installed Context-Fabric runtime."""

    from cfabric.core.config import CFM_VERSION

    return _validated_cfm_version(str(CFM_VERSION))


def directory_bytes(path: Path) -> int:
    """Best-effort byte count of regular files below ``path``."""

    root = Path(path)
    total = 0
    if not root.exists():
        return 0
    for candidate in root.rglob("*"):
        try:
            if candidate.is_file() and not candidate.is_symlink():
                total += candidate.stat().st_size
        except FileNotFoundError:
            continue
    return total
