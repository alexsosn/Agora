"""Conservatively skip CI collection regeneration when only corpus rows change.

This script must be executed from the PR's trusted first-parent revision in CI,
never from the untrusted PR head. No selection is possible without a two-parent
merge commit, regular-file Git changes, and valid unique-key registry YAML.
"""
from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable

import yaml

_RESOURCE_PATH = "registry/resources.yaml"
_HASH = rb"[0-9a-f]{40}|[0-9a-f]{64}"
_RAW = re.compile(
    rb":(?P<old>[0-7]{6}) (?P<new>[0-7]{6}) "
    rb"(?:" + _HASH + rb") (?:" + _HASH + rb") (?P<status>[AMD])\Z"
)
_SHA = re.compile(rb"(?:" + _HASH + rb")\Z")
_RESEARCH = re.compile(r"research/issue-[0-9]+/RESEARCH_PLAN\.md\Z")


class _UniqueSafeLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        if not isinstance(node, yaml.MappingNode):
            raise ValueError("expected YAML mapping")
        self.flatten_mapping(node)
        seen: set[str] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=True)
            if not isinstance(key, str) or key in seen or key == "<<":
                raise ValueError("duplicate, merged or nonstring YAML key")
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _collection_rows(source: str) -> list[dict]:
    if not isinstance(source, str) or not source:
        raise ValueError("missing registry")
    if any(isinstance(token, (yaml.AliasToken, yaml.AnchorToken, yaml.TagToken))
           for token in yaml.scan(source)):
        raise ValueError("YAML aliases/anchors/tags disallowed in CI scope")
    doc = yaml.load(source, Loader=_UniqueSafeLoader)
    if not isinstance(doc, dict) or set(doc) != {"schema_version", "resources"}:
        raise ValueError("unexpected registry structure")
    if type(doc["schema_version"]) is not int or doc["schema_version"] != 1:
        raise ValueError("unknown schema version")
    rows = doc["resources"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("missing resource list")
    seen: set[str] = set()
    collections = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid resource")
        rid, kind = row.get("id"), row.get("kind")
        if not isinstance(rid, str) or not rid or rid in seen:
            raise ValueError("invalid/duplicate resource ID")
        if kind not in ("collection", "corpus"):
            raise ValueError("unknown resource kind")
        seen.add(rid)
        if kind == "collection":
            collections.append(row)
    return collections


def _docs_path(path: str) -> bool:
    if not path or path.startswith("/") or path.endswith("/"):
        return False
    if any(ch in path for ch in ("\\", "\0", "\n", "\r", "\t")):
        return False
    if any(part in ("", ".", "..") for part in path.split("/")):
        return False
    return (path in ("README.md", "CONTRIBUTING.md", "wiki/README.md")
            or (path.startswith("wiki/guides/") and path.endswith(".md"))
            or _RESEARCH.fullmatch(path) is not None)


def _regular_changed_paths(raw: bytes) -> list[str] | None:
    if not isinstance(raw, bytes) or not raw or not raw.endswith(b"\0"):
        return None
    parts = raw[:-1].split(b"\0")
    if len(parts) % 2 or len(parts) > 10000:
        return None
    paths = []
    for index in range(0, len(parts), 2):
        header, filename = parts[index:index + 2]
        match = _RAW.fullmatch(header)
        if match is None or not filename:
            return None
        old, new, status = match.group("old", "new", "status")
        expected = {
            b"M": (b"100644", b"100644"),
            b"A": (b"000000", b"100644"),
            b"D": (b"100644", b"000000"),
        }
        if (old, new) != expected[status]:
            return None
        try:
            path = filename.decode("utf-8", "strict")
        except UnicodeDecodeError:
            return None
        if path in paths:
            return None
        paths.append(path)
    return paths


def classify_resource_diff(raw: bytes, before: str, after: str) -> str:
    """Return 'skip' only for unchanged ordered collection descriptors."""
    paths = _regular_changed_paths(raw)
    if paths is None or paths.count(_RESOURCE_PATH) != 1:
        return "full"
    if any(path != _RESOURCE_PATH and not _docs_path(path) for path in paths):
        return "full"
    try:
        old_collections = _collection_rows(before)
        new_collections = _collection_rows(after)
        if not old_collections or old_collections != new_collections:
            return "full"
        # Avoid declaring a no-op resource change eligible for skipping.
        if before == after:
            return "full"
    except (yaml.YAMLError, ValueError, TypeError, RecursionError):
        return "full"
    return "skip"


def classify_pr_checkout(
    *, git_runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run
) -> str:
    """Classify only a 2-parent GitHub PR merge checkout, else full."""
    def git(*args: str) -> bytes:
        proc = git_runner(["git", *args], check=False, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, timeout=20)
        if proc.returncode != 0 or not isinstance(proc.stdout, bytes):
            raise ValueError("Git command failed")
        return proc.stdout

    try:
        parents = git("rev-list", "--parents", "-n", "1", "HEAD").strip().split()
        if len(parents) != 3 or any(_SHA.fullmatch(item) is None for item in parents):
            return "full"
        raw = git("diff", "--raw", "--no-renames", "-z", "--abbrev=40",
                  "--no-ext-diff", "HEAD^1", "HEAD")
        before = git("show", "HEAD^1:registry/resources.yaml").decode("utf-8", "strict")
        after = git("show", "HEAD:registry/resources.yaml").decode("utf-8", "strict")
        return classify_resource_diff(raw, before, after)
    except (OSError, ValueError, UnicodeDecodeError, subprocess.TimeoutExpired):
        return "full"


def main() -> int:
    if os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
        print("full")
    else:
        print(classify_pr_checkout())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
