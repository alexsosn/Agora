#!/usr/bin/env python3
from __future__ import annotations

import difflib
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]

LOCK_PROJECTS = (
    "plugins/context-fabric",
    "plugins/sedra",
    "verification/mcp-smoke",
)

CONSTRAINT_SNAPSHOTS = (
    (
        "plugins/perseus/runtime-requirements.in",
        "plugins/perseus/runtime-constraints.txt",
    ),
    (
        "plugins/sefaria/runtime-requirements.in",
        "plugins/sefaria/runtime-constraints.txt",
    ),
)

Runner = Callable[..., Any]


def _run(
    command: Sequence[str],
    *,
    root: Path,
    runner: Runner,
) -> Any:
    return runner(
        list(command),
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )


def _failure_detail(result: Any) -> str:
    stderr = str(getattr(result, "stderr", "") or "").strip()
    stdout = str(getattr(result, "stdout", "") or "").strip()
    return stderr or stdout or f"exit code {getattr(result, 'returncode', '<unknown>')}"


def _bounded_diff(expected: Path, actual: Path, *, max_lines: int = 16) -> str:
    diff = list(
        difflib.unified_diff(
            expected.read_text(encoding="utf-8").splitlines(),
            actual.read_text(encoding="utf-8").splitlines(),
            fromfile=str(expected),
            tofile="regenerated",
            lineterm="",
        )
    )
    shown = diff[:max_lines]
    if len(diff) > max_lines:
        shown.append(f"... {len(diff) - max_lines} more diff lines")
    return "\n".join(shown)


def check_runtime_environment_freshness(
    root: Path = ROOT,
    *,
    runner: Runner = subprocess.run,
) -> list[str]:
    """Return freshness errors without modifying committed dependency snapshots."""

    root = Path(root)
    errors: list[str] = []

    for project in LOCK_PROJECTS:
        project_root = root / project
        pyproject = project_root / "pyproject.toml"
        lockfile = project_root / "uv.lock"
        if not pyproject.is_file():
            errors.append(f"{project}: missing pyproject.toml")
            continue
        if not lockfile.is_file():
            errors.append(f"{project}: missing uv.lock")
            continue
        try:
            result = _run(
                ["uv", "lock", "--check", "--project", project],
                root=root,
                runner=runner,
            )
        except OSError as exc:
            errors.append(f"{project}/uv.lock: could not execute uv: {exc}")
            continue
        if getattr(result, "returncode", 1) != 0:
            errors.append(
                f"{project}/uv.lock: stale relative to project metadata: "
                f"{_failure_detail(result)}"
            )

    with tempfile.TemporaryDirectory(prefix="agora-runtime-snapshot-") as tmp:
        temp_root = Path(tmp)
        for index, (source, snapshot) in enumerate(CONSTRAINT_SNAPSHOTS):
            source_path = root / source
            snapshot_path = root / snapshot
            if not source_path.is_file():
                errors.append(f"{source}: missing constraint source")
                continue
            if not snapshot_path.is_file():
                errors.append(f"{snapshot}: missing compiled constraint snapshot")
                continue

            regenerated = temp_root / f"constraints-{index}.txt"
            command = [
                "uv",
                "pip",
                "compile",
                "--universal",
                "--python-version",
                "3.13",
                "--no-header",
                "--no-annotate",
                source,
                "-o",
                str(regenerated),
            ]
            try:
                result = _run(command, root=root, runner=runner)
            except OSError as exc:
                errors.append(f"{snapshot}: could not execute uv: {exc}")
                continue
            if getattr(result, "returncode", 1) != 0:
                errors.append(
                    f"{snapshot}: could not regenerate from {source}: "
                    f"{_failure_detail(result)}"
                )
                continue
            if not regenerated.is_file():
                errors.append(f"{snapshot}: uv did not produce a regenerated snapshot")
                continue
            if regenerated.read_bytes() != snapshot_path.read_bytes():
                errors.append(
                    f"{snapshot}: stale relative to {source}; regenerate with the canonical uv pip compile command\n"
                    f"{_bounded_diff(snapshot_path, regenerated)}"
                )

    return errors


def main() -> int:
    errors = check_runtime_environment_freshness(ROOT)
    if errors:
        print("Runtime dependency snapshot freshness check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Runtime dependency snapshots are fresh against their canonical inputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
