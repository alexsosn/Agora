from __future__ import annotations

import re
import subprocess
from pathlib import Path


class GitStore:
    """Metadata-first Git cache for Text-Fabric repositories.

    Repositories are cloned with no working-tree checkout. Dataset paths are
    discovered from Git tree metadata; blobs for a selected dataset are fetched
    only when that path is materialized.
    """

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir).expanduser()
        self.repositories_dir = self.cache_dir / "repositories"

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

    def ensure_metadata(self, repository: str, *, cache_key: str | None = None) -> Path:
        self.repositories_dir.mkdir(parents=True, exist_ok=True)
        key = self.safe_cache_key(cache_key or repository)
        destination = self.repositories_dir / key
        if (destination / ".git").is_dir():
            return destination

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
        return destination

    def dataset_roots(self, repo: Path) -> list[str]:
        names = self._run("ls-tree", "-r", "--name-only", "HEAD", cwd=repo)
        roots: set[str] = set()
        for name in names.splitlines():
            normalized = name.strip().replace("\\", "/")
            if normalized == "otype.tf":
                roots.add(".")
            elif normalized.endswith("/otype.tf"):
                roots.add(normalized[: -len("/otype.tf")])
        return sorted(roots)

    def materialize(self, repo: Path, relative_path: str) -> Path:
        relative = relative_path.replace("\\", "/").strip("/")
        if not relative or relative == ".":
            relative = "."
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe repository-relative path: {relative_path!r}")

        self._run("checkout", "--quiet", "HEAD", "--", relative, cwd=repo)
        local = repo if relative == "." else repo / relative
        if not (local / "otype.tf").is_file():
            raise FileNotFoundError(f"materialized path is not a Text-Fabric dataset: {relative_path}")
        return local
