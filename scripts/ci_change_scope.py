"""Fail-closed classification of changed paths for risk-based CI.

Fail closed on unknown paths, symlinks, modes, mixed runtime/doc changes,
malformed raw diffs, and non-PR invocations. Exactly enumerated vetted
researcher-documentation generator/test files may use the docs fast path,
provided all changed paths qualify.
"""
from __future__ import annotations

import argparse
import re
import subprocess
from collections.abc import Iterable
from typing import Callable

SAFE_EXACT = frozenset(
    {
        "README.md",
        "CONTRIBUTING.md",
        "wiki/README.md",
        # Explicitly reviewed doc generators and documentation contracts.
        # No general scripts/ or tests/ pattern is permitted.
        "scripts/generate_plugin_docs.py",
        "scripts/generate_resource_catalog_docs.py",
        "tests/test_human_scholarly_guidance_169.py",
        "tests/test_release_front_door.py",
        "tests/test_symptom_recovery_docs_172.py",
        "tests/test_first_success_tutorials_170.py",
        "tests/test_compatibility_decisions_171.py",
        "tests/test_researcher_docs_integrity_173.py",
    }
)
RESEARCH_PLAN = re.compile(r"research/issue-[0-9]+/RESEARCH_PLAN\.md\Z")


def _safe_path(path: object) -> bool:
    if not isinstance(path, str) or not path:
        return False
    if any(ch in path for ch in ("\\", "\x00", "\n", "\r", "\t")):
        return False
    if path.startswith("/") or path.endswith("/") or "//" in path:
        return False
    if any(part in ("", ".", "..") for part in path.split("/")):
        return False
    if path in SAFE_EXACT:
        return True
    if RESEARCH_PLAN.fullmatch(path):
        return True
    if path.startswith("wiki/guides/") and path.endswith(".md"):
        return True
    return False


def classify_changed_paths(paths: Iterable[str] | None) -> str:
    """Return `docs` only when every changed file is an approved docs surface."""
    if paths is None or isinstance(paths, (str, bytes)):
        return "full"
    try:
        items = list(paths)
    except (TypeError, ValueError):
        return "full"
    if not items or not all(_safe_path(path) for path in items):
        return "full"
    return "docs"


# Only the regular, non-executable file modes may use the docs classification.
# Git's raw -z protocol is unambiguous even for tabs/newlines in paths.
_RAW_HEADER = re.compile(
    rb":(?P<old>[0-7]{6}) (?P<new>[0-7]{6}) "
    rb"[0-9a-f]{40,64} [0-9a-f]{40,64} (?P<status>[AMD])\Z"
)
_ALLOWED_MODES = frozenset((b"000000", b"100644"))


def classify_raw_git_diff(raw: bytes | None) -> str:
    """Classify a complete NUL-delimited git --raw diff, never parsed shell lines."""
    if not isinstance(raw, bytes) or not raw or not raw.endswith(b"\x00"):
        return "full"
    chunks = raw[:-1].split(b"\x00")
    if len(chunks) % 2 or not chunks or len(chunks) > 10000:
        return "full"
    paths: list[str] = []
    for i in range(0, len(chunks), 2):
        metadata, name = chunks[i : i + 2]
        match = _RAW_HEADER.fullmatch(metadata)
        if match is None or not name:
            return "full"
        old_mode, new_mode = match.group("old"), match.group("new")
        if old_mode not in _ALLOWED_MODES or new_mode not in _ALLOWED_MODES:
            return "full"
        status = match.group("status")
        if (
            (status == b"M" and (old_mode, new_mode) != (b"100644", b"100644"))
            or (status == b"A" and (old_mode, new_mode) != (b"000000", b"100644"))
            or (status == b"D" and (old_mode, new_mode) != (b"100644", b"000000"))
        ):
            return "full"
        try:
            paths.append(name.decode("utf-8", "strict"))
        except UnicodeDecodeError:
            return "full"
    return classify_changed_paths(paths)


def classify_pr_checkout(
    *, git_runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run
) -> str:
    """Observe a two-parent GitHub PR merge checkout. Failure always means full."""
    try:
        rev = git_runner(
            ["git", "rev-list", "--parents", "-n", "1", "HEAD"],
            check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20,
        )
        if rev.returncode != 0 or not isinstance(rev.stdout, bytes):
            return "full"
        parts = rev.stdout.strip().split()
        if len(parts) != 3 or any(
            re.fullmatch(rb"[0-9a-f]{40}|[0-9a-f]{64}", h) is None for h in parts
        ):
            return "full"
        diff = git_runner(
            [
                "git", "diff", "--raw", "--no-renames", "-z",
                "--abbrev=40", "--no-ext-diff", "HEAD^1", "HEAD",
            ],
            check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20,
        )
        if diff.returncode != 0:
            return "full"
        return classify_raw_git_diff(diff.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return "full"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed CI scope classification")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--git-report", action="store_true")
    mode.add_argument("--git-classify", action="store_true")
    args = parser.parse_args()
    decision = classify_pr_checkout()
    if args.git_classify:
        print(decision)
    else:
        print(f"CI change-scope observation: {decision} (report only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
