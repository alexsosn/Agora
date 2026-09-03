from __future__ import annotations

import hashlib
import json
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

import portalocker


_NODE_SPEC_RE = re.compile(r"^\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*$")
GIB = 1024**3
DEFAULT_SNAPSHOT_SOFT_LIMIT_BYTES = 3 * GIB
DEFAULT_MIN_FREE_BYTES = 6 * GIB
_ABANDONED_EVICTION_GRACE_SECONDS = 300


class CacheLease:
    """Process-backed shared lease for one managed cache object."""

    def __init__(self, path: Path, lock: portalocker.Lock):
        self.path = path
        self._lock = lock
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        self._lock.release()
        self._released = True

    def __enter__(self) -> "CacheLease":
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.release()

    def __del__(self) -> None:
        try:
            self.release()
        except Exception:
            pass


class GitStore:
    """Metadata-first Git cache with revision-addressed TF source snapshots.

    Persistent repositories contain Git metadata only. Corpus and feature-module
    bytes are exported from exact commits into source/provenance snapshots.
    Composed overlays are Agora-derived cache objects. All three object kinds use
    the same cross-process lease/eviction protocol.
    """

    SELECTED_REF = "refs/agora/selected"
    FORBIDDEN_FEATURE_MODULE_FILES = frozenset({"otype.tf", "oslots.tf", "otext.tf"})

    def __init__(
        self,
        cache_dir: Path,
        *,
        snapshot_soft_limit_bytes: int | None = None,
        min_free_bytes: int | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir).expanduser().resolve()
        self.repositories_dir = self.cache_dir / "repositories"
        self.snapshots_dir = self.cache_dir / "snapshots"
        self.overlays_dir = self.cache_dir / "overlays"
        self.tmp_dir = self.cache_dir / "tmp"
        self.locks_dir = self.cache_dir / "locks"
        self.object_locks_dir = self.locks_dir / "cache-objects"
        self.access_dir = self.cache_dir / "access"
        self.object_meta_dir = self.cache_dir / "object-meta"
        self.cache_transition_lock = self.locks_dir / "cache-transition.lock"
        self.snapshot_soft_limit_bytes = (
            snapshot_soft_limit_bytes
            if snapshot_soft_limit_bytes is not None
            else self._env_gib("AGORA_CORPUS_CACHE_MAX_GB", DEFAULT_SNAPSHOT_SOFT_LIMIT_BYTES)
        )
        self.min_free_bytes = (
            min_free_bytes
            if min_free_bytes is not None
            else self._env_gib("AGORA_CORPUS_MIN_FREE_GB", DEFAULT_MIN_FREE_BYTES)
        )
        if self.snapshot_soft_limit_bytes < 0:
            raise ValueError("snapshot_soft_limit_bytes must be >= 0")
        if self.min_free_bytes < 0:
            raise ValueError("min_free_bytes must be >= 0")
        self._ensure_layout()
        self._cleanup_abandoned_evictions()

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
        for path in (
            self.cache_dir,
            self.repositories_dir,
            self.snapshots_dir,
            self.overlays_dir,
            self.tmp_dir,
            self.locks_dir,
            self.object_locks_dir,
            self.access_dir,
            self.object_meta_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _cleanup_abandoned_evictions(self) -> None:
        """Best-effort cleanup for detached trees left behind by process death.

        A grace period keeps a newly created GitStore from racing a live process
        that has just detached a tree and is deleting it outside the transition
        lock. Detached trees are never served, so cleanup needs no cache lease.
        """
        cutoff = time.time() - _ABANDONED_EVICTION_GRACE_SECONDS
        for candidate in self.tmp_dir.glob("evict-*"):
            try:
                if candidate.stat().st_mtime <= cutoff:
                    shutil.rmtree(candidate, ignore_errors=True)
            except FileNotFoundError:
                continue

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

    @staticmethod
    def _portalocker_flags(shared: bool) -> portalocker.LockFlags:
        mode = portalocker.LockFlags.SHARED if shared else portalocker.LockFlags.EXCLUSIVE
        return mode | portalocker.LockFlags.NON_BLOCKING

    @classmethod
    def _new_file_lock(
        cls,
        path: Path,
        *,
        shared: bool,
        timeout: float,
    ) -> portalocker.Lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        return portalocker.Lock(
            str(path),
            mode="a",
            timeout=timeout,
            check_interval=0.05,
            flags=cls._portalocker_flags(shared),
        )

    @classmethod
    def _acquire_file_lock(
        cls,
        path: Path,
        *,
        shared: bool,
        timeout: float,
        description: str,
    ) -> portalocker.Lock:
        lock = cls._new_file_lock(path, shared=shared, timeout=timeout)
        try:
            lock.acquire()
        except portalocker.exceptions.LockException as exc:
            try:
                lock.release()
            except Exception:
                pass
            raise TimeoutError(f"timed out waiting for {description}: {path}") from exc
        return lock

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
        """Serialize repository mutation with an OS-backed crash-safe lock."""
        lock_path = self.locks_dir / f"repository-{self.safe_cache_key(key)}.lock"
        lock = self._acquire_file_lock(
            lock_path,
            shared=False,
            timeout=timeout,
            description="Git cache lock",
        )
        try:
            yield
        finally:
            lock.release()

    @contextmanager
    def cache_transition(
        self,
        *,
        exclusive: bool = False,
        timeout: float = 30.0,
    ) -> Iterator[None]:
        """Coordinate prepare/composition->lease transitions with cache detachment."""
        lock = self._acquire_file_lock(
            self.cache_transition_lock,
            shared=not exclusive,
            timeout=timeout,
            description="Context-Fabric cache transition lock",
        )
        try:
            yield
        finally:
            lock.release()

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
    def _validate_feature_module_files(cls, files: list[str], relative_path: str) -> None:
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
        return {"kind": kind, "metadata": metadata, "max_node": max_node}

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
                f"the configured reserve of {self.min_free_bytes} bytes; inspect corpus_cache_status "
                "and run prune_corpus_cache to reclaim unused cache objects"
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
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=stderr_file)
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
        destination = self._snapshot_destination(repo, resolved_revision, relative, kind=kind)
        with self.cache_transition():
            try:
                validate(destination)
                self.touch_cache_object(destination)
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
            self.touch_cache_object(destination)
            return destination

    @staticmethod
    def _directory_size(path: Path) -> int:
        total = 0
        for root, _dirs, files in os.walk(path):
            for filename in files:
                candidate = Path(root) / filename
                try:
                    if not candidate.is_symlink():
                        total += candidate.stat().st_size
                except FileNotFoundError:
                    continue
        return total

    def _managed_path(self, path: Path) -> Path:
        candidate = Path(path).expanduser().resolve()
        if candidate.is_relative_to(self.snapshots_dir) or candidate.is_relative_to(self.overlays_dir):
            return candidate
        raise ValueError(f"path is outside the managed Context-Fabric cache: {candidate}")

    def _cache_identity(self, path: Path) -> dict[str, Any] | None:
        candidate = self._managed_path(path)
        if candidate.is_relative_to(self.snapshots_dir):
            relative = candidate.relative_to(self.snapshots_dir)
            if len(relative.parts) < 4:
                return None
            resource_id, revision, namespace = relative.parts[:3]
            remaining = relative.parts[3:]
            if namespace not in {"corpora", "feature-modules"}:
                return None
            relative_path = "." if remaining == ("__root__",) else PurePosixPath(*remaining).as_posix()
            return {
                "kind": "corpus-snapshot" if namespace == "corpora" else "feature-module-snapshot",
                "resource_id": resource_id,
                "revision": revision,
                "relative_path": relative_path,
                "legacy": False,
            }

        relative = candidate.relative_to(self.overlays_dir)
        if len(relative.parts) >= 3:
            return {
                "kind": "overlay",
                "resource_id": relative.parts[0],
                "revision": relative.parts[1],
                "relative_path": None,
                "legacy": False,
            }
        if len(relative.parts) == 1:
            return {
                "kind": "overlay",
                "resource_id": None,
                "revision": None,
                "relative_path": None,
                "legacy": True,
            }
        return None

    def _object_id(self, path: Path) -> str:
        candidate = self._managed_path(path)
        relative = candidate.relative_to(self.cache_dir).as_posix()
        return hashlib.sha256(relative.encode("utf-8")).hexdigest()

    def _object_lock_path(self, path: Path) -> Path:
        return self.object_locks_dir / f"{self._object_id(path)}.lock"

    def _access_path(self, path: Path) -> Path:
        return self.access_dir / f"{self._object_id(path)}.stamp"

    def _meta_path(self, path: Path) -> Path:
        return self.object_meta_dir / f"{self._object_id(path)}.json"

    def touch_cache_object(self, path: Path) -> None:
        candidate = self._managed_path(path)
        identity = self._cache_identity(candidate)
        if identity is None:
            raise ValueError(f"unrecognized Context-Fabric cache object: {candidate}")
        if not candidate.is_dir():
            raise FileNotFoundError(f"cache object does not exist: {candidate}")
        stamp = self._access_path(candidate)
        stamp.touch(exist_ok=True)
        os.utime(stamp, None)
        metadata = {
            "path": candidate.relative_to(self.cache_dir).as_posix(),
            **identity,
        }
        meta_path = self._meta_path(candidate)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.object_meta_dir,
                prefix=f".{meta_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                json.dump(metadata, handle, sort_keys=True)
                temp_path = Path(handle.name)
            os.replace(temp_path, meta_path)
            temp_path = None
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass

    def _validate_cache_object(self, path: Path) -> None:
        identity = self._cache_identity(path)
        if identity is None:
            raise ValueError(f"unrecognized Context-Fabric cache object: {path}")
        kind = identity["kind"]
        if kind in {"corpus-snapshot", "overlay"}:
            if not (path / "otype.tf").is_file():
                raise FileNotFoundError(f"managed Context-Fabric cache object is incomplete: {path}")
            return
        files = sorted(candidate.name for candidate in path.glob("*.tf"))
        self._validate_feature_module_files(files, str(path))
        if not files:
            raise FileNotFoundError(f"managed feature-module cache object is empty: {path}")

    def _acquire_cache_lease_locked(self, path: Path, *, timeout: float) -> CacheLease:
        candidate = self._managed_path(path)
        lock = self._acquire_file_lock(
            self._object_lock_path(candidate),
            shared=True,
            timeout=timeout,
            description="Context-Fabric cache-object lease",
        )
        try:
            self._validate_cache_object(candidate)
            self.touch_cache_object(candidate)
        except Exception:
            lock.release()
            raise
        return CacheLease(candidate, lock)

    def acquire_cache_lease(
        self,
        path: Path,
        *,
        timeout: float = 30.0,
        transition_held: bool = False,
    ) -> CacheLease:
        if transition_held:
            return self._acquire_cache_lease_locked(path, timeout=timeout)
        with self.cache_transition(timeout=timeout):
            return self._acquire_cache_lease_locked(path, timeout=timeout)

    def _try_object_exclusive_lock(self, path: Path) -> portalocker.Lock | None:
        lock = self._new_file_lock(self._object_lock_path(path), shared=False, timeout=0)
        try:
            lock.acquire()
        except portalocker.exceptions.LockException:
            try:
                lock.release()
            except Exception:
                pass
            return None
        return lock

    def is_cache_object_in_use(self, path: Path) -> bool:
        lock = self._try_object_exclusive_lock(path)
        if lock is None:
            return True
        lock.release()
        return False

    def _discover_cache_paths(self) -> set[Path]:
        paths: set[Path] = set()
        for meta_path in self.object_meta_dir.glob("*.json"):
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                candidate = (self.cache_dir / str(data["path"])).resolve()
                if candidate.exists():
                    self._managed_path(candidate)
                    paths.add(candidate)
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                continue

        if self.snapshots_dir.exists():
            for otype in self.snapshots_dir.glob("*/*/corpora/**/otype.tf"):
                paths.add(otype.parent.resolve())
            for feature in self.snapshots_dir.glob("*/*/feature-modules/**/*.tf"):
                paths.add(feature.parent.resolve())

        if self.overlays_dir.exists():
            for otype in self.overlays_dir.glob("*/*/*/otype.tf"):
                paths.add(otype.parent.resolve())
            for child in self.overlays_dir.iterdir():
                if child.is_dir() and (child / "otype.tf").is_file():
                    paths.add(child.resolve())
        return paths

    def cache_entries(self, resource_id: str | None = None) -> list[dict[str, Any]]:
        requested = self.safe_cache_key(resource_id) if resource_id is not None else None
        entries: list[dict[str, Any]] = []
        for path in self._discover_cache_paths():
            identity = self._cache_identity(path)
            if identity is None:
                continue
            if requested is not None and identity["resource_id"] != requested:
                continue
            try:
                self._validate_cache_object(path)
                size = self._directory_size(path)
                stat = path.stat()
            except (FileNotFoundError, ValueError):
                continue
            stamp = self._access_path(path)
            try:
                last_accessed = stamp.stat().st_mtime
            except FileNotFoundError:
                last_accessed = stat.st_mtime
            entries.append(
                {
                    **identity,
                    "path": str(path),
                    "size_bytes": size,
                    "last_accessed": last_accessed,
                    "in_use": self.is_cache_object_in_use(path),
                }
            )
        return sorted(entries, key=lambda item: (float(item["last_accessed"]), str(item["path"])))

    def _cleanup_empty_parents(self, path: Path) -> None:
        if path.is_relative_to(self.snapshots_dir):
            stop = self.snapshots_dir
        elif path.is_relative_to(self.overlays_dir):
            stop = self.overlays_dir
        else:
            return
        parent = path.parent
        while parent != stop and parent.is_relative_to(stop):
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent

    def _detach_cache_object_locked(self, path: Path) -> tuple[dict[str, int], Path | None]:
        candidate = self._managed_path(path)
        if not candidate.exists():
            return {"removed_entries": 0, "removed_bytes": 0, "skipped_in_use": 0}, None
        lock = self._try_object_exclusive_lock(candidate)
        if lock is None:
            return {"removed_entries": 0, "removed_bytes": 0, "skipped_in_use": 1}, None
        quarantine_root: Path | None = None
        try:
            if not candidate.exists():
                return {"removed_entries": 0, "removed_bytes": 0, "skipped_in_use": 0}, None
            quarantine_root = Path(tempfile.mkdtemp(prefix="evict-", dir=self.tmp_dir))
            detached = quarantine_root / "data"
            try:
                os.replace(candidate, detached)
            except Exception:
                try:
                    quarantine_root.rmdir()
                except OSError:
                    pass
                quarantine_root = None
                raise
            self._cleanup_empty_parents(candidate)
            for sidecar in (self._access_path(candidate), self._meta_path(candidate)):
                try:
                    sidecar.unlink()
                except FileNotFoundError:
                    pass
            return {"removed_entries": 1, "removed_bytes": 0, "skipped_in_use": 0}, quarantine_root
        finally:
            lock.release()

    def _delete_detached_cache_object(self, quarantine_root: Path) -> int:
        detached = quarantine_root / "data"
        size = self._directory_size(detached)
        shutil.rmtree(quarantine_root, ignore_errors=True)
        return size

    def remove_cache_object(self, path: Path, *, timeout: float = 30.0) -> dict[str, int]:
        quarantine_root: Path | None
        with self.cache_transition(exclusive=True, timeout=timeout):
            result, quarantine_root = self._detach_cache_object_locked(path)
        if quarantine_root is not None:
            result["removed_bytes"] = self._delete_detached_cache_object(quarantine_root)
        return result

    def remove_cache_objects(
        self,
        paths: list[Path],
        *,
        timeout: float = 30.0,
    ) -> dict[str, int]:
        removed_entries = 0
        removed_bytes = 0
        skipped_in_use = 0
        blocked_by_transition = 0
        for path in paths:
            try:
                result = self.remove_cache_object(path, timeout=timeout)
            except TimeoutError:
                blocked_by_transition += 1
                continue
            removed_entries += result["removed_entries"]
            removed_bytes += result["removed_bytes"]
            skipped_in_use += result["skipped_in_use"]
        return {
            "removed_entries": removed_entries,
            "removed_bytes": removed_bytes,
            "skipped_in_use": skipped_in_use,
            "blocked_by_transition": blocked_by_transition,
        }

    def prune(self, *, target_bytes: int | None = None, timeout: float = 30.0) -> dict[str, Any]:
        target = self.snapshot_soft_limit_bytes if target_bytes is None else target_bytes
        if target < 0:
            raise ValueError("target_bytes must be >= 0")
        entries = self.cache_entries()
        before_bytes = sum(int(entry["size_bytes"]) for entry in entries)
        remaining = before_bytes
        removed_entries = 0
        removed_bytes = 0
        skipped_in_use = 0
        blocked_by_transition = 0
        for entry in entries:
            if remaining <= target and self._free_bytes() >= self.min_free_bytes:
                break
            try:
                result = self.remove_cache_object(Path(str(entry["path"])), timeout=timeout)
            except TimeoutError:
                blocked_by_transition += 1
                break
            if result["removed_entries"]:
                remaining -= result["removed_bytes"]
            removed_entries += result["removed_entries"]
            removed_bytes += result["removed_bytes"]
            skipped_in_use += result["skipped_in_use"]
        free_after = self._free_bytes()
        return {
            "target_bytes": target,
            "before_bytes": before_bytes,
            "after_bytes": remaining,
            "removed_entries": removed_entries,
            "removed_bytes": removed_bytes,
            "skipped_in_use": skipped_in_use,
            "blocked_by_transition": blocked_by_transition,
            "target_met": remaining <= target,
            "free_space_met": free_after >= self.min_free_bytes,
            "free_bytes": free_after,
            "min_free_bytes": self.min_free_bytes,
        }

    @staticmethod
    def _gib(value: int) -> float:
        return round(value / GIB, 3)

    def cache_status(self) -> dict[str, Any]:
        entries = self.cache_entries()
        totals: dict[str, dict[str, int]] = {}
        for entry in entries:
            kind = str(entry["kind"])
            bucket = totals.setdefault(kind, {"entries": 0, "bytes": 0, "in_use": 0})
            bucket["entries"] += 1
            bucket["bytes"] += int(entry["size_bytes"])
            bucket["in_use"] += int(bool(entry["in_use"]))
        total_bytes = sum(int(entry["size_bytes"]) for entry in entries)
        free_bytes = self._free_bytes()
        return {
            "cache_bytes": total_bytes,
            "cache_gb": self._gib(total_bytes),
            "snapshot_soft_limit_bytes": self.snapshot_soft_limit_bytes,
            "snapshot_soft_limit_gb": self._gib(self.snapshot_soft_limit_bytes),
            "min_free_bytes": self.min_free_bytes,
            "min_free_gb": self._gib(self.min_free_bytes),
            "free_bytes": free_bytes,
            "free_gb": self._gib(free_bytes),
            "over_soft_limit": total_bytes > self.snapshot_soft_limit_bytes,
            "below_free_space_guardrail": free_bytes < self.min_free_bytes,
            "totals_by_kind": totals,
            "entries": entries,
        }

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
