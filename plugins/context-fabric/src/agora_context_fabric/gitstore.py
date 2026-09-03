from __future__ import annotations

import os
import re
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Iterator


class GitStore:
    """Metadata-first Git cache for Text-Fabric repositories.

    Floating resources refresh from the remote default branch on every metadata
    resolution. Pinned resources fetch their configured ref. The selected commit
    is recorded under ``refs/agora/selected`` and can be surfaced to callers as
    provenance. Repository mutations are serialized with a filesystem lock.
    """

    SELECTED_REF = "refs/agora/selected"

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir).expanduser()
        self.repositories_dir = self.cache_dir / "repositories"
        self.locks_dir = self.cache_dir / "locks"

    @staticmethod
    def repository_url(repository: str) -> str:
        candidate = Path(repository).expanduser()
        if candidate.exists():
            return str(candidate.resolve())
        if "://" in repository or repository.startswith("git@") or repository.endswith(".git"):
            return repository
        if repository.count("/") == 1:
            return f"https://github.com/{repository}.git"
        return repository

    @staticmethod
    def safe_cache_key(value: str) -> str:
        key = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
        return key or "repository"

    def _run(self, *args: str, cwd: Path | None = None) -> str:
        command = ["git"]
        if cwd is not None:
            command += ["-C", str(cwd)]
        command += list(args)
        result = subprocess.run(
            command,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.stdout.strip()

    @contextmanager
    def _repository_lock(self, key: str, timeout: float = 30.0) -> Iterator[None]:
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.locks_dir / f"{self.safe_cache_key(key)}.lock"
        deadline = time.monotonic() + timeout
        fd: int | None = None
        while fd is None:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f"{os.getpid()}\n".encode("ascii"))
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"timed out waiting for Git cache lock: {lock_path}")
                time.sleep(0.05)
        try:
            yield
        finally:
            if fd is not None:
                os.close(fd)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

    def _select(self, repo: Path, ref: str | None) -> str:
        if ref:
            self._run(
                "fetch",
                "--quiet",
                "--filter=blob:none",
                "--depth",
                "1",
                "origin",
                ref,
                cwd=repo,
            )
            selected = self._run("rev-parse", "FETCH_HEAD", cwd=repo)
        else:
            self._run(
                "fetch",
                "--quiet",
                "--filter=blob:none",
                "--depth",
                "1",
                "origin",
                "HEAD",
                cwd=repo,
            )
            selected = self._run("rev-parse", "FETCH_HEAD", cwd=repo)
        self._run("update-ref", self.SELECTED_REF, selected, cwd=repo)
        return selected

    def ensure_metadata(
        self,
        repository: str,
        *,
        cache_key: str | None = None,
        ref: str | None = None,
    ) -> Path:
        self.repositories_dir.mkdir(parents=True, exist_ok=True)
        key = self.safe_cache_key(cache_key or repository)
        destination = self.repositories_dir / key
        with self._repository_lock(key):
            if not (destination / ".git").is_dir():
                source = self.repository_url(repository)
                self._run(
                    "clone",
                    "--quiet",
                    "--filter=blob:none",
                    "--no-checkout",
                    "--depth",
                    "1",
                    source,
                    str(destination),
                )
            self._select(destination, ref)
        return destination

    def selected_revision(self, repo: Path) -> str:
        return self._run("rev-parse", "--verify", self.SELECTED_REF, cwd=repo)

    def _treeish(self, repo: Path, revision: str | None = None) -> str:
        if revision:
            return revision
        try:
            self._run("rev-parse", "--verify", self.SELECTED_REF, cwd=repo)
            return self.SELECTED_REF
        except subprocess.CalledProcessError:
            return "HEAD"

    def _tree_names(self, repo: Path, revision: str | None = None) -> list[str]:
        names = self._run(
            "ls-tree", "-r", "--name-only", self._treeish(repo, revision), cwd=repo
        )
        return [name.strip().replace("\\", "/") for name in names.splitlines() if name.strip()]

    def dataset_roots(self, repo: Path, revision: str | None = None) -> list[str]:
        roots: set[str] = set()
        for normalized in self._tree_names(repo, revision):
            if normalized == "otype.tf":
                roots.add(".")
            elif normalized.endswith("/otype.tf"):
                roots.add(normalized[: -len("/otype.tf")])
        return sorted(roots)

    def feature_files(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None = None,
    ) -> list[str]:
        """Return direct `.tf` files under a repository path using Git metadata only."""
        relative = self._safe_relative_path(relative_path)
        parent = PurePosixPath("" if relative == "." else relative)
        result: list[str] = []
        for name in self._tree_names(repo, revision):
            path = PurePosixPath(name)
            if path.suffix == ".tf" and path.parent == parent:
                result.append(path.name)
        return sorted(result)

    @staticmethod
    def _safe_relative_path(relative_path: str) -> str:
        relative = relative_path.replace("\\", "/").strip("/")
        if not relative or relative == ".":
            relative = "."
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe repository-relative path: {relative_path!r}")
        return relative

    def _checkout_path(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None = None,
    ) -> Path:
        relative = self._safe_relative_path(relative_path)
        key = repo.name
        with self._repository_lock(key):
            self._run(
                "checkout",
                "--quiet",
                "--force",
                self._treeish(repo, revision),
                "--",
                relative,
                cwd=repo,
            )
        return repo if relative == "." else repo / relative

    def materialize(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None = None,
    ) -> Path:
        local = self._checkout_path(repo, relative_path, revision)
        if not (local / "otype.tf").is_file():
            raise FileNotFoundError(f"materialized path is not a Text-Fabric dataset: {relative_path}")
        return local

    def materialize_feature_module(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None = None,
    ) -> Path:
        """Materialize a module directory containing one or more TF feature files."""
        local = self._checkout_path(repo, relative_path, revision)
        if not local.is_dir() or not any(local.glob("*.tf")):
            raise FileNotFoundError(
                f"materialized path is not a Text-Fabric feature module: {relative_path}"
            )
        return local
