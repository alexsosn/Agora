from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterator


_NODE_SPEC_RE = re.compile(r"^\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*$")
GIB = 1024**3
DEFAULT_MIN_FREE_BYTES = 6 * GIB


class GitStore:
    """Metadata-first Git cache with immutable revision-addressed TF snapshots.

    Persistent repositories contain Git metadata only. Corpus and feature-module
    bytes are exported from an exact resolved commit into immutable snapshot
    directories. Snapshot reclamation is intentionally deferred to the separate
    cross-process eviction work.
    """

    SELECTED_REF = "refs/agora/selected"
    FORBIDDEN_FEATURE_MODULE_FILES = frozenset({"otype.tf", "oslots.tf", "otext.tf"})

    def __init__(
        self,
        cache_dir: Path,
        *,
        min_free_bytes: int | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir).expanduser().resolve()
        self.repositories_dir = self.cache_dir / "repositories"
        self.snapshots_dir = self.cache_dir / "snapshots"
        self.tmp_dir = self.cache_dir / "tmp"
        self.locks_dir = self.cache_dir / "locks"
        self.min_free_bytes = (
            min_free_bytes
            if min_free_bytes is not None
            else self._env_gib("AGORA_CORPUS_MIN_FREE_GB", DEFAULT_MIN_FREE_BYTES)
        )
        if self.min_free_bytes < 0:
            raise ValueError("min_free_bytes must be >= 0")
        self._ensure_layout()

    @staticmethod
    def _env_gib(name: str, default_bytes: int) -> int:
        raw = os.environ.get(name)
        if raw is None:
            return default_bytes
        try:
            value = float(raw)
        except ValueError as exc:
            raise ValueError(f"{name} must be a number of GiB") from exc
        if value < 0:
            raise ValueError(f"{name} must be >= 0")
        return int(value * GIB)

    def _ensure_layout(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.repositories_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.locks_dir.mkdir(parents=True, exist_ok=True)

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

    def _resolved_revision(self, repo: Path, revision: str | None = None) -> str:
        return self._run(
            "rev-parse",
            "--verify",
            f"{self._treeish(repo, revision)}^{{commit}}",
            cwd=repo,
        )

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

    @classmethod
    def _validate_feature_module_files(
        cls,
        files: list[str],
        relative_path: str,
    ) -> None:
        forbidden = sorted(set(files) & cls.FORBIDDEN_FEATURE_MODULE_FILES)
        if forbidden:
            raise ValueError(
                f"Text-Fabric feature module {relative_path!r} contains parent warp file(s): "
                f"{', '.join(forbidden)}"
            )

    def feature_files(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None = None,
    ) -> list[str]:
        """Return direct non-warp `.tf` files under a feature-module path."""
        relative = self._safe_relative_path(relative_path)
        parent = PurePosixPath("" if relative == "." else relative)
        result: list[str] = []
        for name in self._tree_names(repo, revision):
            path = PurePosixPath(name)
            if path.suffix == ".tf" and path.parent == parent:
                result.append(path.name)
        result = sorted(result)
        self._validate_feature_module_files(result, relative_path)
        return result

    @staticmethod
    def _safe_relative_path(relative_path: str) -> str:
        relative = relative_path.replace("\\", "/").strip("/")
        if not relative or relative == ".":
            relative = "."
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe repository-relative path: {relative_path!r}")
        return relative

    @staticmethod
    def _node_spec_max(value: str) -> int | None:
        value = value.strip()
        if not _NODE_SPEC_RE.fullmatch(value):
            return None
        maximum = 0
        for part in value.split(","):
            if "-" in part:
                start, end = part.split("-", 1)
                maximum = max(maximum, int(start), int(end))
            else:
                maximum = max(maximum, int(part))
        return maximum

    def _git_show_lines(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None = None,
    ) -> Iterator[str]:
        relative = self._safe_relative_path(relative_path)
        treeish = self._treeish(repo, revision)
        spec = f"{treeish}:{relative}"
        process = subprocess.Popen(
            ["git", "-C", str(repo), "show", spec],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert process.stdout is not None
        try:
            for line in process.stdout:
                yield line.rstrip("\r\n")
        finally:
            process.stdout.close()
            stderr = process.stderr.read() if process.stderr is not None else ""
            returncode = process.wait()
            if process.stderr is not None:
                process.stderr.close()
            if returncode:
                raise subprocess.CalledProcessError(
                    returncode,
                    ["git", "show", spec],
                    stderr=stderr,
                )

    def tf_feature_summary(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None = None,
    ) -> dict[str, Any]:
        """Stream a TF file and summarize compatibility-relevant metadata and node bounds."""
        kind: str | None = None
        metadata: dict[str, Any] = {}
        in_header = True
        implicit_node: int | None = None
        max_node = 0

        for line in self._git_show_lines(repo, relative_path, revision):
            if in_header:
                if not line:
                    in_header = False
                    continue
                if line == "@node":
                    kind = "node"
                elif line == "@edge":
                    kind = "edge"
                elif line == "@config":
                    kind = "config"
                elif line == "@edgeValues":
                    metadata["edgeValues"] = True
                elif line.startswith("@") and "=" in line:
                    key, value = line[1:].split("=", 1)
                    metadata[key] = value
                continue

            if not line or kind == "config":
                continue

            fields = line.split("\t")
            if kind == "node":
                explicit = self._node_spec_max(fields[0]) if len(fields) > 1 else None
                if explicit is None:
                    implicit_node = 1 if implicit_node is None else implicit_node + 1
                    max_node = max(max_node, implicit_node)
                else:
                    implicit_node = explicit
                    max_node = max(max_node, explicit)
                continue

            if kind == "edge":
                edge_values = bool(metadata.get("edgeValues"))
                source_spec: str | None
                target_spec: str
                if edge_values:
                    if len(fields) >= 3:
                        source_spec, target_spec = fields[0], fields[1]
                    else:
                        source_spec, target_spec = None, fields[0]
                else:
                    if len(fields) >= 2:
                        source_spec, target_spec = fields[0], fields[1]
                    else:
                        source_spec, target_spec = None, fields[0]

                source_max = self._node_spec_max(source_spec) if source_spec else None
                if source_max is None:
                    implicit_node = 1 if implicit_node is None else implicit_node + 1
                    source_max = implicit_node
                else:
                    implicit_node = source_max
                target_max = self._node_spec_max(target_spec)
                if target_max is None:
                    raise ValueError(
                        f"invalid Text-Fabric edge target node spec in {relative_path!r}: {target_spec!r}"
                    )
                max_node = max(max_node, source_max, target_max)

        if kind is None:
            raise ValueError(f"Text-Fabric file {relative_path!r} has no @node, @edge, or @config header")
        return {
            "kind": kind,
            "metadata": metadata,
            "max_node": max_node,
        }

    def _blob_sha(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None = None,
    ) -> str | None:
        relative = self._safe_relative_path(relative_path)
        output = self._run(
            "ls-tree",
            self._treeish(repo, revision),
            "--",
            relative,
            cwd=repo,
        )
        if not output:
            return None
        first = output.splitlines()[0]
        metadata, _, returned_path = first.partition("\t")
        parts = metadata.split()
        if len(parts) < 3 or returned_path != relative:
            return None
        return parts[2]

    def dataset_warp_fingerprint(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None = None,
    ) -> str:
        """Fingerprint parent-owned warp blobs without materializing the dataset."""
        relative = self._safe_relative_path(relative_path)
        prefix = "" if relative == "." else f"{relative}/"
        entries: list[str] = []
        for filename in ("otype.tf", "oslots.tf", "otext.tf"):
            path = f"{prefix}{filename}"
            sha = self._blob_sha(repo, path, revision)
            if sha is not None:
                entries.append(f"{filename}:{sha}")
        required = {entry.split(":", 1)[0] for entry in entries}
        if not {"otype.tf", "oslots.tf"}.issubset(required):
            raise ValueError(f"Text-Fabric dataset {relative_path!r} has incomplete warp files")
        digest = hashlib.sha256("\n".join(entries).encode("ascii")).hexdigest()
        return f"sha256:{digest}"

    def _free_bytes(self) -> int:
        return shutil.disk_usage(self.cache_dir).free

    def _ensure_free_reserve(self, required_bytes: int = 0) -> None:
        if required_bytes < 0:
            raise ValueError("required_bytes must be >= 0")
        free_bytes = self._free_bytes()
        if free_bytes < self.min_free_bytes + required_bytes:
            raise OSError(
                "insufficient disk space for corpus materialization: "
                f"{free_bytes} bytes free, need {required_bytes} writable bytes while preserving "
                f"the configured reserve of {self.min_free_bytes} bytes"
            )

    @staticmethod
    def _validate_archive_member(member: tarfile.TarInfo) -> None:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe path in Git archive: {member.name!r}")
        if not (member.isdir() or member.isfile()):
            raise ValueError(f"unsupported entry in Git archive: {member.name!r}")

    @staticmethod
    def _disable_archive_transformations(export_repo: Path) -> None:
        """Make `git archive` preserve tracked bytes despite export attributes."""
        info_dir = export_repo / ".git" / "info"
        info_dir.mkdir(parents=True, exist_ok=True)
        (info_dir / "attributes").write_text(
            "* -export-ignore -export-subst\n",
            encoding="utf-8",
        )

    @staticmethod
    def _raise_archive_process_error(
        process: subprocess.Popen[bytes],
        command: list[str],
        stderr_path: Path,
        cause: BaseException | None = None,
    ) -> None:
        if process.stdout is not None and not process.stdout.closed:
            process.stdout.close()
        return_code = process.wait()
        if return_code:
            stderr = stderr_path.read_bytes()
            error = subprocess.CalledProcessError(return_code, command, stderr=stderr)
            if cause is None:
                raise error
            raise error from cause
        if cause is not None:
            raise cause

    def _snapshot_destination(
        self,
        repo: Path,
        revision: str,
        relative: str,
        *,
        kind: str,
    ) -> Path:
        root = self.snapshots_dir / repo.name / revision / kind
        return root / ("__root__" if relative == "." else Path(relative))

    def _export_snapshot(
        self,
        repo: Path,
        revision: str,
        relative: str,
        destination: Path,
        validate: Callable[[Path], None],
    ) -> None:
        self._ensure_free_reserve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_root = Path(tempfile.mkdtemp(prefix="snapshot-", dir=self.tmp_dir))
        export_repo = temp_root / "export"
        extracted = temp_root / "data"
        stderr_path = temp_root / "archive.stderr"
        extracted.mkdir()
        process: subprocess.Popen[bytes] | None = None
        try:
            source = self._run("remote", "get-url", "origin", cwd=repo)
            self._run("init", "-q", str(export_repo))
            self._disable_archive_transformations(export_repo)
            self._run("remote", "add", "origin", source, cwd=export_repo)
            self._ensure_free_reserve()
            self._run(
                "fetch",
                "--quiet",
                "--no-tags",
                "--filter=blob:none",
                "--depth",
                "1",
                "origin",
                revision,
                cwd=export_repo,
            )
            self._ensure_free_reserve()
            export_revision = self._run("rev-parse", "FETCH_HEAD", cwd=export_repo)

            command = ["git", "-C", str(export_repo), "archive", "--format=tar", export_revision]
            if relative != ".":
                command += ["--", relative]
            with stderr_path.open("wb") as stderr_file:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=stderr_file,
                )
                assert process.stdout is not None
                try:
                    with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
                        for member in archive:
                            self._validate_archive_member(member)
                            required_bytes = member.size if member.isfile() else 0
                            self._ensure_free_reserve(required_bytes)
                            archive.extract(member, extracted, filter="fully_trusted")
                            self._ensure_free_reserve()
                except tarfile.ReadError as exc:
                    self._raise_archive_process_error(process, command, stderr_path, exc)
                self._raise_archive_process_error(process, command, stderr_path)

            exported = extracted if relative == "." else extracted / Path(relative)
            validate(exported)
            try:
                os.replace(exported, destination)
            except FileExistsError:
                validate(destination)
        finally:
            if process is not None:
                if process.stdout is not None and not process.stdout.closed:
                    process.stdout.close()
                if process.poll() is None:
                    process.kill()
                    process.wait()
            shutil.rmtree(temp_root, ignore_errors=True)

    @staticmethod
    def _validate_corpus_snapshot(path: Path) -> None:
        if not (path / "otype.tf").is_file():
            raise FileNotFoundError(f"materialized path is not a Text-Fabric dataset: {path}")

    @classmethod
    def _validate_module_snapshot(cls, path: Path, files: tuple[str, ...]) -> None:
        present = sorted(candidate.name for candidate in path.glob("*.tf"))
        cls._validate_feature_module_files(present, str(path))
        missing = [name for name in files if not (path / name).is_file()]
        if missing:
            raise FileNotFoundError(
                f"materialized Text-Fabric feature module is missing: {', '.join(missing)}"
            )

    def _materialize_snapshot(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None,
        *,
        kind: str,
        validate: Callable[[Path], None],
    ) -> Path:
        relative = self._safe_relative_path(relative_path)
        resolved_revision = self._resolved_revision(repo, revision)
        destination = self._snapshot_destination(
            repo,
            resolved_revision,
            relative,
            kind=kind,
        )
        try:
            validate(destination)
            return destination
        except FileNotFoundError:
            pass

        with self._repository_lock(repo.name):
            try:
                validate(destination)
            except FileNotFoundError:
                self._export_snapshot(
                    repo,
                    resolved_revision,
                    relative,
                    destination,
                    validate,
                )

        validate(destination)
        return destination

    def materialize(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None = None,
    ) -> Path:
        return self._materialize_snapshot(
            repo,
            relative_path,
            revision,
            kind="corpora",
            validate=self._validate_corpus_snapshot,
        )

    def materialize_feature_module(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None = None,
    ) -> Path:
        """Materialize an immutable module snapshot containing non-warp TF features."""
        files = tuple(self.feature_files(repo, relative_path, revision))
        if not files:
            raise FileNotFoundError(
                f"materialized path is not a Text-Fabric feature module: {relative_path}"
            )
        return self._materialize_snapshot(
            repo,
            relative_path,
            revision,
            kind="feature-modules",
            validate=lambda path: self._validate_module_snapshot(path, files),
        )
